from PIL import Image

from waldo.report import Entry, draw_box, render
from waldo.slicing import Box
from waldo.solver import Solution

BOX = Box(left=0.25, top=0.5, right=0.5, bottom=0.75)


def entry(found: bool) -> Entry:
    return Entry(name="1.jpg", image="solution/1.jpg", size=(2000, 1000), solution=Solution(found, 0.62, BOX))


def test_found_shows_label_presence_and_pixel_box():
    html = render([entry(found=True)])
    assert "Waldo" in html and "No Waldo" not in html
    assert "0.62" in html
    assert "left 500, top 500, right 1000, bottom 750" in html
    assert 'src="solution/1.jpg"' in html


def test_not_found_is_labelled_no_waldo():
    assert "No Waldo" in render([entry(found=False)])


def test_draw_box_outlines_the_box_on_the_image():
    drawn = draw_box(Image.new("RGB", (100, 100), "white"), BOX)
    assert drawn.getpixel((25, 60)) != (255, 255, 255)
    assert drawn.getpixel((5, 5)) == (255, 255, 255)
