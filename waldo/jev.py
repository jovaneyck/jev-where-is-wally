"""The hill-climb's best Jev request for a 256px tile (`x6_phrasings` in hillclimb.md)."""

from dataclasses import dataclass
from pathlib import Path

from PIL import Image as PilImage
from typesafe_sdk import AsyncTypeSafeClient, Box, Image, Noul

from waldo import slicing

MODEL = "jev-preview"
HEADERS = {"TypeSafe-Danger-Zone-Images": "true"}
UPSCALE = 6
WALDO = "red-and-white striped shirt and bobble hat, round glasses"
ASSETS = Path(__file__).parent.parent / "assets"
REFERENCE = Image(ASSETS / "waldo-ref-1_1_1.png")
# Lookalikes from the unredacted hi-res Food Court lineup; showing them lifts eval and probe AUC (hillclimb.md)
NOT_WALDO = {"wenda": Image(ASSETS / "wenda-ref.png"), "waldo_watchers": Image(ASSETS / "watchers-ref.png")}


@dataclass(frozen=True)
class TileAnswer:
    presence: float
    nouls: dict[str, float]
    box: slicing.Box
    box_confidence: float


def prepare(tile: PilImage.Image) -> PilImage.Image:
    return tile.resize((tile.width * UPSCALE, tile.height * UPSCALE), PilImage.Resampling.LANCZOS)


def questions(present_criteria=None) -> dict:
    """Differently worded presence questions, averaged into one signal, plus where Waldo is."""
    return {
        "present": Noul(instructions="Is Waldo, as shown in `waldo`, in `scene`?", criteria=present_criteria),
        "present_face": Noul(instructions="Does `scene` show the face of the person in `waldo.picture`?"),
        "present_outfit": Noul(
            instructions="Is someone in `scene` wearing the exact outfit from `waldo`: "
            "red-and-white striped shirt and matching bobble hat?"
        ),
        "present_glasses": Noul(instructions="Does anyone in `scene` have Waldo's round glasses and dark hair?"),
        "box": Box(instructions="Waldo, as shown in `waldo`, in `scene`"),
    }


def request(tile: PilImage.Image, present_criteria=None, negatives: bool = True) -> tuple[dict, dict]:
    state = {"scene": Image.from_pil(prepare(tile)), "waldo": {"description": WALDO, "picture": REFERENCE}}
    if negatives:
        state["not_waldo"] = dict(NOT_WALDO)
    return state, questions(present_criteria)


def read(result) -> TileAnswer:
    nouls = {name: answer.noul for name, answer in result.answers.items() if answer.type == "noul"}
    presences = [value for name, value in nouls.items() if name.startswith("present")]
    box = result.boxes["box"]
    return TileAnswer(
        presence=sum(presences) / len(presences),
        nouls=nouls,
        box=slicing.Box(left=box.box.left, top=box.box.top, right=box.box.right, bottom=box.box.bottom),
        box_confidence=box.confidence,
    )


async def ask(client: AsyncTypeSafeClient, tile: PilImage.Image) -> TileAnswer:
    state, asked = request(tile)
    return read(await client.system_one(state=state, questions=asked, model=MODEL, extra_headers=HEADERS))
