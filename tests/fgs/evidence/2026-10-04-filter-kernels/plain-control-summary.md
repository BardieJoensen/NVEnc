# Matched plain controls

All 21 synthetic fixtures and five real clips now have accepted plain NVENC controls within 3% of every known compatible FGS bitrate in the identity evidence. The largest difference is Amphibia at +2.891%. This completes the matched-size control requirement for these measurements; it does not establish grain quality or resolve the separate identity gate.

| Real clip | Known FGS payload kb/s | Accepted plain payload kb/s | Largest difference |
|---|---:|---:|---:|
| LostTapes | 2852.231–2852.233 | 2841.144 | −0.389% |
| Taxi HDR | 22553.566–22580.156 | 22750.737 | +0.874% |
| Amphibia | 2693.516 | 2771.397 | +2.891% |
| Gentlemen | 1981.874–1992.312 | 2035.624 | +2.712% |
| Silo | 1392.863 | 1374.154 | −1.343% |

The 21 KAT controls all pass; their largest absolute difference is `retain_10bit` at −2.665%. KAT controls come from `kernels-kat-plain-controls-v2`; LostTapes and Taxi use the five repeated controls in `kernels-real-identity`; Amphibia and Gentlemen use accepted retuned controls; Silo uses QVBR 32.32031250 from trial 8 of `kernels-silo-plain-qvbr`. Silo retains the production maximum bitrate of 50,000 kb/s. The clean synthetic fixture uses plain CQP 20, and KAT VBR controls use the documented explicit maximum bitrate to avoid the default level cap.

The audit covers 34 accepted runs. Each retained IVF was reparsed and hashed, its source/binary pins and effective arguments checked, and its saved strict libdav1d grain-off decode verified for pixel hashes, depth and frame count. No source media was reopened and no encode or decode was launched. Every known FGS rate from both admitted arms and historical/profile campaigns was checked, not only a median.

`plain-control-summary.json` records exact targets, requested rates, actual payloads, all known FGS states, deviations, arguments, artifact hashes and source-report hashes. Earlier unmatched, interrupted and superseded calibration attempts are listed separately. Original reports remain unchanged, including the identity aggregate's independent pending status.

The offline generator is `/tmp/downloads/codex-work/fgs-improvement-20261004/summarize_plain_controls.py`. It reads the explicit reports named in the script and verifies retained artifacts; it refuses to overwrite an existing summary. The generator uses the frozen `aggregate_identity.py`, `repeat_identity.py` and `identity-requirements.json` beside it. Their hashes and the final JSON/Markdown hashes are recorded in `plain-control-summary-freeze.json`.
