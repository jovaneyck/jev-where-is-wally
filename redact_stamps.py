"""Black out Waldo's portraits on stamps, seals and character lineups, so the solver can't find him there.

Run:
    uv run redact_stamps.py
    Untouched scenes are kept in a sibling `<folder>-unredacted/`; redaction always starts from those,
    so rerunning is safe. Restore by copying them back.
"""

import shutil
from pathlib import Path

from PIL import Image, ImageDraw

REDACTIONS = {  # folder -> scene -> rectangles in original pixels: left, top, right, bottom
    Path("data/wheres-waldo/Hey-Waldo/original-images"): {
        "8.jpg": [(590, 105, 740, 270)],
        "10.jpg": [(410, 62, 502, 172)],
        "16.jpg": [(390, 42, 506, 170)],
    },
    Path("data/hi-res"): {
        "Wheres-Waldo-Food-Court-Super-High-Resolution-scaled.jpg": [(140, 980, 630, 1375)],
        "Wheres-Waldo-GIANTS-Super-High-Resolution-scaled-e1737404380369.jpg": [(530, 145, 655, 275)],
        "Wheres-Waldo-Ocean-Super-High-Resolution-scaled-e1737403627172.jpg": [(565, 160, 690, 285)],
        "Wheres-Waldo-Underground-Super-High-Resolution-scaled.jpg": [(545, 165, 670, 300)],
    },
}


def redact(folder: Path, scenes: dict[str, list[tuple[int, int, int, int]]]) -> None:
    unredacted = folder.with_name(f"{folder.name}-unredacted")
    if not unredacted.exists():
        shutil.copytree(folder, unredacted)
    for name, rectangles in scenes.items():
        scene = Image.open(unredacted / name).convert("RGB")
        for rectangle in rectangles:
            ImageDraw.Draw(scene).rectangle(rectangle, fill="black")
        scene.save(folder / name, quality=95)
        print(f"redacted {folder / name} {rectangles}")


if __name__ == "__main__":
    for folder, scenes in REDACTIONS.items():
        redact(folder, scenes)
