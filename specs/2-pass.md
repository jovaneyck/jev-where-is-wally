# Two-pass solver: re-rank the top-K tiles with a Choice

> **Status: measured, not shipped.** Steps 1–3 are implemented. No config beat pass 1 (15/17), so step 4 was skipped. The results are in `hillclimb.md`, under "Two-pass re-ranking".

## Why

The first pass (the shipped solver) scores every tile on its own and picks the one with the highest presence. On the labelled eval the right region is often not first, but it is almost always in the top 3. Cached `native_negrefs` runs, scene 1 excluded:

| Waldo's region ranked within | Run 1 | Run 2 |
|---|---|---|
| top 1 (what ships today) | 15 / 17 | 15 / 17 |
| top 3 | 17 / 17 | 17 / 17 |
| top 10 | 17 / 17 | 17 / 17 |

A second pass that compares the top candidates side by side can fix rank-2 and rank-3 misses. A Choice whose options are images is supported, and "search a large image: tiles as Choice options" is a documented pattern (`docs.typesafe.ai/images`, Patterns).

## Current state (context for after compaction)

- **Shipped request** (`waldo/jev.py`, `request`):
  - Each 256px tile is upscaled 6× to 1536px.
  - `state` holds `scene`, `waldo` (`{description, picture: assets/waldo-ref-1_1_1.png}`) and `not_waldo` (`{wenda, waldo_watchers}` pictures).
  - Questions: four presence Nouls (`present*`, averaged into presence) plus a `box` question.
  - Model `jev-preview`, header `TypeSafe-Danger-Zone-Images: true`.
- **Slicing** (`waldo/slicing.py`): native resolution. Scenes are never shrunk; only scenes with a short side under 1024 are scaled up to it. Tiles are 256px, with the last row and column aligned to the edge. `to_scene` maps tile boxes back to scene fractions.
- **Solver** (`waldo/solver.py`): `pick` takes the tile with the highest presence; `THRESHOLD = 0.5`. `solve.py [folder]` (default `data/hi-res`) writes `out/solution.html` and `out/solution.json`.
- **Eval** (`eval_tiles.py`):
  - Runs over 317 labelled 256px dataset tiles, cached per run in `out/runs/<variant>[#n].jsonl`.
  - Native variants map each labelled tile to its region in `original-images-unredacted/` (`SCENE_ORIGINALS`, `slicing.dataset_region`), cut into up to 4 native sub-tiles. Rows store `subtiles`.
  - Metrics (`waldo/metrics.py`): AUC, plus scene hit rate (does the top tile per scene contain Waldo?).
  - The shipped config is `native_negrefs`: AUC 0.929 / 0.928, hit rate 0.882 (15/17).
- **Probe** (`probe_lookalikes.py`): 9 Waldos and 5 lookalikes verified by eye on hi-res; shipped probe AUC 0.911.
- **Data quirks:**
  - Tile scene ids ≠ original file names.
  - Scenes 2/5 and 3/6 are duplicates.
  - Scene 1 is excluded (the reference picture comes from it).
  - Hi-res scenes have **no ground truth**; there, results can only be checked by eye.
- **Ops:** concurrency 8, because the API returns 529 (overloaded) at 16. `API_KEY` lives in `.env`.

## Design

1. **Pass 1** is unchanged: score all tiles and keep the top K by presence.
2. **Candidates:** for each top-K tile, crop around its box in scene pixels. Pad by about 2× the box size, keep it square, clamp it to the scene, and upscale so the short side is at least 280px (the API minimum). Cap each crop at 1568px.
3. **Pass 2:** one request per scene.
   - `state`: `waldo` and `not_waldo` exactly as in pass 1.
   - Question: a Choice, "Which picture shows Waldo, as in `waldo`, and not Wenda or a Waldo-watcher from `not_waldo`?"
   - Criteria: `{"c1": <crop1>, …, "cK": <cropK>, "none": "None of the pictures shows Waldo."}`. Option keys are text; the crop references go in the option values, because object keys are never replaced by images.
4. **Position bias:** Choice leans toward the first option (jev-1.13 jaggedness doc).
   - Ask twice, once in rank order and once reversed, and average the probabilities per candidate.
   - When the two orders disagree on the winner, flag the answer as low confidence.
5. **Decision:** the winner is the candidate with the highest averaged probability. If `none` wins, fall back to the pass-1 top tile; this rule will be measured. The box comes from the winning candidate's pass-1 tile, through `to_scene`.

## Measurement (measure, don't guess)

1. **Labelled eval, offline pass 1.** Take the top-K regions per scene from cached `native_negrefs` rows, using the best sub-tile and its box. Only pass 2 costs requests: about 2 per scene, 17 scenes.
   - **Metric:** scene hit rate. The pick is a hit when its region is Waldo-labelled.
   - **Success:** fixes misses (at most 2 available) and breaks none of the 15 hits. Repeat each config twice; hit rate is noisy.
   - **Sweep:** K = 3, 5, 10. More candidates also means more lookalikes.
   - **Also record** how often `none` wins, and how often the two orders disagree.
2. **Probe-style check (optional).** Pass 2 with only verified hi-res candidates (Waldo plus Wenda or a watcher from the same scene, where known). Does it pick Waldo?
3. **Hi-res end to end.** Run `solve.py` with pass 2 and check the 10 picks by eye. Previous by-eye result: 5 correct, 2 wrong (Beach picked Wenda, Film Set a watcher), 3 unsure. For hi-res, K should be about 10, since each scene has about 70 tiles against about 15 labelled regions.

## Risks and limits

- **Small signal.** The eval can show at most 2 fixed scenes. Hi-res needs eyeballing, or ground truth from the user.
- **Request size.** Ten images plus references in one request may exceed the context length (error `400 max_tokens_exceeded`). If so, shrink the crops or run a tournament: groups of 5, then a final.
- **Coarse labels.** A region-level hit can still have its box on a lookalike within that region.
- **Cost.** Pass 2 adds 2 requests per scene, negligible next to pass 1 (about 70 tiles per hi-res scene).

## Implementation steps (TDD, tiny steps)

1. `waldo/candidates.py`: `crop_box(scene_size, box, pad) -> pixel rectangle`. Pure geometry; unit-test padding, squaring, clamping and the minimum size.
2. `waldo/rerank.py`:
   - `choice_request(candidates, order) -> (state, questions)`: test the option keys, the `none` option, and the order.
   - `combine(prob_forward, prob_reversed) -> winner, agreement`: pure; test the averaging and the disagreement flag.
3. **Eval:** a `rerank_eval.py` (or a mode in `eval_tiles.py`) that reads the cached `native_negrefs` rows, runs pass 2, caches answers to `out/rerank/<config>.jsonl`, and reports hit rate per K.
4. **Solver:** ship only if the eval holds up. `solve` keeps all tile answers, takes the top K and runs pass 2. `pick` stays as the fallback.
5. Record the results in `hillclimb.md`.
