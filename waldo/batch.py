"""Several tiles in one Jev request: each crop gets the shipped tile questions, pointed at it."""

from types import SimpleNamespace

from PIL import Image as PilImage
from typesafe_sdk import AsyncTypeSafeClient, Image

from waldo import jev
from waldo.slicing import TILE

SIDE = TILE * jev.UPSCALE
GROUP = 4  # crops at SIDE per request; 6 exceed max_tokens


def prepare(crop: PilImage.Image, side: int = SIDE) -> PilImage.Image:
    return crop.resize((side, side), PilImage.Resampling.LANCZOS)


def request(crops: list[PilImage.Image], side: int = SIDE) -> tuple[dict, dict]:
    keys = [f"c{i}" for i in range(1, len(crops) + 1)]
    tile_state, _ = jev.request(crops[0])
    state = {
        "waldo": tile_state["waldo"],
        "not_waldo": tile_state["not_waldo"],
        "crops": {key: Image.from_pil(prepare(crop, side)) for key, crop in zip(keys, crops)},
    }
    questions = {
        f"{key}.{name}": type(question)(instructions=question.instructions.replace("`scene`", f"`crops.{key}`"))
        for key in keys
        for name, question in jev.questions().items()
    }
    return state, questions


def read(result, count: int) -> list[jev.TileAnswer]:
    """One tile answer per crop, in request order."""

    def own(answers: dict, key: str) -> dict:
        return {name.removeprefix(f"{key}."): answer for name, answer in answers.items() if name.startswith(f"{key}.")}

    keys = [f"c{i}" for i in range(1, count + 1)]
    return [jev.read(SimpleNamespace(answers=own(result.answers, k), boxes=own(result.boxes, k))) for k in keys]


async def ask(client: AsyncTypeSafeClient, crops: list[PilImage.Image], side: int = SIDE) -> list[jev.TileAnswer]:
    state, questions = request(crops, side)
    return read(await client.system_one(state=state, questions=questions, model=jev.MODEL, extra_headers=jev.HEADERS), len(crops))
