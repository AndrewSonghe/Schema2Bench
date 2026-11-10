# Data and evaluation records

## Task sets

`data/tasks/{template,refill,ring,omni,synth}.jsonl` contains the first release,
with 2,000 tasks per construction. `reference.jsonl` has 906 target references;
`source.jsonl` has 1,034 Spider source tasks. Each record identifies its database,
question and SQL. External-method and source records also retain the original
prompt hash and a shared prefix key. `data/prompt_prefixes.json` stores those
prefixes once; concatenate prefix, `question_delimiter` and `prompt_suffix` to
recover the recorded prompt exactly. The original prompt hash verifies the join.

`selection/PAIR_METADATA.jsonl` contains the 3,778 canonical candidate pairs
eligible for structural selection. Its IDs bind Template and Refill alternatives,
which need not have the same meaning. Ten-release membership is recorded in
`replay/main/matrices/memberships.json`.

## Matrices

Each matrix row contains `id`, `domain`, `base` and `verified`. The last two are
lists in the model order defined by `memberships.json`. A score is `[0,0]` for a
known execution mismatch, `[1,1]` for a match, or `[0,1]` when unresolved.

`core.jsonl` covers the union of paired tasks selected across ten releases.
The other method matrices cover fixed 2,000-item sets. Source and reference
uncertainty is shared when constructing direct contrasts. Subtracting separately
optimized row intervals would compute a different comparison.

Base applies the original execution scoring rules. Verified adds recorded native
SQLite, row-count and ordering evidence. Proof coverage differs by method;
Verified does not mean human-verified question semantics.

## Model outputs

`data/predictions/<population>/<model>.jsonl.gz` contains compact JSON Lines.
Use Python's `gzip.open(path, "rt")` to read it. Output text, parsed SQL,
termination information, prompt hashes and token counts are retained when
present in the original record. Full token-ID arrays are omitted. Each row has
`record_sha256`, the hash of the original record serialized with sorted keys and
compact separators, for comparison with the retained source archive.

`data/tasks/paired_union.jsonl.gz` contains the question and SQL for every paired task
selected in any of the ten releases.

The paired population covers all stored inputs needed by the ten releases and
target references. The source population and each external method are separate.
The recorded `qwen` alias is retained where present; `canonical_model=qwen3_8b`
binds it to the model ordering.

## Semantic labels

The 4,000 rows in `evaluation/semantic/labels.jsonl` are joined to construction
and domain IDs. Sampling is 100 tasks per method per domain. The exact blinded review inputs are
in `evaluation/semantic/inputs.jsonl.gz`. Labels are
`supported`, `incorrect`, `insufficient` or `unavailable`. They describe an API
review of question-SQL agreement and should not be read as ground-truth labels.

## Dependencies and redistribution

`configs/databases.json` lists byte hashes of local snapshots; these are not
publisher signatures. `configs/models.json` identifies model snapshots and
retains their recorded file fingerprints. Neither weights nor databases are
included. Upstream task data and generated derivatives retain the applicable
source terms. The local staging package does not assign a new license to those
materials.
