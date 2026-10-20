# R16 midpoint rate refinement runner

Preparation only; no new encode has been launched. `encode_refine.py` retains
the execution body of the frozen R16 TF-off runner, with fresh output root and the
Round16 rate-refinement contract bound. Initial execution requires both immutable
10014 (low) and 10070 (high) receipts and the strict midpoint request 10042.
Later requests must cite the immediately previous refinement receipt and derive a
strict interior midpoint from its measured bracket. At most three refinement
requests are allowed by the contract. Existing R16 runners and receipts remain
immutable.

`replay_refine.py` is a preparation-only adaptation of the reviewed R11 replay:
it imports the new refinement runner's recursive receipt validator, preserves the
same R11 build pins and pass-2-only neutral replay, and uses a fresh replay root.
It is not executable until a selected matched refinement receipt and parent
build/admission pins are supplied.

The parent corrected the worker drafts before execution. The public validator
now validates refinement nodes, reconstructs endpoint updates from predecessor
receipts, and validates original endpoints through the frozen original runner.
Endpoint-equal rates are allowed; requests must remain strictly interior.
The corrected replay is derived directly from verified R16 replay `03118968…`,
not the rejected package's R8-based replay.

Current runner SHA256:
`5804a1a5985d0676975abe28fba2d8c7a8d6af71c2f70d39dab11436bf2941e4`.
Current replay SHA256:
`8491a376d6376aeb3f0cd2e3903c513b8f7bd0a300eaddd1d882a06917814cc6`.
Reproduction of the parent edits is in
`parent/psyex-tf0-r16-refine/repair_refine.py`; rejected source revisions remain
beside the current files. Earlier preview/validation receipts apply to the
drafts named in them and do not validate the corrected scripts.
