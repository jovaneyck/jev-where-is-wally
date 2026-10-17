"""Hill-climbing eval: run a prompt variant over every labelled 256px colour tile and score it.

Run:
    1. Put API_KEY=<your TypeSafe key> in .env
    2. uv run eval_tiles.py <variant>[#n] ...      (see VARIANTS below)
    Answers are cached in out/runs/<run>.jsonl, so an interrupted run resumes.
    Several runs are averaged per tile, e.g. `reference_x6 reference_x6#2` scores a 2-run ensemble.
"""

import asyncio
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image as PilImage
from typesafe_sdk import AsyncTypeSafeClient, Box, Image, Noul

from waldo import jev, slicing
from waldo.jev import REFERENCE, WALDO
from waldo.metrics import Scored, auc, scene_hit_rate

TILES = Path("data/wheres-waldo/Hey-Waldo/256")
ORIGINALS = Path("data/wheres-waldo/Hey-Waldo/original-images-unredacted")  # tiles were cut before redaction
# Tile scene ids don't match original file names; found by template matching. 2/5 and 3/6 are duplicates.
SCENE_ORIGINALS = {
    1: "1.jpg", 2: "17.jpg", 3: "18.jpg", 4: "19.jpg", 5: "17.jpg", 6: "18.jpg", 7: "3.jpg",
    8: "4.jpg", 9: "5.jpg", 10: "6.jpg", 11: "7.jpg", 12: "10.jpg", 13: "8.jpg", 14: "9.jpg",
    15: "11.jpg", 16: "12.jpg", 17: "13.jpg", 18: "14.jpg", 19: "15.jpg", 20: "2.jpg", 21: "16.jpg",
}  # fmt: skip
RUNS = Path("out/runs")
UPSCALE = 2  # tiles are 256px, the API minimum side is 280px
CONCURRENCY = 16
EXCLUDED_SCENES = {"1"}  # REFERENCE is cropped from scene 1
LOOKALIKES = {
    "true": "A person matching `waldo`: round glasses, bobble hat and red-and-white striped shirt together.",
    "false": "No such person. Other people in red-and-white stripes, striped objects, "
    "or people missing the round glasses or bobble hat don't count.",
}


def questions(present_criteria=None) -> dict:
    return {
        "present": Noul(instructions="Is Waldo, as shown in `waldo`, in `scene`?", criteria=present_criteria),
        "box": Box(instructions="Waldo, as shown in `waldo`, in `scene`"),
    }


def upscaled(tile: PilImage.Image, factor: int = UPSCALE, resample=PilImage.Resampling.LANCZOS) -> Image:
    return Image.from_pil(tile.resize((tile.width * factor, tile.height * factor), resample))


def baseline(tile: PilImage.Image):
    return {"scene": upscaled(tile), "waldo": WALDO}, questions()


def reference(tile: PilImage.Image, factor: int = UPSCALE, resample=PilImage.Resampling.LANCZOS, asked=questions):
    return {"scene": upscaled(tile, factor, resample), "waldo": {"description": WALDO, "picture": REFERENCE}}, asked()


def reference_lookalikes(tile: PilImage.Image):
    state, _ = reference(tile)
    return state, questions(LOOKALIKES)


def load_tile(path: Path) -> PilImage.Image:
    return PilImage.open(path).convert("RGB")


def native_tiles(path: Path) -> list[PilImage.Image]:
    """The labelled tile's region cut from the original at native resolution, as TILE-sized sub-tiles."""
    scene, col, row = (int(part) for part in path.stem.split("_"))
    original = PilImage.open(ORIGINALS / SCENE_ORIGINALS[scene]).convert("RGB")
    region = original.crop(slicing.dataset_region(original.size, col, row))
    if min(region.size) < slicing.TILE:  # original is below dataset scale: nothing to gain
        return [region.resize((slicing.TILE, slicing.TILE), PilImage.Resampling.LANCZOS)]
    return [region.crop((t.x, t.y, t.x + slicing.TILE, t.y + slicing.TILE)) for t in slicing.tiles(*region.size)]


def on_tile(build):
    """Variant asking one request about the labelled 256px tile itself."""
    return lambda path: [build(load_tile(path))]


