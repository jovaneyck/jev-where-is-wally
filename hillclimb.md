# Hill-climbing Jev on Waldo tiles

**Setup.** All 317 labelled 256px colour tiles (`data/wheres-waldo/Hey-Waldo/256`, 31 Waldo / 286 not-Waldo), model `jev-preview`. Reproduce with `uv run eval_tiles.py <variant>[#n] ...` (answers cached in `out/runs/`).

**Metrics** (`waldo/metrics.py`)
- **AUC**: chance a Waldo tile outscores a non-Waldo tile. Run-to-run noise ±0.01, so this is the climbing metric.
- **Scene hit rate**: fraction of scenes whose top-scoring tile contains Waldo; this is what the solver needs. 17 scenes, so one scene is 0.059, and identical runs swing it by up to 0.12.
- Scene 1 is excluded from every score because the reference picture is cropped from it.

## Results

| Step | AUC | Scene hit rate | Verdict |
|---|---|---|---|
| Text description only (baseline) | 0.749 | 0.353 | |
| + reference picture of Waldo in `state` | 0.82–0.83 | 0.47–0.59 | kept |
| + tile upscaled 6× to 1536px (was 2×) | 0.86–0.87 | 0.706 | kept |
| + four different phrasings, nouls averaged | **0.901 / 0.904** | **0.824** | kept, best (`x6_phrasings`) |
| Upscale 4× | 0.80–0.81 | 0.59 | worse than 2× |
| NEAREST instead of LANCZOS upscaling | 0.751 | 0.588 | worse |
| Noul criteria ruling out lookalikes | ±0 | ±0 | no gain |
| Repeating the same prompt and averaging | ±0 | ±0 | wasted calls |
| Box confidence as the score | 0.80–0.82 | 0.41–0.53 | the Noul is better |

## Learnings

- **Questions don't share instructions.** Put the Waldo description and picture in `state` once and refer to them as `` `waldo` `` from every question.
- **Showing beats describing.** A reference picture is the biggest single gain.
- **More pixels help**, but only at 6×; 4× was worse than 2×. Don't extrapolate.
- **Vary the phrasing, don't repeat it.** Four wordings score 0.84–0.88 alone and 0.90 averaged; repeating one prompt reproduces the same errors.
- **Use the Box for location, not presence.** Its confidence looked like the best signal on 6 tiles and lost clearly at 317.
- **Misses are near-misses.** In scenes 4, 16 and 17 the Waldo tile ranks 3rd to 5th, with margins around 0.03–0.05.

## Caveats

- Tiles 12_0_0, 13_0_0 and 21_0_0 show Waldo's portrait on a postage stamp, and 9_0_2 is a character lineup. These are easy wins that inflate the scores.
- Box placement is only eyeballed (`out/contact_x6_phrasings.jpg`). There are no ground-truth boxes.
- Several variants were tried on the same 17 scenes, so expect lower numbers on new pictures.

## Solver (`uv run solve.py` → `out/solution.html`)

- **How the dataset was tiled.** Template matching shows the scene is resized to a short side of 1024 and centre-cropped to 1024×1024, then cut into a 4×4 grid of 256px tiles named `scene_col_row` (not row first). The tiles cover only the central square, which is why scenes 8, 15 and 20 have no Waldo tile.
- **How the solver tiles.** It slices the *whole* scene at that same scale, aligning the last row and column to the edge, asks the `x6_phrasings` request for each tile, takes the tile with the highest presence, and converts its box back to the scene.
- **First run, by eyeball:** Waldo found in 14 of 19 scenes; 2 more boxes are on Waldo's postage-stamp portrait (scenes 10 and 16); 3 misses (9, 11, 13).
- **The label doesn't discriminate.** Every scene's best tile scores at least 0.5, so every scene is labelled "Waldo". All originals contain Waldo, so "No Waldo" can't be validated.

## Native-resolution slicing (shipped)

