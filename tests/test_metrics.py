from waldo.metrics import Scored, auc, scene_hit_rate


def scored(scene: str, is_waldo: bool, score: float) -> Scored:
    return Scored(scene=scene, is_waldo=is_waldo, score=score)


class TestAuc:
    def test_perfect_separation_is_one(self):
        assert auc([scored("1", True, 0.9), scored("1", False, 0.1)]) == 1.0

    def test_inverted_separation_is_zero(self):
        assert auc([scored("1", True, 0.1), scored("1", False, 0.9)]) == 0.0

    def test_ties_count_half(self):
        assert auc([scored("1", True, 0.5), scored("1", False, 0.5)]) == 0.5

    def test_partial_overlap(self):
        tiles = [
            scored("1", True, 0.8),
            scored("1", True, 0.3),
            scored("1", False, 0.5),
            scored("1", False, 0.1),
        ]
        assert auc(tiles) == 0.75


class TestSceneHitRate:
    def test_hit_when_top_tile_is_waldo(self):
        assert scene_hit_rate([scored("1", True, 0.9), scored("1", False, 0.1)]) == 1.0

    def test_miss_when_top_tile_is_not_waldo(self):
        assert scene_hit_rate([scored("1", True, 0.1), scored("1", False, 0.9)]) == 0.0

    def test_any_waldo_tile_on_top_is_a_hit(self):
        tiles = [scored("1", False, 0.5), scored("1", True, 0.9), scored("1", True, 0.2)]
        assert scene_hit_rate(tiles) == 1.0

    def test_averages_over_scenes(self):
        tiles = [
            scored("1", True, 0.9),
            scored("1", False, 0.1),
            scored("2", True, 0.1),
            scored("2", False, 0.9),
        ]
        assert scene_hit_rate(tiles) == 0.5

    def test_ignores_scenes_without_waldo(self):
        tiles = [scored("1", True, 0.9), scored("1", False, 0.1), scored("2", False, 0.9)]
        assert scene_hit_rate(tiles) == 1.0
