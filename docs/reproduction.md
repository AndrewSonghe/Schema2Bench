# Reproducing the analyses

Run commands from the repository root. The standard-library replay requires no
installation. Optional construction and plotting commands use `requirements.txt`.

## Main comparison

```bash
python3 scripts/replay_main.py
```

The replay checks the source and target populations, the ten-model ordering,
2,000-item releases and equal domain quotas. It recomputes accuracy, correct-count
CDF and disagreement coordinates, TEF bounds, target-gap bounds and direct
Refill-minus-comparator contrasts for Base and Verified scoring. Each release
must agree with `replay/main/EXPECTED.json` within 1e-10.

For the first Verified release, Template target gap is approximately 0.224967
and Refill is approximately 0.169275. The direct difference is approximately
-0.055693. The output ends with
`PORTABLE_FIVE_METHOD_TEN_SEED_REPLAY_VERIFIED` and is saved in
`replay/main/REPLAY_RESULT.json`.

## Selection and structural coverage

```bash
python3 scripts/replay_selection.py --release 0
python3 scripts/check_difficulty_support.py
```

The saved first release contains 2,000 tasks and ten exchanges with H=1/100.
Choose release indices 0 through 9 to check the other releases. This command
reconstructs the structural selection; it does not repeat the earlier
output-availability screening that formed the eligible pool.

The difficulty certificate checks the capacity of the original quota-constrained
pool. Its 173 easy slots imply a TV lower bound of 0.3775 and a necessary deficit
of 755 additional eligible easy candidates for exact matching. This is a
structural statement, not a bound on TEF or semantic quality.

The more general diagnostic solves a four-block relaxation that excludes the
nonnegative operator block:

```bash
mkdir -p results
python3 diagnostics/support.py --candidates diagnostics/example_candidates.jsonl --profile diagnostics/example_profile.json --anchor diagnostics/example_anchor.json --quotas diagnostics/example_quotas.json --tau 0 --seconds 30 --output results/support.json
```

The diagnostic reports solver status and an integer witness when available.
A solver time limit must not be interpreted as a proof of optimality.

## Semantic judgments and score sensitivity

```bash
python3 scripts/recount_semantic.py
python3 scripts/replay_witness.py
```

Semantic recount reproduces the generated-task panel in Table VIII from the
final 4,000-item label file. The prompt and response schema are included under
`evaluation/semantic/`. The one unavailable response remains in the denominator.
The reference cross-check panel uses a different sample and is described in the
manuscript; it is not recomputed by this command.

The witness command checks exact coverage of the permitted unknown cells and
recomputes the saved positive gap difference, approximately 0.000037889. It
verifies feasibility under the stated score model; it does not repeat the search
or decide whether those assignments are semantically correct.

## Figures

```bash
python3 figures/draw_fig3.py
python3 figures/draw_fig4.py
python3 figures/draw_fig5.py
python3 figures/draw_fig6.py
```

The scripts check their saved numerical inputs and write PDFs, PNGs and local
validation output. They redraw archived analyses; only the main matrix replay
recomputes the complete five-method comparison from item scores. Figures 1 and 2
are conceptual diagrams supplied with the manuscript.

## Full reruns

Full reruns require the database snapshots, model weights, inference runtime,
original prompt construction and all per-experiment generation policies. The
package contains the core constructor, the published task records, score
matrices and compact outputs, but does not package a complete model-serving
installation or every historical experiment launcher. The example constructor
is for using the components on another SQLite database; its output is not an
exact reconstruction of the paper's population. Local offline replay should not
be described as a complete end-to-end regeneration of all experiments.

## Optional SQLite cache check

The original fixed-hash sample of 32 query results is retained as JSON under
`evaluation/cache_check/`, together with the original audit result. This sample
was exported from the existing cache without new database execution.

After obtaining the matching snapshots, the check can be repeated with:

```bash
python3 scripts/check_sqlite_sample.py --database-root /path/to/databases
```

The command verifies database hashes, opens SQLite in read-only mode and compares
column counts and result multisets. It does not establish question-SQL semantic
agreement. The databases are external dependencies and are not in this repository.
