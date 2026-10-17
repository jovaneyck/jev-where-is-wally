from collections import defaultdict
from dataclasses import dataclass
from itertools import product


@dataclass(frozen=True)
class Scored:
    scene: str
    is_waldo: bool
    score: float


def auc(tiles: list[Scored]) -> float:
    """Probability that a random Waldo tile outscores a random non-Waldo tile."""
    positives = [t.score for t in tiles if t.is_waldo]
    negatives = [t.score for t in tiles if not t.is_waldo]
    wins = sum(1.0 if p > n else 0.5 if p == n else 0.0 for p, n in product(positives, negatives))
    return wins / (len(positives) * len(negatives))


def scene_hit_rate(tiles: list[Scored]) -> float:
    """Fraction of scenes containing Waldo whose top-scoring tile contains Waldo."""
    scenes: dict[str, list[Scored]] = defaultdict(list)
    for tile in tiles:
        scenes[tile.scene].append(tile)
    with_waldo = [s for s in scenes.values() if any(t.is_waldo for t in s)]
    hits = sum(max(s, key=lambda t: t.score).is_waldo for s in with_waldo)
    return hits / len(with_waldo)