- **The eval data was mis-mapped.** Tile scene ids don't match original file names; the mapping in `eval_tiles.py` was found by template matching. Tile scenes 2 and 5 are both `17.jpg`, and 3 and 6 are both `18.jpg`, so two pictures count double in every score.
- **The `native_x6_phrasings` variant.** Each labelled tile's region is cut from the unredacted original at native resolution into up to four 256px sub-tiles, and the region scores as its best sub-tile. 120 regions come from originals smaller than dataset scale, so they don't change.
- **Presence AUC:** 0.911 / 0.915 on all tiles, against 0.901 / 0.904 before. On the 181 changed regions it is **0.951 / 0.951** against 0.924 / 0.934. The scene hit rate is unchanged.
- **Solver change.** Scenes are never shrunk; only scenes below a 1024 short side are scaled up. On the hi-res set this costs about 2.4× more requests.
- **Hi-res, by eyeball.** The Toys and Ocean misses are now hits. New doubts: Skiing and Beach may be **Wenda** (stripes, bobble hat, glasses, longer hair), and Film Set's pick shows no glasses.

## Lookalikes: Wenda and the Waldo-watchers (shipped: negative references)

- **References.** Wenda and a strip of Waldo-watchers are cropped from the unredacted hi-res Food Court lineup (`assets/wenda-ref.png`, `assets/watchers-ref.png`). That scene isn't part of the eval, so there's no leak. Watchers don't wear glasses.
- **Probe** (`probe_lookalikes.py`): 9 Waldos and 5 lookalikes (2 Wendas, 1 watcher, a striped torso, a fisherman), each verified by eye. These are native tiles centred on hi-res solver picks, with 3 repeats each. The probe is small and its tiles were picked after seeing the results, so it's indicative only.

| Variant | Probe AUC | Eval AUC (native, two runs) |
|---|---|---|
| Phrasings, no negatives (previously shipped) | 0.711 (both Wendas score 0.87) | 0.911 / 0.915 |
| Contrast text: "not Wenda (skirt, long hair), not watchers (no glasses)" | 0.800 | 0.909 / 0.914 |
| **Wenda and watcher pictures as `not_waldo` in `state`** | **0.911** | **0.929 / 0.928** |
| … minus 0.5 × a lookalike Noul | 0.956 | 0.893 |
| … minus 1.0 × a lookalike Noul | 0.956 | 0.834 |

- The pictures in `state` lift both measures, so they ship. The lookalike-Noul penalty helps the probe but clearly hurts the larger eval, so it doesn't ship.
- **Hi-res, by eye.** Skiing is fixed (the real Waldo, not Wenda). Beach (Wenda) and Film Set (a watcher) are still wrong. Underground, Candy Factory and Space Station switched to a *different* glasses-and-bobble-hat figure than the last run, and I can't tell Waldo from Wenda there by eye.
- **Measurement gap.** There's no ground truth for the hi-res scenes, so end-to-end changes there can't be measured, only eyeballed.

## Two-pass re-ranking (measured, not shipped)

Plan: `specs/2-pass.md`. Each scene's top-K pass-1 regions (cached `native_negrefs`) are cropped square around their pass-1 box and shown as options of one Choice, plus a `none` option. The Choice is asked in rank order and reversed, and the probabilities are averaged. If `none` wins, the pick falls back to pass 1. Reproduce with `uv run rerank_eval.py <config>` (`rerank_eval.py`, `waldo/rerank.py`, `waldo/candidates.py`).

Hits are out of 17 scenes; `none` wins and order agreement are out of 20 scenes (3 have no Waldo tile). Where a row has two runs, they're separated by `/`.

| Config (K, min crop px, request px) | Pass 2 hits | Forced (no `none`) | `none` wins | Orders agree |
|---|---|---|---|---|
| Pass 1 alone (shipped) | 15 | | | |
| K3, 256, 560 | 15 / 15 | 13 / 13 | 9 / 9 | 16 / 17 |
| K3, 128, 560 | 15 | 15 | 6 | 17 |
| K3, 256, 1024 | 15 | 14 | 4 | 20 |
| K3, 128, 1024 | 15 | 15 | 5 | 18 |
| K5, 256, 560 | 14 (breaks scene 9) | 12 | 9 | 16 |
| K10, 256, 560 | 15 | 13 | 11 | 17 |

