import asyncio
from dataclasses import dataclass

from PIL import Image
from typesafe_sdk import AsyncTypeSafeClient

from waldo import jev
from waldo.slicing import Box, Tile, slice_scene, to_scene

# Tile-level optimum moved between 0.42 and 0.51 across two eval runs; see hillclimb.md
THRESHOLD = 0.5


@dataclass(frozen=True)
class Solution:
    found: bool
    presence: float
    box: Box  # fractions of the scene


def pick(answers: list[tuple[Tile, jev.TileAnswer]], scene_size: tuple[int, int]) -> Solution:
    tile, best = max(answers, key=lambda pair: pair[1].presence)
    return Solution(found=best.presence >= THRESHOLD, presence=best.presence, box=to_scene(best.box, tile, scene_size))


async def solve(client: AsyncTypeSafeClient, scene: Image.Image, gate: asyncio.Semaphore) -> Solution:
    size, tiles = slice_scene(scene)

    async def ask(tile: Tile, pixels: Image.Image) -> tuple[Tile, jev.TileAnswer]:
        async with gate:
            return tile, await jev.ask(client, pixels)

    return pick(await asyncio.gather(*(ask(t, p) for t, p in tiles)), size)
