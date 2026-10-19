from waldo.candidates import crop_box, zoom_frame
from waldo.slicing import Box


class TestCropBox:
    """Square crop around a pixel box, `pad` times its longest side, at least `minimum`, inside the scene."""

    def test_large_box_is_padded_around_its_centre(self):
        assert crop_box((2000, 2000), (900, 900, 1100, 1100), pad=3, minimum=100) == (700, 700, 1300, 1300)

    def test_oblong_box_is_squared_on_its_longest_side(self):
        assert crop_box((2000, 2000), (950, 900, 1050, 1100), pad=3, minimum=100) == (700, 700, 1300, 1300)

    def test_small_box_gets_the_minimum_side(self):
        assert crop_box((2000, 2000), (990, 990, 1010, 1010), pad=3, minimum=256) == (872, 872, 1128, 1128)

    def test_crop_past_an_edge_is_shifted_inside(self):
        assert crop_box((2000, 2000), (0, 1900, 100, 2000), pad=3, minimum=100) == (0, 1700, 300, 2000)

    def test_crop_never_exceeds_the_scene_short_side(self):
        assert crop_box((800, 400), (300, 100, 500, 300), pad=3, minimum=100) == (200, 0, 600, 400)


def test_zoom_frame_crops_around_a_scene_fraction_box_at_the_zoom_minimum():
    box = Box(left=0.5, top=0.5, right=0.51, bottom=0.52)  # 20x20 px in a 2000x1000 scene
    assert zoom_frame(box, (2000, 1000)) == (946, 446, 1074, 574)
