from waldo.slicing import Box, Tile, offsets, tiles, to_scene


class TestOffsets:
    def test_length_of_one_tile_gives_one_offset(self):
        assert offsets(256) == [0]

    def test_exact_multiple_tiles_without_overlap(self):
        assert offsets(1024) == [0, 256, 512, 768]

    def test_remainder_adds_a_last_tile_aligned_to_the_edge(self):
        assert offsets(1676) == [0, 256, 512, 768, 1024, 1280, 1420]


def test_tiles_cover_both_axes():
    assert tiles(512, 256) == [Tile(0, 0), Tile(256, 0)]


class TestToScene:
    def test_full_tile_at_origin_maps_to_tile_area(self):
        assert to_scene(Box(left=0, top=0, right=1, bottom=1), Tile(0, 0), (1024, 512)) == Box(
            left=0, top=0, right=0.25, bottom=0.5
        )

    def test_offset_tile_shifts_box(self):
        assert to_scene(Box(left=0.5, top=0.25, right=0.75, bottom=0.5), Tile(512, 256), (1024, 512)) == Box(
            left=0.625, top=0.625, right=0.6875, bottom=0.75
        )
