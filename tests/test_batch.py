from types import SimpleNamespace

import pytest
from PIL import Image

from waldo.batch import prepare, read, request
from waldo.slicing import Box


def crops(count: int) -> list[Image.Image]:
    return [Image.new("RGB", (256, 256)) for _ in range(count)]


def test_every_crop_is_in_state_next_to_waldo_and_the_lookalikes():
    state, _ = request(crops(2))
    assert sorted(state) == ["crops", "not_waldo", "waldo"]
    assert sorted(state["crops"]) == ["c1", "c2"]


def test_every_crop_gets_the_tile_questions_pointed_at_it():
    _, questions = request(crops(2))
    assert questions["c2.present"].instructions == "Is Waldo, as shown in `waldo`, in `crops.c2`?"
    assert sorted(name for name in questions if name.startswith("c1.")) == [
        "c1.box", "c1.present", "c1.present_face", "c1.present_glasses", "c1.present_outfit"
    ]  # fmt: skip


def test_read_averages_each_crops_presence_nouls_and_keeps_its_box():
    def noul(value):
        return SimpleNamespace(type="noul", noul=value)

    def box(left):
        return SimpleNamespace(type="box", box=SimpleNamespace(left=left, top=0.2, right=0.3, bottom=0.4), confidence=0.9)

    answers = {"c1.present": noul(0.2), "c1.present_face": noul(0.4), "c2.present": noul(0.9), "c1.box": box(0.1), "c2.box": box(0.2)}
    result = SimpleNamespace(answers=answers, boxes={"c1.box": box(0.1), "c2.box": box(0.2)})
    first, second = read(result, 2)
    assert first.presence == pytest.approx(0.3)
    assert first.box == Box(left=0.1, top=0.2, right=0.3, bottom=0.4)
    assert second.presence == 0.9


def test_prepare_upscales_a_tile_like_the_shipped_request_by_default():
    assert prepare(Image.new("RGB", (256, 256))).size == (1536, 1536)


def test_prepare_takes_a_smaller_side_so_more_crops_fit_one_request():
    assert prepare(Image.new("RGB", (256, 256)), side=768).size == (768, 768)
