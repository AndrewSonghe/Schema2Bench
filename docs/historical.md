# Earlier seven-database experiments

Section VI-A and Table IV(b) report experiments on Chinook, IMDb, Instacart,
SFDFFD, TPC-DS, TPC-H and USAccidents. They evaluate an earlier SQL-first
constructor and selection modules. Their seven-model panel differs from the
current ten-model deterministic Refill comparison on BIRD.

The compact records in `evaluation/historical/` contain:

- Selection summaries for a 2,806-candidate pool, 2,000-task releases and ten
  overlapping seeds. Exact-fraction TEF outputs cover 80 saved releases,
  including anchors, bounded selectors and matched random controls.
- Cell-level metrics for 147 construction runs: seven methods, seven databases,
  three seeds and 500 attempts per cell. The summary retains all seven methods.
- Scope, model names and SHA-256 hashes linking these files to the original
  archived analyses.

Run the recount with the Python standard library:

```bash
python3 scripts/recount_historical.py
```

It checks the table values, the 5.67% pooled TEF reduction relative to quota
random, and the repair yield change from 396.00 to 417.90 unique SQLs per 1,000
attempts, with 20 favorable database/seed pairs and one tie. Controlled
construction has lower profile error than Ring-style, but lower yield and
higher token cost.

All 14 cost-aware exchanges occur in TPC-DS because the old release has unequal
domain quotas. The pooled reduction does not show improvement within every
database. Structural greedy retains lower structural loss. These are reused
development records, not independent confirmation of the current Refill
implementation or evidence of target model-selection gains. The recount checks
archived cell and release summaries; it does not repeat inference or reconstruct
every historical membership from item-level responses.
