# Paper-to-artifact map

The map follows manuscript v44. "Replay" means a
calculation is run from the included records. "Saved analysis" means the reported
numerical output is included without its full input pipeline.

| Paper content | Artifact | Coverage |
| --- | --- | --- |
| Section IV-A: Benchmark Construction | `src/schema2bench/`, `scripts/generate_candidates.py` | Core components and an executable example; historical population formation is not regenerated |
| Section IV-B and V-C3: Workload Selection | `selection/`, `scripts/replay_selection.py` | Reconstructs any of ten structural releases and checks saved membership |
| Section IV-C: execution scoring and cache checks | `evaluation/scoring.py`, `evaluation/proofs/`, `evaluation/cache_check/`, `scripts/check_sqlite_sample.py` | Scorer and saved evidence; original 32-query sample requires matching external databases for a rerun |
| Section V-B, Table II: five-method comparison | `replay/main/` | Item-level replay of both scoring layers, direct TEF/gap contrasts and ten releases |
| Section V-B3, Table III, Figure 3(c): model-selection regret | `figures/data/regret.json`, `paper/` | Saved first-release analysis with 906 references and figure input; the additional 1,118-reference rows are reported in the manuscript |
| Section V-C3, Table IV(b): earlier seven-database selection and repair | `evaluation/historical/`, `scripts/recount_historical.py` | Recounts archived selection and 147-cell generation summaries; see [scope](historical.md) |
| Section V-C1, Table V: column/value controls | `figures/data/name.json`, `figures/data/depth.json` | Saved aggregate and domain analyses |
| Section V-C2, Table VI: same-SQL rewriting | `figures/data/rewrite.json` | Saved analyses and plotting input |
| Sections IV-B1 and V-C4: difficulty support | `scripts/check_difficulty_support.py` | Recomputes the 0.3775 capacity certificate |
| Section IV-B1: general support diagnostic | `diagnostics/support.py` | Executable four-block LP/integer relaxation with example |
| Section V-C5: additional candidate generation | `paper/` | Reported results; the full generation inputs are outside this compact release |
| Section V-D2, Table VIII(a): generated-task semantic audit | `evaluation/semantic/` | Recounts the 4,000 archived labels and retains the review protocol |
| Sections V-D2/V-D3, Table IX and Figure 5: uncertainty and witnesses | `figures/data/risk.json`, `replay/witness/` | Saved scenario bounds and independent replay of one binary witness |
| Section V-D4, Figure 6: weight sensitivity | `figures/data/weights.json` | Saved component bounds and region plotting |
| Sections V-D2/V-D3, Table VIII(c): uniform Terra review and joint semantic sensitivity | `evaluation/followup/semantic/`, `scripts/replay_followup.py` | Recounts 480 labels, parses 479 responses and replays the added score sensitivities |
| Section V-E, Table XI: BEAVER pilot and schema-context control | `evaluation/followup/beaver/`, `scripts/replay_followup.py` | Recomputes TEF/gap tables, unknown counts and direct aggregate/domain contrasts from stored scores |
| Sections V-D/V-E: revised references, model-panel checks, TACO pilot and seven-database diagnostic | `paper/` | Reported results; full rerun inputs are not included in this compact release |
| Figures 1-6 and manuscript | `figures/`, `paper/figures/current/`, `paper/Schema2Bench_ICDE2027_v44.pdf` | Published figure assets, editable/plotting sources and the v44 PDF; see [figure instructions](reproduction.md#figures) |

The package is sufficient to inspect the main construction components and
recompute the main stored-score comparison. It should not be described as a
complete regeneration package for every experiment in the paper.

The manuscript calls the method Schema2Bench (S2B). Existing records retain
`refill` as their method identifier. The paper's Figure 1 is illustrative;
Figure 2 describes the workflow. Neither is an additional experimental result.

In v44, ranking panels retain bold for established best values and underlining
for second place. Interval ranks that are not identified remain unmarked. The
13 ranking marks from v42 are unchanged. API support counts describe recorded
judgments, not semantic truth.

In direct contrasts and sensitivity columns, bold highlights 29 favorable
estimates or intervals wholly on the favorable side of zero. Captions state the
focal method or intervention and the sign convention. Opposite-signed intervals
are adverse; intervals containing zero remain unresolved. This is not a ranking
of different conditions or a significance symbol. Table X explicitly separates
point estimates, conditional confidence intervals and unknown-score bounds.
No custom F/A/U direction codes or significance stars are used.

The experiment narrative separates the main comparison, component controls,
and robustness. S2B improves source fidelity and target gap over Template in
the main Verified comparison, and source fidelity over the three external
adaptations. Those adaptations attain lower target gaps; Ring also has lower
mean model-selection regret. The ablations discuss column/value grounding,
question wording, then selection. Improvements mostly precede selection;
coverage diagnosis remains a separate contribution. External and semantic
sensitivity results limit the generality of these claims.

All eleven table blocks, including the v43 ranking and contrast emphasis,
nine equation groups, 71 citation keys, six figure assets and experimental
records are unchanged. The five-method ten-release stored-score replay was
rerun successfully for v44. The revised narrative states the supported
source-fidelity advantage and Template gap improvement; it does not reclassify
external gap disadvantages as small or statistically non-significant. The requested short
language-assistance disclosure and prior terminology choices are retained.
[Supplementary experiment details](../paper/EXPERIMENT_DETAILS.txt) preserve
score counts, operational limits and auxiliary summaries moved from the main
prose. These details describe existing experiments, not new runs.
