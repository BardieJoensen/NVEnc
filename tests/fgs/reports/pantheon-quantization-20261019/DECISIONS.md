# Decisions

- auto: reuse validated procedures and prior source/metric identities; rebuild only affected scratch paths. Stage1 first, absolute quantizer intervention second, budget test only after convincing preservation.
- auto: bound synthesis to same-frame representability under hard source-clean constraints before another fit.

- auto: E05 fixed-decision qindex 48 scalar reconstruction restores little shirt HF (0.146 versus 0.606 source); use one real CQP 4 / AQ off diagnostic to force substantially lower realized qindex without rate-control compensation. Retain preset/tune/input/FGS settings. Decide any further encode from realized maps and texture, not requested QP.
