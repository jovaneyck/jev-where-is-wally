"""Hill-climbing eval on the hi-res scenes against hand-drawn labels (data/hi-res/labels.json).

Run:
    1. Put API_KEY=<your TypeSafe key> in .env
    2. uv run build_labeler.py                 (once: shipped request on all 700 tiles, the baseline)
    3. uv run hires_eval.py [variant[#n] ...]   no variant: report the baseline only
       uv run hires_eval.py solution             score the solver's out/solution.json end to end
       uv run hires_eval.py --scenes=Film-Set,Ocean ...   only scenes whose name contains a fragment
    A variant is asked on a subset: every Waldo tile plus each scene's HARD most likely non-Waldo tiles
    under the baseline; WHOLE_SCENE variants are asked on every tile. Answers are cached in out/hires/<run>.jsonl.
"""

import asyncio
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image
from typesafe_sdk import AsyncTypeSafeClient

from build_labeler import TILES as BASELINE
from eval_tiles import negative_references
from probe_lookalikes import SCENES
from waldo import batch, jev
from waldo.candidates import zoom_frame
from waldo.ground_truth import contains_waldo, iou
from waldo.metrics import Scored, auc
from waldo.slicing import TILE, Box, in_frame
from waldo.solver import SHORTLIST

LABELS = SCENES / "labels.json"
SOLUTION = Path("out/solution.json")
OUT = Path("out/hires")
CONCURRENCY = 8
HARD = 10


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def scene_sizes() -> dict[str, tuple[int, int]]:
    return {p.name: Image.open(p).size for p in SCENES.glob("*.jpg")}


def tile_area(row: dict, size: tuple[int, int]) -> Box:
    return Box(row["x"] / size[0], row["y"] / size[1], (row["x"] + TILE) / size[0], (row["y"] + TILE) / size[1])


def tile_frame(scene: Image.Image, row: dict) -> tuple[int, int, int, int]:
    return row["x"], row["y"], row["x"] + TILE, row["y"] + TILE


def zoom(minimum: int):
    """Square crop around the baseline box of the tile, `minimum` px or 3x the box, asked like a tile."""
    return lambda scene, row: zoom_frame(Box(**row["box"]), scene.size, minimum)


VARIANTS = {  # name: (frame in scene pixels, request for a TILE-sized image)
    "shipped": (tile_frame, jev.request),
    "negrefs": (tile_frame, negative_references),
    "zoom64": (zoom(64), jev.request),
    "zoom96": (zoom(96), jev.request),
    "zoom128": (zoom(128), jev.request),
    "zoom192": (zoom(192), jev.request),
    "zoom128_negrefs": (zoom(128), negative_references),
}


def subset(baseline: list[dict], labels: dict[str, Box], sizes: dict) -> list[dict]:
    """Every Waldo tile, plus each scene's HARD most likely other tiles."""
    chosen = []
    for scene in labels:
        ranked = sorted((r for r in baseline if r["scene"] == scene), key=lambda r: -r["presence"])
        waldo = [r for r in ranked if contains_waldo(tile_area(r, sizes[scene]), labels[scene])]
        chosen += waldo + [r for r in ranked if r not in waldo][:HARD]
    return chosen


async def run(name: str, tiles: list[dict]) -> list[dict]:
    frame_of, request = VARIANTS[name.split("#")[0]]
    path = OUT / f"{name}.jsonl"
    rows = load(path)
    done = {(r["scene"], r["x"], r["y"]) for r in rows}
    path.parent.mkdir(parents=True, exist_ok=True)
    scenes = {scene: Image.open(SCENES / scene).convert("RGB") for scene in {t["scene"] for t in tiles}}
    gate = asyncio.Semaphore(CONCURRENCY)

    async def one(client, tile):
        scene = scenes[tile["scene"]]
        frame = frame_of(scene, tile)
        state, questions = request(scene.crop(frame).resize((TILE, TILE), Image.Resampling.LANCZOS))
        async with gate:
            answer = jev.read(await client.system_one(state=state, questions=questions, model=jev.MODEL, extra_headers=jev.HEADERS))
        box = in_frame(answer.box, frame, scene.size)
        row = {**{k: tile[k] for k in ("scene", "x", "y")}, "presence": answer.presence, "nouls": answer.nouls, "box": asdict(box)}
        with path.open("a") as out:
            out.write(json.dumps(row) + "\n")
        rows.append(row)

    async with AsyncTypeSafeClient(api_key=os.environ["API_KEY"], timeout=60) as client:
        await asyncio.gather(*(one(client, t) for t in tiles if (t["scene"], t["x"], t["y"]) not in done))
    return rows


BATCHED = {  # name: (frame, crops per request, crop side in the request)
    "batched128_g4": (zoom(128), batch.GROUP, batch.SIDE),
    "batched128_s768": (zoom(128), HARD + 1, 768),  # all of a scene's subset tiles in one request
    "pass1_g4": (tile_frame, batch.GROUP, batch.SIDE),  # pass 1 batched: whole tiles, as the shipped request
}
WHOLE_SCENE = {"pass1_g4"}
BATCHED["pass2_after_pass1_g4"] = (zoom(128), batch.GROUP, batch.SIDE)
SHORTLIST_FROM = {"pass2_after_pass1_g4": "pass1_g4"}  # name: run whose top SHORTLIST tiles it re-scores, like the solver


