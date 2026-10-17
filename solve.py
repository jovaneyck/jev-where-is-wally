"""Find Waldo in every original scene and write an HTML report.

Run:
    1. Put API_KEY=<your TypeSafe key> in .env
    2. uv run solve.py
    3. Open out/solution.html
"""

import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image
from typesafe_sdk import AsyncTypeSafeClient

from waldo.report import Entry, draw_box, render
from waldo.solver import solve

SCENES = Path("data/wheres-waldo/Hey-Waldo/original-images")
OUT = Path("out")
CONCURRENCY = 16


async def solve_scene(client: AsyncTypeSafeClient, path: Path, gate: asyncio.Semaphore) -> Entry:
    scene = Image.open(path)
    solution = await solve(client, scene, gate)
    drawn = Path("solution") / path.name
    draw_box(scene, solution.box).save(OUT / drawn)
    print(f"{path.name:7} {'Waldo' if solution.found else 'No Waldo':8} presence={solution.presence:.2f} {solution.box}")
    return Entry(name=path.name, image=drawn.as_posix(), size=scene.size, solution=solution)


async def main() -> None:
    (OUT / "solution").mkdir(parents=True, exist_ok=True)
    scenes = sorted(SCENES.glob("*.jpg"), key=lambda p: int(p.stem))
    gate = asyncio.Semaphore(CONCURRENCY)
    async with AsyncTypeSafeClient(api_key=os.environ["API_KEY"], timeout=60) as client:
        entries = await asyncio.gather(*(solve_scene(client, p, gate) for p in scenes))
    (OUT / "solution.html").write_text(render(entries), encoding="utf-8")
    (OUT / "solution.json").write_text(json.dumps([asdict(e) for e in entries], indent=2))
    print(f"Wrote {OUT / 'solution.html'}")


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
