import asyncio
from dataclasses import dataclass

from PIL import Image
from typesafe_sdk import AsyncTypeSafeClient

from waldo import batch, jev
from waldo.candidates import zoom_frame
from waldo.slicing import TILE, Box, Tile, in_frame, resized, slice_scene, to_scene

# Tile-level optimum moved between 0.42 and 0.51 across two eval runs; see hillclimb.md.
# Not recalibrated for zoomed presence: every labelled scene contains Waldo, so "No Waldo" can't be measured.
THRESHOLD = 0.5
SHORTLIST = 10  # Waldo's tile ranked at most 7th in pass 1 on every labelled hi-res scene

Frame = tuple[int, int, int, int]  # pixels of the resized scene: left, top, right, bottom


@dataclass(frozen=True)
class Solution:
    found: bool
    presence: float
    box: Box  # fractions of the scene


def shortlist(answers: list[tuple[Tile, jev.TileAnswer]], k: int = SHORTLIST) -> list[tuple[Tile, jev.TileAnswer]]:
    """The k most likely tiles, ordered by position as in the eval, so batches don't start with the favourite."""
    best = sorted(answers, key=lambda pair: -pair[1].presence)[:k]
    return sorted(best, key=lambda pair: (pair[0].y, pair[0].x))


def pick(answers: list[tuple[Frame, jev.TileAnswer]], scene_size: tuple[int, int]) -> Solution:
    frame, best = max(answers, key=lambda pair: pair[1].presence)
    return Solution(found=best.presence >= THRESHOLD, presence=best.presence, box=in_frame(best.box, frame, scene_size))


async def solve(client: AsyncTypeSafeClient, scene: Image.Image, gate: asyncio.Semaphore) -> Solution:
    """Pass 1 scores every tile; pass 2 re-scores the shortlist's zoom crops, batched (hillclimb.md)."""
    size, tiles = slice_scene(scene)

    async def ask(tile: Tile, pixels: Image.Image) -> tuple[Tile, jev.TileAnswer]:
        async with gate:
            return tile, await jev.ask(client, pixels)

    candidates = shortlist(await asyncio.gather(*(ask(t, p) for t, p in tiles)))
    frames = [zoom_frame(to_scene(a.box, t, size), size) for t, a in candidates]
    scaled = resized(scene)
    crops = [scaled.crop(f).resize((TILE, TILE), Image.Resampling.LANCZOS) for f in frames]

    async def ask_batch(group: list[Image.Image]) -> list[jev.TileAnswer]:
        async with gate:
            return await batch.ask(client, group)

    groups = [crops[i : i + batch.GROUP] for i in range(0, len(crops), batch.GROUP)]
    zoomed = [answer for answers in await asyncio.gather(*(ask_batch(g) for g in groups)) for answer in answers]
    return pick(list(zip(frames, zoomed)), size)