- **No gain.** No config fixes either miss (scenes 16 and 17). Every pass-2 "hit" is pass 1's pick, either confirmed or reached through the `none` fallback.
- **It confirms, it doesn't discover.** When pass 1 is right, the Choice usually backs c1 at 0.7–0.99. In hard scenes `none` gets 0.4–0.6, and forcing a pick among the crops breaks hits.
- **Tighter crops help the forced pick** (13 → 15 of 17), which matches pass 1's lesson that more pixels on Waldo matter. Still, they only reach pass 1's level.
- **The pass-1 box is the bottleneck.** In scenes 16 and 21 the Waldo region's box isn't on Waldo, so its crop can't win (in 21, pass 1 hits only at region level). In 17 Waldo is small and partly hidden. In 4 he is clearly visible and still loses to `none`.

## Hi-res with ground truth: zoom on the tile's own box

**Labels.** Waldo is boxed by hand in all 10 hi-res scenes (`data/hi-res/labels.json`, drawn with `build_labeler.py` → `out/label.html`). Five of my by-eye guesses turned out to be wrong.

**Eval** (`uv run hires_eval.py [variant ...]`)
- A tile contains Waldo when it holds the centre of his label.
- *Top-1* is the number of scenes whose top tile contains Waldo; there the box also overlaps the label every time.
- The baseline is the shipped request on all 700 tiles (`out/labeler/tiles.jsonl`). Variants run on a 110-tile subset: each scene's Waldo tile plus its 10 strongest rivals under the baseline. Waldo's baseline rank is at most 8, so this is exactly a "re-score the top 10" pipeline.

| Variant | Tile AUC (subset) | Top-1 | Waldo's rank per scene |
|---|---|---|---|
| Shipped (baseline, all 700 tiles: AUC 0.985) | 0.898 | 5/10 | 2 1 8 1 1 3 1 3 2 1 |
| Shipped, rerun | 0.894 | 5/10 | 2 1 7 1 1 3 1 3 2 1 |
| + lookalike Nouls | 0.906 | 5/10 | 2 1 7 1 1 3 1 3 2 1 |
| **Zoom: crop square around the tile's own box (≥128px, or 3× the box), asked like a tile** | **0.956 / 0.963** | **8/10** (both runs) | 1 1 1 1 1 1 1 3 2 1 |
| Zoom ≥64px | 0.967 | 8/10 | 1 1 1 1 1 1 1 3 3 1 |
| Zoom ≥96px | 0.958 | 8/10 | 1 1 1 1 1 1 1 4 3 1 |
| Zoom ≥192px | 0.954 | 7/10 | 1 1 2 1 1 1 1 3 2 1 |
| Zoom + lookalike-Noul penalty (0.25–1.0) | 0.966–0.969 | 8/10 | trades Space Station for Film Set |
| Mean of tile and zoom presence | 0.951 | 7/10 | |

- **Ranking was the problem, not boxes.** On Waldo's own tile the box hits him in 10/10 scenes; he loses only because striped lookalikes (watchers, kids, a Wenda-like figure, a printed Waldo-face badge in Film Set) outrank his tile.
- **Zooming in on the box fixes 3 of 5 misses** and is stable across two runs and three zoom levels (64–128px, i.e. up to 24× instead of 6×). It confirms the earliest lesson: more pixels on Waldo beat everything else.
- **The lookalike penalty doesn't help.** Any 9/10 result came from choosing the weight and Noul after seeing the scores, so the penalty isn't shipped.
- **Still missed:** Space Station (Waldo ranks 3rd) and Toys (2nd).
- **Not shipped yet.** The solver change would be: pass 1 unchanged, then re-score the top 10 tiles with the zoom crop (+10 requests per scene) and pick by zoomed presence.

## Batching zoom crops into one request

**Redaction first.** Film Set had an unredacted Waldo-face badge on a clapperboard, which was one of the rivals. It's now in `redact_stamps.py`, and the cached tiles near it were re-scored. Numbers above this section predate that; it moved Film Set's Waldo rank 7 → 6 and changed nothing else.

