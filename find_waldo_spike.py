"""Spike: ask Jev whether Waldo is in labelled dataset tiles and where.

Run:
    1. Put API_KEY=<your TypeSafe key> in .env
    2. uv run find_waldo_spike.py
    Prints one line per tile and writes each tile with its returned box drawn on it to out/
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image as PilImage
from PIL import ImageDraw
from typesafe_sdk import Box, Image, Noul, TypeSafeClient

TILES = Path("data/wheres-waldo/Hey-Waldo/256")
SAMPLES = [
    TILES / "waldo/1_1_1.jpg",
    TILES / "waldo/5_0_1.jpg",
    TILES / "waldo/9_1_1.jpg",
    TILES / "notwaldo/1_0_0.jpg",
    TILES / "notwaldo/5_2_2.jpg",
    TILES / "notwaldo/9_3_3.jpg",
]
UPSCALE = 2  # tiles are 256px, the API minimum side is 280px
# Questions don't see each other's instructions: share the description via state so every question gets it
WALDO = "red-and-white striped shirt and bobble hat, round glasses"
OUT = Path("out")


def load_tile(path: Path) -> PilImage.Image:
    tile = PilImage.open(path).convert("RGB")
    return tile.resize((tile.width * UPSCALE, tile.height * UPSCALE), PilImage.Resampling.LANCZOS)


def ask(client: TypeSafeClient, tile: PilImage.Image):
    return client.system_one(
        state={"scene": Image.from_pil(tile), "waldo": WALDO},
        questions={
            "waldo_present": Noul(instructions="Is Waldo, as described in `waldo`, in `scene`?"),
            "waldo": Box(instructions="Waldo, as described in `waldo`, in `scene`"),
        },
        model="jev-preview",
        extra_headers={"TypeSafe-Danger-Zone-Images": "true"},
    )


def draw_box(tile: PilImage.Image, edges) -> PilImage.Image:
    ImageDraw.Draw(tile).rectangle(
        (edges.left * tile.width, edges.top * tile.height, edges.right * tile.width, edges.bottom * tile.height),
        outline="lime",
        width=4,
    )
    return tile


load_dotenv()
OUT.mkdir(exist_ok=True)

with TypeSafeClient(api_key=os.environ["API_KEY"]) as client:
    for path in SAMPLES:
        tile = load_tile(path)
        result = ask(client, tile)
        present = result.answers["waldo_present"].noul
        box = result.boxes["waldo"]
        print(f"{path.parent.name:9} {path.name:10} present={present:.2f} box={box.box} confidence={box.confidence:.2f}")
        draw_box(tile, box.box).save(OUT / f"{path.parent.name}-{path.name}")
