from waldo.ground_truth import contains_waldo, iou
from waldo.slicing import Box

LABEL = Box(left=0.4, top=0.4, right=0.6, bottom=0.6)


class TestContainsWaldo:
    def test_area_around_the_label_centre_contains_waldo(self):
        assert contains_waldo(Box(left=0.3, top=0.3, right=0.55, bottom=0.55), LABEL)

    def test_area_overlapping_the_label_but_not_its_centre_does_not(self):
        assert not contains_waldo(Box(left=0.0, top=0.0, right=0.45, bottom=0.45), LABEL)


class TestIou:
    def test_identical_boxes(self):
        assert iou(LABEL, LABEL) == 1

    def test_disjoint_boxes(self):
        assert iou(Box(left=0, top=0, right=0.1, bottom=0.1), LABEL) == 0

    def test_partial_overlap(self):
        assert iou(Box(left=0.5, top=0.4, right=0.7, bottom=0.6), LABEL) == 1 / 3
