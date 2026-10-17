from dataclasses import dataclass
from html import escape

from PIL import Image, ImageDraw

from waldo.slicing import Box
from waldo.solver import Solution


@dataclass(frozen=True)
class Entry:
    name: str
    image: str  # path of the drawn image, relative to the html page
    size: tuple[int, int]  # original pixels
    solution: Solution


def pixels(box: Box, size: tuple[int, int]) -> tuple[int, int, int, int]:
    width, height = size
    return round(box.left * width), round(box.top * height), round(box.right * width), round(box.bottom * height)


def draw_box(image: Image.Image, box: Box) -> Image.Image:
    drawn = image.convert("RGB")
    ImageDraw.Draw(drawn).rectangle(pixels(box, drawn.size), outline="lime", width=max(3, drawn.width // 400))
    return drawn


def _card(entry: Entry) -> str:
    s = entry.solution
    left, top, right, bottom = pixels(s.box, entry.size)
    label = "Waldo" if s.found else "No Waldo"
    return f"""
<section class="card">
  <h2>{escape(entry.name)} <span class="label {'found' if s.found else 'missing'}">{label}</span></h2>
  <p>presence {s.presence:.2f} · box (px) left {left}, top {top}, right {right}, bottom {bottom}
     · box (fraction) {s.box.left:.3f}, {s.box.top:.3f}, {s.box.right:.3f}, {s.box.bottom:.3f}</p>
  <a href="{escape(entry.image)}"><img src="{escape(entry.image)}" alt="{escape(entry.name)} with Waldo's box"></a>
</section>"""


def render(entries: list[Entry]) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Where's Waldo</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 0 auto; padding: 16px; max-width: 1200px; background: #fafafa; color: #222; }}
  .card {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 12px 16px; margin-bottom: 24px; }}
  h2 {{ margin: 0 0 4px; font-size: 1.1rem; }}
  p {{ margin: 0 0 8px; font-size: 0.9rem; color: #555; }}
  img {{ max-width: 100%; height: auto; display: block; }}
  .label {{ font-size: 0.8rem; padding: 2px 8px; border-radius: 999px; margin-left: 8px; }}
  .found {{ background: #d1fadf; color: #05603a; }}
  .missing {{ background: #fee4e2; color: #912018; }}
</style>
</head>
<body>
<h1>Where's Waldo</h1>
{''.join(_card(e) for e in entries)}
</body>
</html>
"""
