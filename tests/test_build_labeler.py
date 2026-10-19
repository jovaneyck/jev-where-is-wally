from build_labeler import guesses


def tile(presence: float, left: float) -> dict:
    return {"presence": presence, "box": {"left": left, "top": 0.2, "right": left + 0.05, "bottom": 0.3}}


SCENES = {
    "Wheres-Waldo-Toys.jpg": {"size": [2000, 1000], "tiles": [tile(0.3, 0.1), tile(0.8, 0.5), tile(0.6, 0.7)]},
    "Wheres-Waldo-Beach.jpg": {"size": [2000, 1000], "tiles": [tile(0.4, 0.1)]},
}


def test_top_tiles_become_guesses_most_likely_first():
    assert guesses(SCENES, [], top=2)["Wheres-Waldo-Toys.jpg"] == [
        {"source": "presence 0.80", "box": tile(0.8, 0.5)["box"]},
        {"source": "presence 0.60", "box": tile(0.6, 0.7)["box"]},
    ]


def test_a_waldo_probe_becomes_a_fixed_size_box_around_its_centre():
    probes = [("Toys", 0.5, 0.5, True, "Waldo among toys")]
    assert guesses(SCENES, probes, top=0, size=(40, 80))["Wheres-Waldo-Toys.jpg"] == [
        {"source": "eye: Waldo among toys", "box": {"left": 0.49, "top": 0.46, "right": 0.51, "bottom": 0.54}}
    ]


def test_lookalike_probes_are_not_guesses():
    probes = [("Beach", 0.5, 0.5, False, "Wenda")]
    assert guesses(SCENES, probes, top=0)["Wheres-Waldo-Beach.jpg"] == []
