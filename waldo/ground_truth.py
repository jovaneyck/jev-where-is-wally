"""Compare answers with hand-drawn Waldo boxes (data/hi-res/labels.json); all boxes are scene fractions."""

from waldo.slicing import Box


def contains_waldo(area: Box, label: Box) -> bool:
    """An area (e.g. a tile) contains Waldo when it holds the centre of his label."""
    x, y = (label.left + label.right) / 2, (label.top + label.bottom) / 2
    return area.left <= x <= area.right and area.top <= y <= area.bottom


def iou(a: Box, b: Box) -> float:
    width = max(0.0, min(a.right, b.right) - max(a.left, b.left))
    height = max(0.0, min(a.bottom, b.bottom) - max(a.top, b.top))
    overlap = width * height
    area = lambda box: (box.right - box.left) * (box.bottom - box.top)  # noqa: E731
    return overlap / (area(a) + area(b) - overlap)
