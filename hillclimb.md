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

## Next steps

1. Re-check the top 3 tiles per scene with a more expensive second pass.
2. Use a reference picture from outside the dataset, so scene 1 can be scored again.
3. Slice full scenes into tiles and score each one with `x6_phrasings`.
