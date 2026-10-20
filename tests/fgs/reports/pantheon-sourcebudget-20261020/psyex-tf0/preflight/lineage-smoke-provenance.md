# Lineage smoke provenance

The executed smoke used the analysis venv Python and imported the final `encode_r16.py` by absolute path. It created a temporary synthetic receipt and packet-window JSON (336 packets: 96 one-byte prefix packets, then 240 packets totaling 11,875,000 bytes), called the module-level `validate_chain(receipt, sha256(receipt))`, and asserted acceptance. It then made two temporary mutations: changed `--enable-tf` from `0` to `1` (asserted rejection) and introduced an attempt-2 predecessor cycle (asserted rejection). No encoder, decoder, media, or GPU was used.

Exact executed shell command was an inline heredoc and was not persisted as a standalone script; this is a truthful reconstruction of its operations, not a claim that this file was executed. Evidence is `lineage-smoke.json` (SHA `f2bbb0f33e47af15ce12242b435cf0239b3791fa3fb37131b8ae211d2e997b96`).
