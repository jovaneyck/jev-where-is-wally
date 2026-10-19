from PIL import Image
from typesafe_sdk import Image as Asset

from waldo.rerank import CROP_SIDE, NONE, choice_request, combine, prepare


def crops(count: int) -> list[Image.Image]:
    return [Image.new("RGB", (100, 100)) for _ in range(count)]


class TestChoiceRequest:
    def test_options_are_candidates_by_rank_plus_none(self):
        _, questions = choice_request(crops(3), reverse=False)
        assert list(questions["waldo"].criteria) == ["c1", "c2", "c3", NONE]

    def test_reversed_order_presents_the_last_candidate_first_and_none_last(self):
        _, questions = choice_request(crops(3), reverse=True)
        assert list(questions["waldo"].criteria) == ["c3", "c2", "c1", NONE]

    def test_state_shows_waldo_and_the_lookalikes(self):
        state, _ = choice_request(crops(1), reverse=False)
        assert sorted(state) == ["not_waldo", "waldo"]

    def test_candidates_are_shown_as_images(self):
        _, questions = choice_request(crops(1), reverse=False)
        assert isinstance(questions["waldo"].criteria["c1"], Asset)


def test_prepare_resizes_a_crop_to_a_fixed_side():
    assert prepare(Image.new("RGB", (300, 300))).size == (CROP_SIDE, CROP_SIDE)


def test_prepare_takes_another_side():
    assert prepare(Image.new("RGB", (300, 300)), side=1024).size == (1024, 1024)


class TestCombine:
    def test_winner_has_the_highest_averaged_probability(self):
        forward = {"c1": 0.6, "c2": 0.4, NONE: 0.0}
        backward = {"c1": 0.1, "c2": 0.8, NONE: 0.1}
        assert combine(forward, backward) == ("c2", False)

    def test_orders_agreeing_on_the_winner_are_flagged(self):
        forward = {"c1": 0.7, "c2": 0.3, NONE: 0.0}
        backward = {"c1": 0.6, "c2": 0.4, NONE: 0.0}
        assert combine(forward, backward) == ("c1", True)
