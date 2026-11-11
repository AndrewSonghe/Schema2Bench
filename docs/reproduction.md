# Reproducing the analyses

These instructions accompany manuscript v43. S2B is recorded as `refill` in
the unchanged data keys and replay output. Run commands from the repository root.
The standard-library replay requires no
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

Semantic recount reproduces the generated-task panel in Table VIII(a) from the
final 4,000-item label file. The prompt and response schema are included under
`evaluation/semantic/`. The one unavailable response remains in the denominator.
The reference cross-check panel uses a different sample. The uniform Terra
follow-up below includes its 160 reference labels; the other Qwen parsing settings are
not recomputed by this command.

The witness command checks exact coverage of the permitted unknown cells and
recomputes the saved positive gap difference, approximately 0.000037889. It
verifies feasibility under the stated score model; it does not repeat the search
or decide whether those assignments are semantically correct.

## External contexts and uniform semantic review

```bash
python3 scripts/replay_followup.py
```

This standard-library command reconstructs the BEAVER score matrices in both
schema contexts, checks all population and model counts, and recomputes Base
and Verified TEF/gap tables, direct contrasts and per-database contrasts.
Each context uses its own 1,034-item Spider source; source scores from different
contexts are not pooled. Unknown counts are checked against the saved analysis.

It then recounts the 480 uniform semantic labels, reparses 479 available response
texts, checks paired original/rewrite labels, and builds the union with prior
flags. It recomputes the semantic-sensitivity contrasts using the main score
matrices and the added rewrite matrix. All numeric outputs must agree with the
saved results within 1e-10. Success ends with `FOLLOWUP_REPLAY_VERIFIED`.

This command uses no API, GPU or database. It verifies score-based analyses and
response parsing; it does not independently establish semantic truth or repeat
database execution. Context definitions and interpretation are in
[External and semantic checks](followup.md).

## Figures

Install the optional dependencies from `requirements.txt`, then run:

```bash
python3 figures/draw_fig3.py
python3 figures/draw_fig4.py
python3 figures/draw_fig5.py
python3 figures/draw_fig6.py
```

The scripts check their saved numerical inputs and write PDFs, SVGs and local
validation output under `figures/`. Add `--preview /path/to/previews` to write
PNGs. The published figures use Arial; plotting falls back to Matplotlib's
DejaVu Sans when Arial is unavailable, so font metrics can differ. The original
numerical inputs remain fixed. These commands redraw saved analyses; the main
matrix replay separately recomputes the five-method comparison from item scores.

Figure 1 is supplied as an editable PowerPoint drawing (`figures/Fig1.pptx`)
and its exported PDF. Figure 2 is a vector diagram; `python3 figures/edit_fig2.py`
recreates its current labels from `figures/Fig2_base.pdf` using PyMuPDF. These
two figures illustrate the problem and method, not measured outcomes.

The manuscript builds with fixed assets in `paper/figures/current/`. Plotting
does not overwrite those assets. `paper/figures/v8/` retains the older layout;
it is not used by the v43 build. To read the exact submission rendering, use
`paper/Schema2Bench_ICDE2027_v43.pdf`. To rebuild from source:

```bash
sh paper/build.sh
```

The output is `paper/build/main.pdf`. This requires TeX Live with IEEEtran and
`latexmk`, but no database, API key or plotting dependencies.

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
