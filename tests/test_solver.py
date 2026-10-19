from waldo.jev import TileAnswer
from waldo.slicing import Box, Tile
from waldo.solver import Solution, pick, shortlist

TILE_BOX = Box(left=0, top=0, right=1, bottom=1)


def answer(presence: float) -> TileAnswer:
    return TileAnswer(presence=presence, nouls={}, box=TILE_BOX, box_confidence=0.5)


def test_picks_the_most_likely_frame_and_maps_its_box_to_the_scene():
    solution = pick([((0, 0, 256, 256), answer(0.3)), ((256, 0, 512, 256), answer(0.8))], (512, 256))
    assert solution == Solution(found=True, presence=0.8, box=Box(left=0.5, top=0, right=1, bottom=1))


def test_found_at_threshold():
    assert pick([((0, 0, 256, 256), answer(0.5))], (256, 256)).found


def test_not_found_below_threshold():
    assert not pick([((0, 0, 256, 256), answer(0.49))], (256, 256)).found


class TestShortlist:
    def test_keeps_the_most_likely_tiles(self):
        answers = [(Tile(0, 0), answer(0.1)), (Tile(256, 0), answer(0.9)), (Tile(512, 0), answer(0.5))]
        assert [tile for tile, _ in shortlist(answers, k=2)] == [Tile(256, 0), Tile(512, 0)]

    def test_orders_them_by_position_not_by_presence(self):
        answers = [(Tile(256, 256), answer(0.9)), (Tile(512, 0), answer(0.7)), (Tile(0, 256), answer(0.8))]
        assert [tile for tile, _ in shortlist(answers, k=3)] == [Tile(512, 0), Tile(0, 256), Tile(256, 256)]
