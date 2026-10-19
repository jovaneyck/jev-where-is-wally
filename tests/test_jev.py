from types import SimpleNamespace

from PIL import Image

from waldo.jev import TileAnswer, prepare, read, request
from waldo.slicing import Box


def noul(value: float):
    return SimpleNamespace(type="noul", noul=value)


def box_answer(confidence: float):
    edges = SimpleNamespace(left=0.1, top=0.2, right=0.3, bottom=0.4)
    return SimpleNamespace(type="box", box=edges, confidence=confidence)


def test_prepare_upscales_tile_six_times():
    assert prepare(Image.new("RGB", (256, 256))).size == (1536, 1536)


def test_request_asks_four_presence_phrasings_and_a_box():
    _, questions = request(Image.new("RGB", (256, 256)))
    assert sorted(questions) == ["box", "present", "present_face", "present_glasses", "present_outfit"]


def test_read_averages_presence_nouls_and_keeps_the_box():
    box = box_answer(0.7)
    result = SimpleNamespace(
        answers={"present": noul(0.2), "present_face": noul(0.6), "box": box},
        boxes={"box": box},
    )
    assert read(result) == TileAnswer(
        presence=0.4,
        nouls={"present": 0.2, "present_face": 0.6},
        box=Box(left=0.1, top=0.2, right=0.3, bottom=0.4),
        box_confidence=0.7,
    )


def test_read_keeps_other_nouls_out_of_presence():
    box = box_answer(0.7)
    result = SimpleNamespace(
        answers={"present": noul(0.2), "present_face": noul(0.6), "lookalike_wenda": noul(0.9), "box": box},
        boxes={"box": box},
    )
    answer = read(result)
    assert answer.presence == 0.4
    assert answer.nouls["lookalike_wenda"] == 0.9


def test_request_shows_lookalikes_as_negative_references():
    state, _ = request(Image.new("RGB", (256, 256)))
    assert sorted(state["not_waldo"]) == ["waldo_watchers", "wenda"]


def test_request_without_negatives_leaves_them_out():
    state, _ = request(Image.new("RGB", (256, 256)), negatives=False)
    assert "not_waldo" not in state
