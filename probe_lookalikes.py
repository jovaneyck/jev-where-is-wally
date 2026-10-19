"""Targeted lookalike probe: do prompt variants separate verified Waldos from verified lookalikes?

Native-resolution 256px tiles centred on solver picks in the redacted hi-res scenes, each verified by eye
(hillclimb.md). Run:
    uv run probe_lookalikes.py <variant> ...      (tile variants from eval_tiles.py)
Each variant is asked REPEATS times per probe; answers are cached in out/probes/<variant>.jsonl.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image
from typesafe_sdk import AsyncTypeSafeClient

from eval_tiles import contrast_description, negative_references
from waldo import jev
from waldo.metrics import Scored, auc
from waldo.slicing import TILE

SCENES = Path("data/hi-res")
OUT = Path("out/probes")
REPEATS = 3
# scene file stem fragment, box centre as fractions, is Waldo, what it is
PROBES = [
    ("Skiing", 0.856, 0.729, True, "Waldo with camera gear"),
    ("Film-Set", 0.828, 0.575, True, "Waldo, glasses, peeking"),
    ("Food-Court", 0.567, 0.361, True, "Waldo"),
    ("Underground", 0.706, 0.059, True, "Waldo among cavemen"),
    ("Candy-Factory", 0.502, 0.899, True, "Waldo behind chef"),
    ("Space-Station", 0.299, 0.531, True, "Waldo partly hidden"),
    ("GIANTS", 0.177, 0.661, True, "Waldo in crowd"),
    ("Toys", 0.3225, 0.8354, True, "Waldo among toys"),
    ("Ocean", 0.517, 0.237, True, "Waldo behind bearded man"),
    ("Beach", 0.773, 0.408, False, "Wenda"),
    ("Skiing", 0.4895, 0.425, False, "Wenda"),
    ("Film-Set", 0.8265, 0.758, False, "Waldo-watcher, no glasses"),
    ("Toys", 0.5287, 0.8738, False, "striped torso, no face"),
    ("Ocean", 0.0736, 0.0363, False, "fisherman in striped shirt"),
]
VARIANTS = {"phrasings": lambda tile: jev.request(tile, negatives=False), "negrefs": negative_references, "contrast": contrast_description}


def scene_path(fragment: str) -> Path:
    return next(SCENES.glob(f"*{fragment}*.jpg"))


def probe_tile(fragment: str, cx: float, cy: float) -> Image.Image:
    scene = Image.open(scene_path(fragment)).convert("RGB")
    x = min(max(round(cx * scene.width) - TILE // 2, 0), scene.width - TILE)
    y = min(max(round(cy * scene.height) - TILE // 2, 0), scene.height - TILE)
    return scene.crop((x, y, x + TILE, y + TILE))


async def run(name: str, client: AsyncTypeSafeClient) -> list[dict]:
    path = OUT / f"{name}.jsonl"
    if path.exists():
        return [json.loads(line) for line in path.read_text().splitlines()]

    async def one(index: int, repeat: int) -> dict:
        fragment, cx, cy, is_waldo, what = PROBES[index]
        state, questions = VARIANTS[name](probe_tile(fragment, cx, cy))
        answer = jev.read(await client.system_one(state=state, questions=questions, model=jev.MODEL, extra_headers=jev.HEADERS))
        return {"probe": index, "repeat": repeat, "is_waldo": is_waldo, "what": f"{fragment}: {what}",
                "presence": answer.presence, "nouls": answer.nouls}  # fmt: skip

    rows = await asyncio.gather(*(one(i, r) for i in range(len(PROBES)) for r in range(REPEATS)))
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return rows


def report(name: str, rows: list[dict]) -> None:
    by_probe: dict[int, list[dict]] = {}
    for row in rows:
        by_probe.setdefault(row["probe"], []).append(row)
    mean = lambda values: sum(values) / len(values)  # noqa: E731
    signals = {"presence": lambda r: r["presence"]}
    if "lookalike_wenda" in rows[0]["nouls"]:
        for weight in (0.25, 0.5, 1.0):
            signals[f"presence-{weight}*lookalike"] = lambda r, w=weight: r["presence"] - w * max(
                r["nouls"]["lookalike_wenda"], r["nouls"]["lookalike_watcher"]
            )
    print(f"== {name}")
    for label, signal in signals.items():
        scored = [Scored("probe", rs[0]["is_waldo"], mean([signal(r) for r in rs])) for rs in by_probe.values()]
        print(f"{label:28} auc={auc(scored):.3f}")
    for rs in by_probe.values():
        extra = {k: round(mean([r["nouls"][k] for r in rs]), 2) for k in rs[0]["nouls"] if k.startswith("lookalike")}
        print(f"   {'WALDO' if rs[0]['is_waldo'] else 'other'} presence={mean([r['presence'] for r in rs]):.2f} {extra} {rs[0]['what']}")


async def main(names: list[str]) -> None:
    async with AsyncTypeSafeClient(api_key=os.environ["API_KEY"], timeout=60) as client:
        for name in names:
            report(name, await run(name, client))


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main(sys.argv[1:]))