VARIANTS = {
    "baseline": on_tile(baseline),
    "reference": on_tile(reference),
    "reference_rerun": on_tile(reference),  # same prompt, measures run-to-run noise
    "reference_lookalikes": on_tile(reference_lookalikes),
    "reference_x4": on_tile(lambda tile: reference(tile, 4)),
    "reference_x6": on_tile(lambda tile: reference(tile, 6)),
    "x6_nearest": on_tile(lambda tile: reference(tile, 6, PilImage.Resampling.NEAREST)),
    "x6_lookalikes": on_tile(lambda tile: reference(tile, 6, asked=lambda: questions(LOOKALIKES))),
    "x6_phrasings": on_tile(jev.request),  # the shipped solver request
    "x6_phrasings_lookalikes": on_tile(lambda tile: jev.request(tile, LOOKALIKES)),
    # region scored by its most likely native-resolution sub-tile, as the solver picks its most likely tile
    "native_x6_phrasings": lambda path: [jev.request(t) for t in native_tiles(path)],
}


def labelled_tiles() -> list[Path]:
    return sorted(TILES.glob("waldo/*.jpg")) + sorted(TILES.glob("notwaldo/*.jpg"))


def cached(run: Path) -> dict[str, dict]:
    if not run.exists():
        return {}
    rows = (json.loads(line) for line in run.read_text().splitlines())
    return {row["tile"]: row for row in rows}


async def ask(client: AsyncTypeSafeClient, variant, path: Path) -> dict:
    async def one(state, questions) -> jev.TileAnswer:
        return jev.read(
            await client.system_one(state=state, questions=questions, model=jev.MODEL, extra_headers=jev.HEADERS)
        )

    answers = await asyncio.gather(*(one(*request) for request in variant(path)))
    best = max(answers, key=lambda a: a.presence)
    return {
        "tile": path.as_posix(),
        "scene": path.name.split("_")[0],
        "is_waldo": path.parent.name == "waldo",
        "present": best.presence,
        "nouls": best.nouls,
        "box_confidence": best.box_confidence,
        "box": asdict(best.box),
        "requests": len(answers),
    }


async def run(name: str) -> list[dict]:
    """`name` is a variant, optionally suffixed with #n to repeat it as a separate run."""
    variant = VARIANTS[name.split("#")[0]]
    path = RUNS / f"{name}.jsonl"
    rows = cached(path)
    todo = [t for t in labelled_tiles() if t.as_posix() not in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    gate = asyncio.Semaphore(CONCURRENCY)

    async def one(client, tile):
        async with gate:
            row = await ask(client, variant, tile)
        with path.open("a") as out:
            out.write(json.dumps(row) + "\n")
        rows[row["tile"]] = row

    async with AsyncTypeSafeClient(api_key=os.environ["API_KEY"], timeout=60) as client:
        await asyncio.gather(*(one(client, t) for t in todo))
    return list(rows.values())


def averaged(runs: list[list[dict]]) -> list[dict]:
    by_tile = [{r["tile"]: r for r in rows} for rows in runs]
    return [
        {
            **row,
            "present": sum(rows[tile]["present"] for rows in by_tile) / len(by_tile),
            "box_confidence": sum(rows[tile]["box_confidence"] for rows in by_tile) / len(by_tile),
        }
        for tile, row in by_tile[0].items()
    ]


async def run_all(names: list[str]) -> list[list[dict]]:
    return [await run(name) for name in names]


def report(rows: list[dict]) -> None:
    signals = {
        "present": lambda r: r["present"],
        "box_confidence": lambda r: r["box_confidence"],
        "present*box": lambda r: r["present"] * r["box_confidence"],
    }
    rows = [r for r in rows if r["scene"] not in EXCLUDED_SCENES]
    print(f"{len(rows)} tiles")
    for name, signal in signals.items():
        tiles = [Scored(r["scene"], r["is_waldo"], signal(r)) for r in rows]
        print(f"{name:15} auc={auc(tiles):.3f} scene_hit_rate={scene_hit_rate(tiles):.3f}")


if __name__ == "__main__":
    load_dotenv()
    report(averaged(asyncio.run(run_all(sys.argv[1:]))))
