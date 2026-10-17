from PIL import Image

from waldo.slicing import Box, Tile, dataset_region, offsets, slice_scene, tiles, to_scene


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


class TestDatasetRegion:
    """Dataset tiles: scene resized to short side 1024, centre-cropped to 1024x1024, 4x4 grid."""

    def test_landscape_at_dataset_scale_is_offset_by_the_centre_crop(self):
        assert dataset_region((2048, 1024), col=1, row=0) == (768, 0, 1024, 256)

    def test_larger_scene_scales_the_region_up(self):
        assert dataset_region((4096, 2048), col=0, row=1) == (1024, 512, 1536, 1024)

    def test_portrait_is_cropped_vertically(self):
        assert dataset_region((1024, 2048), col=0, row=0) == (0, 512, 256, 768)


class TestSliceScene:
    def test_scene_above_dataset_scale_is_sliced_at_native_resolution(self):
        size, _ = slice_scene(Image.new("RGB", (2000, 1600)))
        assert size == (2000, 1600)

    def test_scene_below_dataset_scale_is_upscaled_to_it(self):
        size, _ = slice_scene(Image.new("RGB", (1000, 800)))
        assert size == (1280, 1024)