def top(rows: list[dict], k: int = SHORTLIST) -> list[dict]:
    by_scene = {}
    for row in sorted(rows, key=lambda r: -r["presence"]):
        by_scene.setdefault(row["scene"], []).append(row)
    return [row for ranked in by_scene.values() for row in ranked[:k]]


async def run_batched(name: str, tiles: list[dict]) -> list[dict]:
    frame_of, group_size, side = BATCHED[name.split("#")[0]]
    path = OUT / f"{name}.jsonl"
    rows = load(path)
    done = {(r["scene"], r["x"], r["y"]) for r in rows}
    path.parent.mkdir(parents=True, exist_ok=True)
    gate = asyncio.Semaphore(CONCURRENCY)

    async def one(client, scene_name, group):
        scene = Image.open(SCENES / scene_name).convert("RGB")
        frames = [frame_of(scene, t) for t in group]
        crops = [scene.crop(f).resize((TILE, TILE), Image.Resampling.LANCZOS) for f in frames]
        async with gate:
            answers = await batch.ask(client, crops, side)
        new = [
            {**{k: t[k] for k in ("scene", "x", "y")}, "presence": a.presence, "nouls": a.nouls,
             "box": asdict(in_frame(a.box, f, scene.size))}
            for t, f, a in zip(group, frames, answers)
        ]  # fmt: skip
        with path.open("a") as out:
            out.writelines(json.dumps(row) + "\n" for row in new)
        rows.extend(new)

    by_scene = {}
    for t in sorted(tiles, key=lambda t: (t["y"], t["x"])):  # by position: subset order lists Waldo first
        if (t["scene"], t["x"], t["y"]) not in done:
            by_scene.setdefault(t["scene"], []).append(t)
    groups = [(s, ts[i : i + group_size]) for s, ts in by_scene.items() for i in range(0, len(ts), group_size)]
    print(f"{name}: {len(groups)} requests")
    async with AsyncTypeSafeClient(api_key=os.environ["API_KEY"], timeout=300) as client:
        await asyncio.gather(*(one(client, s, g) for s, g in groups))
    return rows


def report(name: str, rows: list[dict], labels: dict[str, Box], sizes: dict) -> None:
    by_scene = {}
    for row in rows:
        by_scene.setdefault(row["scene"], []).append(row)
    scored, ranks, tile_hits, box_hits, ious, waldo_box_hits = [], [], 0, 0, [], 0
    for scene, tiles in sorted(by_scene.items()):
        label, size = labels[scene], sizes[scene]
        ranked = sorted(tiles, key=lambda r: -r["presence"])
        is_waldo = [contains_waldo(tile_area(r, size), label) for r in ranked]
        scored += [Scored(scene, w, r["presence"]) for r, w in zip(ranked, is_waldo)]
        ranks.append(is_waldo.index(True) + 1 if True in is_waldo else None)
        top_box = Box(**ranked[0]["box"])
        tile_hits += is_waldo[0]
        box_hits += iou(top_box, label) > 0
        ious.append(iou(top_box, label))
        waldo_tile = next((r for r, w in zip(ranked, is_waldo) if w), None)
        waldo_box_hits += waldo_tile is not None and iou(Box(**waldo_tile["box"]), label) > 0
    n = len(by_scene)
    print(
        f"{name:22} auc={auc(scored):.3f} top1_tile={tile_hits}/{n} top1_box={box_hits}/{n} "
        f"mean_iou={sum(ious) / n:.2f} best_waldo_tile_box={waldo_box_hits}/{n} waldo_rank={ranks}"
    )


def report_solution(labels: dict[str, Box]) -> None:
    """Hit when the solver's box overlaps the label."""
    entries = json.loads(SOLUTION.read_text())
    for e in entries:
        overlap = iou(Box(**e["solution"]["box"]), labels[e["name"]])
        print(f"{'hit ' if overlap > 0 else 'MISS'} iou={overlap:.2f} presence={e['solution']['presence']:.2f} {e['name']}")
    hits = sum(iou(Box(**e["solution"]["box"]), labels[e["name"]]) > 0 for e in entries)
    print(f"solution: {hits}/{len(entries)} boxes on Waldo")


if __name__ == "__main__":
    load_dotenv()
    labels = {scene: Box(**box) for scene, box in json.loads(LABELS.read_text()).items()}
    if sys.argv[1:] == ["solution"]:
        sys.exit(report_solution(labels))
    fragments = next((a.removeprefix("--scenes=").split(",") for a in sys.argv[1:] if a.startswith("--scenes=")), [""])
    labels = {scene: box for scene, box in labels.items() if any(f in scene for f in fragments)}
    sizes = scene_sizes()
    baseline = [r for r in load(BASELINE) if r["scene"] in labels]
    report(f"baseline (all {len(baseline)} tiles)", baseline, labels, sizes)
    tiles = subset(baseline, labels, sizes)
    keys = {(t["scene"], t["x"], t["y"]) for t in tiles}
    report(f"baseline ({len(tiles)} subset)", [r for r in baseline if (r["scene"], r["x"], r["y"]) in keys], labels, sizes)
    for name in (a for a in sys.argv[1:] if not a.startswith("--")):
        variant = name.split("#")[0]
        runner = run_batched if variant in BATCHED else run
        if variant in SHORTLIST_FROM:
            asked = top([r for r in load(OUT / f"{SHORTLIST_FROM[variant]}.jsonl") if r["scene"] in labels])
        else:
            asked = baseline if variant in WHOLE_SCENE else tiles
        rows = asyncio.run(runner(name, asked))
        report(name, [r for r in rows if r["scene"] in labels], labels, sizes)
