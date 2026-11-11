# External and semantic checks

The main comparison remains the eight-database BIRD study. In manuscript v39,
these checks appear in Sections V-D2/V-D3 (semantic assessment) and V-E
(generalization). The original identifier `refill` remains in the saved records. Two later checks
examine its transfer scope and the interpretation of question rewriting.
Their score-based analyses can be replayed with:

```bash
python3 scripts/replay_followup.py
```

## BEAVER under two schema contexts

The pilot uses the SQLite-converted BEAVER distribution provided by
[CORE-T](https://github.com/UKPLab/emnlp2026-core-t), rather than the original
MySQL environment. Template and S2B did not reach the original 250-pair
construction requirement in two databases. A separate partial-panel protocol
retains 250 tasks per method in DW, 198 in Nova and 24 in Neutron, together with
121, 43 and 30 references. Nova and Neutron are related databases. These are
fixed unequal populations, not three independent draws from a domain population.

All ten models evaluate Template, S2B, Ring and the references. The first
condition uses retrieved schemas. The control supplies all required tables and
views, including view dependencies, selected using reference SQL. The SQL itself
is hidden from the evaluator. All 1,610 target prompts use this oracle selection;
the 1,034 Spider prompts use full compact DDL. Every prediction is regenerated in
the control, and TEF uses the source scores from the corresponding context.

The table reports Verified direct S2B-minus-comparator differences. Negative
values favor S2B. Bounds preserve shared uncertain source/reference variables;
they are conservative score bounds, not confidence intervals.

| Context | Comparator | TEF difference | Target-gap difference |
| --- | --- | --- | --- |
| Retrieved schema | Template | [-0.146163, -0.037765] | [-0.081035, +0.060364] |
| Retrieved schema | Ring | [-0.235815, -0.016203] | [-0.056789, +0.099330] |
| Sufficient schema | Template | [-0.142702, -0.028519] | [-0.083884, +0.049262] |
| Sufficient schema | Ring | [-0.130602, +0.168975] | [-0.051570, +0.064633] |

S2B's source-fidelity advantage over Template persists in both contexts.
Against Ring it is unresolved in the sufficient-schema condition; Neutron's
sufficient-schema TEF and gap both favor Ring. Reference scores contain 660 and
663 unknowns out of 1,940, respectively, and only 21 definite matches in either
context. Supplying the necessary schema therefore does not resolve target
alignment. The earlier TACO pilot remains adverse against Ring and unresolved
against Template; these BEAVER results do not replace that finding.

The package retains 26,440 compact score records per context, including the
matching Spider source. Questions, SQL, database rows, weights and inference
outputs for BEAVER are not redistributed here. `provenance.json` records source
hashes and the context definitions. The replay recomputes both scoring layers,
aggregate and per-database contrasts, and unknown counts from those scores.

## Uniform Terra review

The fixed sample contains 160 original questions, their 160 rewrites with SQL
held fixed, and 160 target references, each balanced over the eight domains.
There are 160 new original-question reviews and 319 reused available reviews;
one rewrite is unavailable. All use `gpt-6.1-terra`, the same review prompt and
label schema. The structured-output format name differs for the reference
requests; these are not byte-identical requests.

| Sample | Supported | Incorrect | Insufficient | Unavailable |
| --- | ---: | ---: | ---: | ---: |
| Original | 141 | 14 | 5 | 0 |
| Rewrite | 117 | 32 | 10 | 1 |
| Reference | 89 | 54 | 17 | 0 |

Union with prior flags gives 24 original S2B, 43 rewrite, 23 Ring and 71
reference concerns. Only these scores are relaxed; no new labels are assigned
to unsampled items. Denominators remain 2,000 tasks per method, 906 references
and 1,034 source items. Under Verified scoring, rewrite-minus-original gap is
[-0.142130, +0.032135] and TEF is [-0.008539, +0.235566]. Both include zero.

These bounds qualify the execution-level wording comparison. They do not
estimate the chance that rewriting helps, nor establish a human semantic gold
standard. The 19 new original-question concerns all occur in the thrombosis
database and involve a date interpretation; this concentration is retained in
the domain and label-pattern records. It is a reason to inspect model judgment,
not to relabel the sample automatically.

The available response texts are compact exports bound to original response
hashes. The initial independent recount had a syntax error; the corrected
independent recount passed without changes to model outputs or scores. Its audit
record is included. The packaged replay performs a further calculation from the
distributed labels, prior flags and score matrices.
