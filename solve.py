"""Find Waldo in every scene of a folder and write an HTML report.

Run:
    1. Put API_KEY=<your TypeSafe key> in .env
    2. uv run redact_stamps.py      (once: hides Waldo portraits on stamps, seals and lineups)
    3. uv run solve.py [folder]     (default: data/hi-res)
    4. Open out/solution.html
"""

import asyncio
import json
import os
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image
from typesafe_sdk import AsyncTypeSafeClient

from waldo.report import Entry, draw_box, render
from waldo.solver import solve

SCENES = Path("data/hi-res")
OUT = Path("out")
CONCURRENCY = 8


async def solve_scene(client: AsyncTypeSafeClient, path: Path, gate: asyncio.Semaphore) -> Entry:
    scene = Image.open(path)
    solution = await solve(client, scene, gate)
    drawn = Path("solution") / path.name
    draw_box(scene, solution.box).save(OUT / drawn)
    print(f"{path.name} {'Waldo' if solution.found else 'No Waldo'} presence={solution.presence:.2f} {solution.box}")
    return Entry(name=path.name, image=drawn.as_posix(), size=scene.size, solution=solution)


async def main(folder: Path) -> None:
    shutil.rmtree(OUT / "solution", ignore_errors=True)
    (OUT / "solution").mkdir(parents=True)
    scenes = sorted(folder.glob("*.jpg"), key=lambda p: (len(p.stem), p.stem))  # 2.jpg before 10.jpg
    gate = asyncio.Semaphore(CONCURRENCY)
    async with AsyncTypeSafeClient(api_key=os.environ["API_KEY"], timeout=60) as client:
        entries = await asyncio.gather(*(solve_scene(client, p, gate) for p in scenes))
    (OUT / "solution.html").write_text(render(entries), encoding="utf-8")
    (OUT / "solution.json").write_text(json.dumps([asdict(e) for e in entries], indent=2))
    print(f"Wrote {OUT / 'solution.html'}")


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main(Path(sys.argv[1]) if len(sys.argv) > 1 else SCENES))
