# Repeat variability with FGS disabled

The deployed encoder produced two different results from the same 240-frame, 1080p Gentlemen clip with identical settings and film grain synthesis disabled. The second result was 7,217 bytes smaller (0.282%), and every decoded picture differed. This means repeat variability can happen without FGS, so later library comparisons must account for encoder variation instead of treating a single changed output as evidence of an FGS change.

The completed plain-control rows use the deployed `c6cbd528…` binary and source `e41e63a9…`, software input decoding, seek 60 seconds, 240 frames, 10-bit AV1, VBR 1992 kb/s, quality/HQ, lookahead 32/level 3, and spatial plus temporal AQ. Their arguments match exactly except for the output filename. No film-grain options occur. Both logs list only the two color-conversion filters. Source identity is established by the existing pinned run receipts; source media was not reopened.

| Observation | Repeats 1–3 | Repeats 4–5 |
|---|---:|---:|
| IVF MD5 | `4c3e3c66b96840249fccc353ce1424d2` | `166569b5fca561739f8f8f4e1e99fe61` |
| Grain-off pixel MD5 | `c7c35aacc78ddf06afb67391b2b72829` | `543619482b1ad114f1048f3eaeb84edd` |
| IVF bytes | 2,556,264 | 2,549,047 |
| Video payload kb/s | 2042.6816 | 2036.9080 |

The first difference occurs at packet 0 and decoded picture 0, using zero-based indices. Of 240 packets, 121 differ; all 240 decoded pictures differ. Packet timestamps are identical. Retained IVFs were reparsed and rehashed, and their saved strict libdav1d grain-off hash files were checked against the report. The full receipt, exact arguments, artifact SHA256 hashes, and first differing hashes are in `gentlemen-plain-variability.json`.

FGS processing is not necessary for the observed variation in this case. This does not establish that every FGS-related variation shares a cause, prove identical surfaces reached NVENC, or identify a driver defect. No new encode, GPU operation, or source-media read was performed.