**How a batch works** (`waldo/batch.py`). The crops go in `state` as `crops.c1…cN`, next to `waldo` and `not_waldo`. Every crop gets the shipped tile questions, pointed at it (4 presence Nouls + Box). Within a scene, crops are ordered by position, because the subset lists Waldo's tile first.

**Size limit.** 4 crops at 1536px fit in one request; 6 return `400 max_tokens_exceeded`.

| Variant (zoom ≥128px crops) | Requests | Tile AUC | Top-1 | Waldo's margin over the best rival, per scene |
|---|---|---|---|---|
| One crop per request (`zoom128`) | 110 | 0.956 / 0.963 | 8/10 | +.13 +.06 +.10 +.08 +.17 +.05 +.27 −.03 −.11 +.01 |
| **4 crops per request, 1536px (`batched128_g4`, two runs)** | **30** | **0.987 / 0.990** | **10/10** | +.12 +.10 +.05 +.09 +.20 +.06 +.23 +.02 +.13 +.15 |
| All 11 crops in one request, 768px (`batched128_s768`) | 10 | 0.966 | 9/10 | boxes degrade: mean IoU 0.15 vs 0.57 |

- **Batching is both cheaper and better.** It needs 3.7× fewer requests, and both runs put Waldo first in every scene. Toys flips from −0.11 to +0.13, and Underground's margin grows.
- **This wasn't tuned.** The group size of 4 is the request size limit, not a swept setting. Still, it's 10 scenes; Space Station wins by only +0.02/+0.03.
- **Why it helps is unknown.** A plausible guess is that seeing other crops from the same scene calibrates each answer. That isn't verified.
- **Don't shrink crops to fit more.** At 768px the ranking holds (9/10), but the boxes fall apart.

## Shipped: two-pass solver with batched zoom (`waldo/solver.py`)

- **Pass 1** is unchanged: the shipped request on every native 256px tile.
- **Pass 2** takes the 10 most likely tiles (`SHORTLIST`) and crops each square around its pass-1 box (`candidates.zoom_frame`, at least 128px). The crops are ordered by position and asked 4 per request (`batch.GROUP`). The pick is the crop with the highest zoomed presence, and its box comes from that crop.
- **Cost:** 3 extra requests per scene (70 → 73 on hi-res).
- **End to end** (`uv run solve.py && uv run hires_eval.py solution`): the box is on Waldo in **10/10** scenes, against 5/10 for the previous solver. IoU with the hand-drawn box ranges 0.15–0.86.
- **Caveats:**
  - `THRESHOLD` isn't recalibrated for zoomed presence. Every scene contains Waldo, so "No Waldo" still can't be measured.
  - It's one end-to-end run on 10 scenes that also served for tuning the zoom level.

## Batching pass 1 too (measured on the 3 hardest scenes, not shipped)

These are the scenes where pass 1 ranks Waldo worst: Film Set, Ocean and Space Station. Reproduce with `uv run hires_eval.py --scenes=Film-Set,Ocean,Space-Station pass1_g4 pass2_after_pass1_g4`.

| Pass 1 (210 tiles) | Requests | Tile AUC | Waldo's rank |
|---|---|---|---|
| One tile per request (shipped) | 210 | 0.948 | 7, 3, 3 |
| **4 tiles per request, position order (`pass1_g4`)** | **54** | **0.979** | **2, 2, 1** |

- **The shipped pass 2 on that shortlist** (`pass2_after_pass1_g4`, top 10 → zoom crops in batches of 4, 9 requests) puts Waldo first in **3/3** scenes, with tile AUC 1.000.
- **Batching helps pass 1 as well**, and it would cut a hi-res scene from 73 requests to 21.
- **Probably fewer tokens too:** each request repeats the 3 reference pictures, so 4 tiles per request means 7 images instead of 16. That assumes images make up most of the tokens, which isn't verified.
- **Caveats:** one run on 3 scenes, chosen for being hardest under the unbatched pass 1; they were not chosen for batching. The other 7 scenes weren't run, to save tokens.

## Next steps

1. Ship batched pass 1 in the solver, then confirm end to end on all 10 scenes when tokens allow.
2. Get scenes that weren't used for tuning, to check that this generalises.
