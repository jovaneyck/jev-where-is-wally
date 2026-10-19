"""Crops around pass-1 boxes, re-scored in pass 2 (hillclimb.md)."""

from waldo.slicing import Box

PAD = 3  # crop side in box sides: the box plus one box of context on each side
MINIMUM = 256  # scene pixels; boxes on non-Waldo tiles can be tiny


def crop_box(
    scene_size: tuple[int, int], box: tuple[int, int, int, int], pad: float = PAD, minimum: int = MINIMUM
) -> tuple[int, int, int, int]:
    """Square crop centred on `box` (pixels), shifted to stay inside the scene."""
    left, top, right, bottom = box
    side = round(min(max(pad * max(right - left, bottom - top), minimum), *scene_size))

    def start(low: int, high: int, length: int) -> int:
        return min(max(round((low + high - side) / 2), 0), length - side)

    x, y = start(left, right, scene_size[0]), start(top, bottom, scene_size[1])
    return x, y, x + side, y + side


ZOOM = 128  # scene pixels; zoom crops of 64-128px rank Waldo best on hi-res (hillclimb.md)


def zoom_frame(box: Box, scene_size: tuple[int, int], minimum: int = ZOOM) -> tuple[int, int, int, int]:
    """Square pixel crop around a box given as scene fractions."""
    width, height = scene_size
    pixels = (round(box.left * width), round(box.top * height), round(box.right * width), round(box.bottom * height))
    return crop_box(scene_size, pixels, minimum=minimum)
