# Paper-to-artifact map

The map follows manuscript v40. "Replay" means a
calculation is run from the included records. "Saved analysis" means the reported
numerical output is included without its full input pipeline.

| Paper content | Artifact | Coverage |
| --- | --- | --- |
| Section IV-A: Benchmark Construction | `src/schema2bench/`, `scripts/generate_candidates.py` | Core components and an executable example; historical population formation is not regenerated |
| Section IV-B and V-C1: Workload Selection | `selection/`, `scripts/replay_selection.py` | Reconstructs any of ten structural releases and checks saved membership |
| Section IV-C: execution scoring and cache checks | `evaluation/scoring.py`, `evaluation/proofs/`, `evaluation/cache_check/`, `scripts/check_sqlite_sample.py` | Scorer and saved evidence; original 32-query sample requires matching external databases for a rerun |
| Section V-B, Table II: five-method comparison | `replay/main/` | Item-level replay of both scoring layers, direct TEF/gap contrasts and ten releases |
| Section V-B3, Table III, Figure 3(c): model-selection regret | `figures/data/regret.json`, `paper/` | Saved first-release analysis with 906 references and figure input; the additional 1,118-reference rows are reported in the manuscript |
| Section V-C1, Table IV(b): earlier seven-database selection and repair | `evaluation/historical/`, `scripts/recount_historical.py` | Recounts archived selection and 147-cell generation summaries; see [scope](historical.md) |
| Section V-C2, Table V: column/value controls | `figures/data/name.json`, `figures/data/depth.json` | Saved aggregate and domain analyses |
| Section V-C3, Table VI: same-SQL rewriting | `figures/data/rewrite.json` | Saved analyses and plotting input |
| Sections IV-B1 and V-C4: difficulty support | `scripts/check_difficulty_support.py` | Recomputes the 0.3775 capacity certificate |
| Section IV-B1: general support diagnostic | `diagnostics/support.py` | Executable four-block LP/integer relaxation with example |
| Section V-C5: additional candidate generation | `paper/` | Reported results; the full generation inputs are outside this compact release |
| Section V-D2, Table VIII(a): generated-task semantic audit | `evaluation/semantic/` | Recounts the 4,000 archived labels and retains the review protocol |
| Sections V-D2/V-D3, Table IX and Figure 5: uncertainty and witnesses | `figures/data/risk.json`, `replay/witness/` | Saved scenario bounds and independent replay of one binary witness |
| Section V-D4, Figure 6: weight sensitivity | `figures/data/weights.json` | Saved component bounds and region plotting |
| Sections V-D2/V-D3, Table VIII(c): uniform Terra review and joint semantic sensitivity | `evaluation/followup/semantic/`, `scripts/replay_followup.py` | Recounts 480 labels, parses 479 responses and replays the added score sensitivities |
| Section V-E, Table XI: BEAVER pilot and schema-context control | `evaluation/followup/beaver/`, `scripts/replay_followup.py` | Recomputes TEF/gap tables, unknown counts and direct aggregate/domain contrasts from stored scores |
| Sections V-D/V-E: revised references, model-panel checks, TACO pilot and seven-database diagnostic | `paper/` | Reported results; full rerun inputs are not included in this compact release |
| Figures 1-6 and manuscript | `figures/`, `paper/figures/current/`, `paper/Schema2Bench_ICDE2027_v40.pdf` | Published figure assets, editable/plotting sources and the v40 PDF; see [figure instructions](reproduction.md#figures) |

The package is sufficient to inspect the main construction components and
recompute the main stored-score comparison. It should not be described as a
complete regeneration package for every experiment in the paper.

The manuscript calls the method Schema2Bench (S2B). Existing records retain
`refill` as their method identifier. The paper's Figure 1 is illustrative;
Figure 2 describes the workflow. Neither is an additional experimental result.

In v40, bold and underlining mark best and second reported values only within
comparable groups. Interval-valued rankings require an established order;
midpoints are not ranked. S2B is uniquely first on the main Verified TEF measure,
while its target gap is fourth. The TEF runner-up and mutual gap ordering of
Ring/Omni/Synth remain unresolved. API support counts rank model judgments
within the same review panel, not semantic truth. Experimental values are
unchanged from v39.
