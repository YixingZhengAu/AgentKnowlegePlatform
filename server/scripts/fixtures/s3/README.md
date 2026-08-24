# S3 demo fixtures — the reviewed output of the Phase B tuning work

These files are **not test data**. They are the human-reviewed governance assets that the
analytics Q&A demo runs on, produced and signed off one stage at a time in a throwaway
lab that never entered the repository (see the B1–B8 evidence blocks in `documents/S3-PLAN.md`). `scripts/seed_s3_demo.py` loads them into the
real tables so a fresh machine gets the same demo — and the same measured accuracy — without
re-spending the LLM budget that produced them.

| File | What it is | Who reviewed it |
| --- | --- | --- |
| `semantic_layer.json` | table/column descriptions + per-value meanings for every enum | B2 gate |
| `intents/i*.json` | 12 verified intents: SQL template + the three-zone parameter panel | B4 + B6 gates (i01–i18); hand-authored and query-tested (i19–i23) |
| `questions/i*.json` | ~8 similar questions per intent (the retrieval surface) | B7 |
| `non_data_faces.json` | 12 "none of the above" faces that make the null route work | B7/B8 |
| `eval_cases.json` | the frozen 20-question eval set, kept as a regression asset | B8 gate |

Editing these by hand is allowed and expected (they are meant to be human-editable assets),
but `eval_cases.json` is the yardstick: change it and the "migration is lossless" claim in
`smoke_s3_e2e.py` no longer compares like with like.
