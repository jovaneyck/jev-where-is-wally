"""Cut a scene into tiles at the scale the hill-climb chose (see hillclimb.md)."""

from dataclasses import dataclass

from PIL import Image

SHORT_SIDE = 1024  # dataset tiles come from scenes resized to this short side
TILE = 256


@dataclass(frozen=True)
class Box:
    """Edges as fractions of an image's width and height."""

    left: float
    top: float
    right: float
    bottom: float


@dataclass(frozen=True)
class Tile:
    """Top-left corner of a tile, in pixels of the resized scene."""

    x: int
    y: int


def offsets(length: int, tile: int = TILE) -> list[int]:
    """Tile starts covering `length`; the last tile is aligned to the edge so every tile is full size."""
    starts = list(range(0, length - tile + 1, tile))
    return starts if starts[-1] + tile == length else [*starts, length - tile]


def tiles(width: int, height: int) -> list[Tile]:
    return [Tile(x, y) for y in offsets(height) for x in offsets(width)]


def to_scene(box: Box, tile: Tile, scene_size: tuple[int, int], size: int = TILE) -> Box:
    width, height = scene_size
    return Box(
        left=(tile.x + box.left * size) / width,
        top=(tile.y + box.top * size) / height,
        right=(tile.x + box.right * size) / width,
        bottom=(tile.y + box.bottom * size) / height,
    )


def dataset_region(scene_size: tuple[int, int], col: int, row: int) -> tuple[int, int, int, int]:
    """Original pixels covered by dataset tile `<scene>_<col>_<row>`: the scene was resized to SHORT_SIDE,
    centre-cropped to a square and cut into a 4x4 grid of TILE."""
    scale = SHORT_SIDE / min(scene_size)
    width, height = (round(side * scale) for side in scene_size)
    left = (width - SHORT_SIDE) // 2 + col * TILE
    top = (height - SHORT_SIDE) // 2 + row * TILE
    return tuple(round(edge / scale) for edge in (left, top, left + TILE, top + TILE))


def resized(scene: Image.Image) -> Image.Image:
    """Native resolution beat dataset scale in eval (hillclimb.md); only scenes below dataset scale are scaled up."""
    scale = max(1.0, SHORT_SIDE / min(scene.size))
    return scene.convert("RGB").resize(
        (round(scene.width * scale), round(scene.height * scale)), Image.Resampling.LANCZOS
    )


def slice_scene(scene: Image.Image) -> tuple[tuple[int, int], list[tuple[Tile, Image.Image]]]:
    """The resized scene's size, and each tile with its pixels."""
    scaled = resized(scene)
    return scaled.size, [
        (t, scaled.crop((t.x, t.y, t.x + TILE, t.y + TILE))) for t in tiles(*scaled.size)
    ]
