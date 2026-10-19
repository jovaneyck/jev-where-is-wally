"""Pass-2 eval: re-rank each scene's top-K labelled regions from cached pass-1 answers with one Choice.

Run:
    1. Put API_KEY=<your TypeSafe key> in .env
    2. uv run eval_tiles.py native_negrefs         (pass 1, once; cached)
    3. uv run rerank_eval.py <config>[#n] ...      config: K[-m<minimum crop px>][-s<side px>], e.g. `3 3#2 3-m128 5`
    Answers are cached in out/rerank/<config>.jsonl.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image as PilImage
from typesafe_sdk import AsyncTypeSafeClient

from eval_tiles import CONCURRENCY, EXCLUDED_SCENES, ORIGINALS, RUNS, SCENE_ORIGINALS, cached
from waldo import rerank, slicing
from waldo.candidates import MINIMUM, crop_box

PASS_1 = RUNS / "native_negrefs.jsonl"
OUT = Path("out/rerank")


def candidate(row: dict, minimum: int) -> PilImage.Image:
    """Crop around the pass-1 box of the region's best native sub-tile, in original pixels."""
    scene, col, row_index = (int(part) for part in Path(row["tile"]).stem.split("_"))
    original = PilImage.open(ORIGINALS / SCENE_ORIGINALS[scene]).convert("RGB")
    left, top, right, bottom = slicing.dataset_region(original.size, col, row_index)
    width, height = right - left, bottom - top
    if min(width, height) < slicing.TILE:  # the region was asked as one upscaled tile
        x, y, size = left, top, (width, height)
    else:
        presences = [sub["presence"] for sub in row["subtiles"]]
        sub = slicing.tiles(width, height)[presences.index(max(presences))]
        x, y, size = left + sub.x, top + sub.y, (slicing.TILE, slicing.TILE)
    box = row["box"]
    pixels = (
        round(x + box["left"] * size[0]),
        round(y + box["top"] * size[1]),
        round(x + box["right"] * size[0]),
        round(y + box["bottom"] * size[1]),
    )
    return original.crop(crop_box(original.size, pixels, minimum=minimum))


def top_k(rows: list[dict], k: int) -> dict[str, list[dict]]:
    scenes = {}
    for row in sorted(rows, key=lambda r: -r["present"]):
        if row["scene"] not in EXCLUDED_SCENES:
            scenes.setdefault(row["scene"], []).append(row)
    return {scene: ranked[:k] for scene, ranked in scenes.items()}


def parse(config: str) -> tuple[int, int, int]:
    """K, minimum crop side and request crop side from `K[-m<px>][-s<px>][#n]`."""
    k, *options = config.split("#")[0].split("-")
    settings = {"m": MINIMUM, "s": rerank.CROP_SIDE} | {option[0]: int(option[1:]) for option in options}
    return int(k), settings["m"], settings["s"]


async def run(config: str, pass_1: list[dict]) -> list[dict]:
    k, minimum, side = parse(config)
    path = OUT / f"{config}.jsonl"
    done = {row["scene"]: row for row in (json.loads(l) for l in path.read_text().splitlines())} if path.exists() else {}
    path.parent.mkdir(parents=True, exist_ok=True)
    gate = asyncio.Semaphore(CONCURRENCY)

    async def one(client, scene, ranked):
        crops = [candidate(row, minimum) for row in ranked]
        async with gate:
            forward, backward = await asyncio.gather(
                rerank.ask(client, crops, False, side), rerank.ask(client, crops, True, side)
            )
        row = {"scene": scene, "ranked": [r["tile"] for r in ranked], "forward": forward, "backward": backward}
        with path.open("a") as out:
            out.write(json.dumps(row) + "\n")
        done[scene] = row

    todo = {s: r for s, r in top_k(pass_1, k).items() if s not in done}
    async with AsyncTypeSafeClient(api_key=os.environ["API_KEY"], timeout=120) as client:
        await asyncio.gather(*(one(client, s, r) for s, r in todo.items()))
    return list(done.values())


def is_waldo(tile: str) -> bool:
    return Path(tile).parent.name == "waldo"


def report(config: str, rows: list[dict]) -> None:
    has_waldo = [r for r in rows if any(is_waldo(t) for t in r["ranked"])]
    first = second = forced = nones = agreed = 0
    changes = []
    for row in sorted(rows, key=lambda r: int(r["scene"])):
        winner, agreement = rerank.combine(row["forward"], row["backward"])
        nones += winner == rerank.NONE
        agreed += agreement
        pick = row["ranked"][0] if winner == rerank.NONE else row["ranked"][int(winner[1:]) - 1]
        first += is_waldo(row["ranked"][0])
        second += is_waldo(pick)
        without_none = {o: p for o, p in row["forward"].items() if o != rerank.NONE}
        best, _ = rerank.combine(without_none, {o: row["backward"][o] for o in without_none})
        forced += is_waldo(row["ranked"][int(best[1:]) - 1])
        if is_waldo(pick) != is_waldo(row["ranked"][0]):
            changes.append(f"{row['scene']}:{'fixed' if is_waldo(pick) else 'broken'}")
    n = len(has_waldo)
    print(
        f"{config:6} scenes={n} pass1={first}/{n} pass2={second}/{n} forced={forced}/{n} "
        f"none_wins={nones} orders_agree={agreed}/{len(rows)} {' '.join(changes)}"
    )


async def main(configs: list[str]) -> None:
    pass_1 = list(cached(PASS_1).values())
    for config in configs:
        report(config, await run(config, pass_1))


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main(sys.argv[1:]))
