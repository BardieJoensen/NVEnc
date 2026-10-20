# R16 refinement source/settings audit

The encoder policy is the frozen R16 TF-off policy: same input, source commit,
app/library, R8 command receipt, two pass commands, stats discipline, CPU
affinity 0-7, `nice -n 10`, and packet accounting. Only the fresh run root,
request bitrate, and calibration lineage are changed. No min/max-QP bounds or
encoder-policy changes are introduced. The contract is
`ROUND16_RATE_REFINEMENT.md` SHA256
`9ea9b3bd9dcf4c5a7f994e0eb12508448a93142ad9d7b7baec27f5ea21597d82`.
