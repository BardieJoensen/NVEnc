# R16 midpoint-refinement release review

Reviewed 2026-10-20 before any real refinement encode.

## Accepted artifacts

- `encode_refine.py` SHA-256
  `5804a1a5985d0676975abe28fba2d8c7a8d6af71c2f70d39dab11436bf2941e4`
- `replay_refine.py` SHA-256
  `8491a376d6376aeb3f0cd2e3903c513b8f7bd0a300eaddd1d882a06917814cc6`
- addendum `ROUND16_RATE_REFINEMENT.md` SHA-256
  `9ea9b3bd9dcf4c5a7f994e0eb12508448a93142ad9d7b7baec27f5ea21597d82`
- independent binder `bind_refine_headers.py` SHA-256
  `5d30f960504b12d840d9cd916140dac5b24ae2053852c88a5a66b87ae1b347dc`

The corrected encoder is directly derived from frozen R16 runner `2c146047...`.
Its execution body is unchanged except for recording whether the completed
response lies inside the measured bracket. Before importing legacy validation
code it verifies the old runner hash. Its public validator reconstructs the
canonical 10014/10070 endpoints and their old lineages, every later endpoint
replacement, request midpoint, closed measured-rate interval, target interval,
attempt limit, packet rate, policy and live identities. Endpoint-equal rates
remain valid plateaus.

The corrected replay is directly derived from accepted selected-receipt replay
`03118968...`. It requires an explicit matched, under-cap refinement receipt,
calls the corrected public validator, and replays that selected run's pass-two
command and fresh statistics. Neutral output is compared with the selected IVF
and reconstruction, not with R8.

The no-encode preview emitted request 10042 with the exact canonical endpoint
arguments: preview receipt SHA `ea19b811...`, outer receipt SHA `4b3c590a...`.
Synthetic state-machine controls used script SHA `92ecdfa2...`; execution SHA
`f2ee22b5...` completed with return code zero. Four valid cases passed,
including equal-high-rate plateau and both endpoint transitions; five corrupted
phase/midpoint/anchor/rate/identity cases failed. Result SHA is `cd4da98a...`.
These controls establish validator behavior only and make no encode or quality
claim.

## Disposition

The initial 10042 request is released for one fresh two-pass calibration run
through the existing outer execution wrapper. A completed output is selectable
only if the same validator proves its rate inside the unchanged 99--100% source
interval and the independent binder/admission chain succeeds. If its measured
rate is outside the closed old endpoint-rate range, it must be retained but may
not drive another request. At most two later midpoint requests remain after the
initial refinement.
