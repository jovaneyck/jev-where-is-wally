from waldo.jev import TileAnswer
from waldo.slicing import Box, Tile
from waldo.solver import Solution, pick

TILE_BOX = Box(left=0, top=0, right=1, bottom=1)


def answer(presence: float) -> TileAnswer:
    return TileAnswer(presence=presence, nouls={}, box=TILE_BOX, box_confidence=0.5)


def test_picks_the_most_likely_tile_and_maps_its_box_to_the_scene():
    solution = pick([(Tile(0, 0), answer(0.3)), (Tile(256, 0), answer(0.8))], (512, 256))
    assert solution == Solution(found=True, presence=0.8, box=Box(left=0.5, top=0, right=1, bottom=1))


def test_found_at_threshold():
    assert pick([(Tile(0, 0), answer(0.5))], (256, 256)).found


def test_not_found_below_threshold():
    assert not pick([(Tile(0, 0), answer(0.49))], (256, 256)).found
