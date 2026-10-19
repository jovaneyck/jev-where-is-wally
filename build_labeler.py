"""Build a page for drawing ground-truth Waldo boxes on the hi-res scenes, pre-filled with our best guesses.

Run:
    1. Put API_KEY=<your TypeSafe key> in .env
    2. uv run build_labeler.py          (scores every tile with the shipped request, ~700 requests;
                                         cached in out/labeler/tiles.jsonl, so an interrupted run resumes)
    3. Open out/label.html, draw one box per scene, click "Download labels.json"
       and save it as data/hi-res/labels.json (the page can load it back to continue).
"""

import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image
from typesafe_sdk import AsyncTypeSafeClient

from probe_lookalikes import PROBES, SCENES
from waldo import jev
from waldo.slicing import slice_scene, to_scene

CONCURRENCY = 8
TILES = Path("out/labeler/tiles.jsonl")
TEMPLATE = Path(__file__).parent / "labeler.template.html"
PAGE = Path("out/label.html")
TOP = 10  # Waldo's region was within the top 3 on every eval scene, but hi-res scenes have ~4x more tiles
GUESS_SIZE = (40, 80)  # scene pixels; roughly Waldo's body on the 2560px hi-res scenes


def guesses(scenes: dict[str, dict], probes, top: int = TOP, size: tuple[int, int] = GUESS_SIZE) -> dict[str, list[dict]]:
    """Per scene: the `top` most likely tiles, plus Waldos spotted by eye in the lookalike probe (centres only)."""
    found = {}
    for name, scene in scenes.items():
        best = sorted(scene["tiles"], key=lambda t: -t["presence"])[:top]
        found[name] = [{"source": f"presence {t['presence']:.2f}", "box": t["box"]} for t in best]
        width, height = size[0] / scene["size"][0] / 2, size[1] / scene["size"][1] / 2
        for fragment, x, y, is_waldo, what in probes:
            if is_waldo and fragment in name:
                box = {"left": x - width, "top": y - height, "right": x + width, "bottom": y + height}
                found[name].append({"source": f"eye: {what}", "box": {edge: round(v, 6) for edge, v in box.items()}})
    return found


async def score(paths: list[Path]) -> dict[str, dict]:
    """Every tile's presence and scene box per scene, from the cache plus the shipped request for the rest."""
    rows = [json.loads(line) for line in TILES.read_text().splitlines()] if TILES.exists() else []
    done = {(r["scene"], r["x"], r["y"]) for r in rows}
    TILES.parent.mkdir(parents=True, exist_ok=True)
    gate = asyncio.Semaphore(CONCURRENCY)
    scenes = {}

    async def one(client, name, size, tile, pixels):
        async with gate:
            answer = await jev.ask(client, pixels)
        box = to_scene(answer.box, tile, size)
        row = {"scene": name, "x": tile.x, "y": tile.y, "presence": answer.presence, "box": asdict(box)}
        with TILES.open("a") as out:
            out.write(json.dumps(row) + "\n")
        rows.append(row)

    async with AsyncTypeSafeClient(api_key=os.environ["API_KEY"], timeout=60) as client:
        jobs = []
        for path in paths:
            size, tiles = slice_scene(Image.open(path))
            scenes[path.name] = {"size": list(size), "tiles": []}
            jobs += [one(client, path.name, size, t, p) for t, p in tiles if (path.name, t.x, t.y) not in done]
        print(f"{len(jobs)} tiles to score")
        await asyncio.gather(*jobs)
    for row in rows:
        scenes[row["scene"]]["tiles"].append({"presence": row["presence"], "box": row["box"]})
    return scenes


if __name__ == "__main__":
    load_dotenv()
    scenes = asyncio.run(score(sorted(SCENES.glob("*.jpg"))))
    PAGE.write_text(
        TEMPLATE.read_text(encoding="utf-8").replace("__GUESSES__", json.dumps(guesses(scenes, PROBES))),
        encoding="utf-8",
    )
    print(f"Wrote {PAGE}")
