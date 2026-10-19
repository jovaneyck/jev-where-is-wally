"""Pass 2: show the top-K pass-1 candidates side by side and let one Choice pick Waldo (specs/2-pass.md)."""

from PIL import Image as PilImage
from typesafe_sdk import AsyncTypeSafeClient, Choice, Image

from waldo import jev

CROP_SIDE = 560  # 2x the API minimum; K crops share one request
NONE = "none"


def prepare(crop: PilImage.Image, side: int = CROP_SIDE) -> PilImage.Image:
    return crop.convert("RGB").resize((side, side), PilImage.Resampling.LANCZOS)


def choice_request(crops: list[PilImage.Image], reverse: bool, side: int = CROP_SIDE) -> tuple[dict, dict]:
    """Option `c<rank>` shows the crop of pass-1 rank `rank`; `reverse` counters Choice's first-option bias."""
    options = [(f"c{rank}", Image.from_pil(prepare(crop, side))) for rank, crop in enumerate(crops, start=1)]
    criteria = dict(reversed(options) if reverse else options)
    criteria[NONE] = "None of the pictures shows Waldo."
    state = {"waldo": {"description": jev.WALDO, "picture": jev.REFERENCE}, "not_waldo": dict(jev.NOT_WALDO)}
    question = Choice(
        instructions="Which picture shows Waldo, as in `waldo`, and not Wenda or a Waldo-watcher from `not_waldo`?",
        criteria=criteria,
    )
    return state, {"waldo": question}


def combine(forward: dict[str, float], backward: dict[str, float]) -> tuple[str, bool]:
    """Winner by averaged probability, and whether both orders picked it."""
    averaged = {option: (forward[option] + backward[option]) / 2 for option in forward}
    return max(averaged, key=averaged.get), max(forward, key=forward.get) == max(backward, key=backward.get)


async def ask(
    client: AsyncTypeSafeClient, crops: list[PilImage.Image], reverse: bool, side: int = CROP_SIDE
) -> dict[str, float]:
    state, questions = choice_request(crops, reverse, side)
    result = await client.system_one(state=state, questions=questions, model=jev.MODEL, extra_headers=jev.HEADERS)
    return result.choices["waldo"].probabilities
