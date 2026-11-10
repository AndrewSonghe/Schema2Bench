# Paper-to-artifact map

The map follows the current manuscript's section numbering. "Replay" means a
calculation is run from the included records. "Saved analysis" means the reported
numerical output is included without its full input pipeline.

| Paper content | Artifact | Coverage |
| --- | --- | --- |
| Section III: SQL construction | `src/schema2bench/`, `scripts/generate_candidates.py` | Core components and an executable example; historical population formation is not regenerated |
| Section III: bounded selection | `selection/`, `scripts/replay_selection.py` | Reconstructs any of ten structural releases and checks saved membership |
| Section IV: cache checks | `evaluation/cache_check/`, `scripts/check_sqlite_sample.py` | Original 32-query sample; rerun requires matching external databases |
| Sections IV-V: five-method comparison | `replay/main/` | Item-level replay of both scoring layers, direct TEF/gap contrasts and ten releases |
| Section V: model-selection regret | `figures/data/regret.json`, `paper/` | Saved analysis and figure input |
| Section VI: column/value controls | `figures/data/name.json`, `depth.json` | Saved aggregate and domain analyses |
| Section VI: same-SQL rewriting | `figures/data/rewrite.json` | Saved analyses and plotting input |
| Section VI: difficulty support | `scripts/check_difficulty_support.py` | Recomputes the 0.3775 capacity certificate |
| Section VI: general support diagnostic | `diagnostics/support.py` | Executable four-block LP/integer relaxation with example |
| Section VII: generated-task semantic audit | `evaluation/semantic/` | Recounts the 4,000 archived labels and retains the review protocol |
| Section VII: uncertainty and witnesses | `figures/data/risk.json`, `replay/witness/` | Saved scenario bounds and independent replay of one binary witness |
| Section VII: weight sensitivity | `figures/data/weights.json` | Saved component bounds and region plotting |
| Section VII: uniform Terra review and joint semantic sensitivity | `evaluation/followup/semantic/`, `scripts/replay_followup.py` | Recounts 480 labels, parses 479 responses and replays the added score sensitivities |
| Section VII: BEAVER pilot and schema-context control | `evaluation/followup/beaver/`, `scripts/replay_followup.py` | Recomputes TEF/gap tables, unknown counts and direct aggregate/domain contrasts from stored scores |
| Section VII: revised references, larger panels and TACO pilot | `paper/` | Reported results; full rerun inputs are not included in this compact release |

The package is sufficient to inspect the main construction components and
recompute the main stored-score comparison. It should not be described as a
complete regeneration package for every experiment in the paper.
