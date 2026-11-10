# Schema2Bench

**Measuring What Text-to-SQL Benchmark Migration Preserves**

Schema2Bench studies what happens to model comparisons when a Text-to-SQL
benchmark is moved to a different relational database. The framework separates
SQL grounding, question realization and workload selection. Evaluation asks two
questions: does the new workload preserve model behavior on the source
benchmark, and does it reproduce model differences on target reference tasks?

![Benchmark migration across databases](docs/overview.png)

The study compares five constructions on eight BIRD databases with ten models,
2,000 tasks per method and 906 target references. Refill improves source fidelity
and target-gap error over the template baseline under the reported scoring
convention. Ring-style construction gives lower target gap and mean selection
regret. Rewriting questions while keeping SQL fixed improves target alignment
but reduces source fidelity.

## Start with the saved results

Python 3.10 or newer is recommended. These commands use the standard library;
they do not need a GPU, database download or API key.

```bash
python3 scripts/verify_manifest.py
python3 scripts/replay_main.py
python3 scripts/recount_semantic.py
python3 scripts/replay_witness.py
```

The main replay recomputes both scoring layers for all ten releases and compares
the tables and direct method contrasts with the archived values. It prints one
confirmation per release. Semantic recount verifies the 4,000 API judgments;
the witness replay checks the saved binary assignment used in the reference-risk
analysis. See [reproduction instructions](docs/reproduction.md) for expected
outputs and additional commands.

## Contents

| Directory | Contents |
| --- | --- |
| `src/schema2bench/` | SQL construction, schema profiling, planning and question-generation components |
| `selection/` | Quota allocation, bounded exchanges, candidate metadata and saved releases |
| `diagnostics/` | Structural support analysis and a small worked example |
| `evaluation/` | Execution scorer, proof records, semantic prompt and archived labels |
| `data/` | Task sets, shared prompt prefixes and compact model-output records |
| `replay/` | Score matrices, membership lists and executable result checks |
| `figures/` | Plotting code and the data for Figures 3-6 |
| `configs/` | Model fingerprints, database hashes and experiment settings |
| `paper/` | Manuscript source and figures |

[Data formats](docs/data.md) explain the record fields and scoring layers.
[Paper-to-artifact mapping](docs/paper-map.md) identifies which results can be
recomputed here and which are supplied as saved analyses.

## Construction and selection

Install the optional analysis dependencies:

```bash
python3 -m pip install -r requirements.txt
python3 scripts/replay_selection.py --release 0
python3 scripts/check_difficulty_support.py
```

The selection replay reconstructs the first release from candidate SQL features
before comparing its IDs with the saved release. The difficulty check recovers
the 0.3775 lower bound and the capacity of 173 easy tasks under the fixed quotas.

A small example runs the construction components on an illustrative database:

```bash
python3 scripts/create_example.py
python3 scripts/generate_candidates.py --database results/shop.sqlite --output results/candidates.jsonl
```

This example creates candidates for inspection. It does not reconstruct the
paper's screened population or establish semantic correctness.

## Reproduction scope

The repository supports offline reanalysis of the retained records. Database
files, model weights and full token-ID arrays are excluded. The compressed
prediction files retain model output text, parsed SQL, termination information
and input hashes. Re-running SQL requires the database snapshots identified in
`configs/databases.json`; re-running inference also requires the model snapshots
and original runtime configuration.

The ten releases overlap and are not independent datasets. Ring, Omni and Synth
are local adaptations of their respective construction approaches. Semantic
labels are model judgments, not human annotations or calibrated confidence
scores. Base and Verified bounds represent unresolved execution scores, not
sampling confidence intervals.

## Paper and data sources

This repository accompanies the manuscript *Schema2Bench: Measuring What
Text-to-SQL Benchmark Migration Preserves*. See `CITATION.cff` for its authors.

The experiments use [Spider](https://yale-lily.github.io/spider/) and
[BIRD](https://bird-bench.github.io/). Obtain databases and model weights through
their original distribution channels and follow the applicable terms.

## Build the manuscript

With TeX Live (including IEEEtran) and `latexmk` installed:

```bash
sh paper/build.sh
```

The PDF is written to `paper/build/main.pdf`.
