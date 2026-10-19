# Evidence and playback packet

Final archive: `/media/merged-storage/cold-storage/docker-apps/pantheon-rd-20261019`. Prior archives remain immutable.
`archive-receipt.json` records verified relocation, manifest and cleanup results.
`SHA256SUMS` in the archive covers every retained evidence file except itself;
verify from the archive root with `sha256sum --quiet -c SHA256SUMS`.

## Minimum decisive playback

Record blind labels before opening `viewer-key.json` or named full streams.
No investigator has observed motion playback. These clips enable that required
external check; they do not imply perceptual acceptance.

- [E04 packet instructions](/media/merged-storage/cold-storage/docker-apps/pantheon-rd-20261019/parent/playback/e04/README.md):
  [purple texture](/media/merged-storage/cold-storage/docker-apps/pantheon-rd-20261019/parent/playback/e04/purple.mkv),
  [source-selected quiet context](/media/merged-storage/cold-storage/docker-apps/pantheon-rd-20261019/parent/playback/e04/quiet-context.mkv),
  [post-hoc worst quiet context](/media/merged-storage/cold-storage/docker-apps/pantheon-rd-20261019/parent/playback/e04/quiet-tail-context.mkv).
- [E05 packet instructions](/media/merged-storage/cold-storage/docker-apps/pantheon-rd-20261019/parent/playback/e05-1440/README.md):
  [shirt](/media/merged-storage/cold-storage/docker-apps/pantheon-rd-20261019/parent/playback/e05-1440/shirt.mkv),
  [background](/media/merged-storage/cold-storage/docker-apps/pantheon-rd-20261019/parent/playback/e05-1440/background.mkv),
  [face and scratches](/media/merged-storage/cold-storage/docker-apps/pantheon-rd-20261019/parent/playback/e05-1440/face.mkv),
  [source-selected quiet context](/media/merged-storage/cold-storage/docker-apps/pantheon-rd-20261019/parent/playback/e05-1440/quiet-context.mkv),
  [post-hoc worst quiet context](/media/merged-storage/cold-storage/docker-apps/pantheon-rd-20261019/parent/playback/e05-1440/quiet-tail-context.mkv).

Each native crop loop is240 frames, approximately10 seconds, FFV1/10bit BT709
limited with exact all-plane panel hashes. E04 has source/4x, E05 source/3x/4x.
At100% zoom, assess whether fine texture moves naturally or freezes/boils/pumps,
whether source-clean areas gain visible noise, and whether lines, scratches,
grid boundaries, ringing or banding change. The worst-quiet contexts are selected
after outcomes from the maximum signed HF excess across frozen source-quiet
tiles; they are stress diagnostics, not a new gate or an unbiased confirmation.
E04 focus: scored7.007s/frame168, tile(1640,1016). E05:1.000s/frame24,
tile(1304,1016). In both stress clips that32x32 tile starts at(96,100) within
each labeled panel, including the header.

Then compare full picture at normal viewing distance in the actual player:

| Fixture | Lossless original-derived reference | Actual measured H264 streams |
|---|---|---|
| E04 | [source336](/media/merged-storage/cold-storage/docker-apps/pantheon-rd-20261019/parent/playback/e04/source-full336.mkv) | [4x candidate](/media/merged-storage/cold-storage/docker-apps/pantheon-rd-20261019/parent/crosscodec/e04/x264-search11-4x1/out.mkv) |
| E05 | [source336](/media/merged-storage/cold-storage/docker-apps/pantheon-rd-20261019/parent/playback/e05-1440/source-full336.mkv) | [3x comparison](/media/merged-storage/cold-storage/docker-apps/pantheon-rd-20261019/parent/crosscodec/e05-1440/x264-search11-3x1/out.mkv), [4x candidate](/media/merged-storage/cold-storage/docker-apps/pantheon-rd-20261019/parent/crosscodec/e05-1440/x264-search11-4x1/out.mkv) |

These contain336 frames; scored content starts4.004s(E04)/4.000s(E05).
Record player, display, scaling and processing; report which labels show an
artifact and its time/region, and whether E05's3x-to4x difference is visible at
normal distance. Quiet-tail full-stream times are11.011s(E04)/5.000s(E05).
The approximately4x bitrate and measured5.47–6.72 wall-seconds per input-second
also require an explicit practicality decision. No production proposal follows
from numerical screens alone.

## Evidence map

| Retained archive location | Purpose |
|---|---|
| `fixtures/*/validity.json`, `fresh-validation.json` | Untouched-original identity, exact frame/color input validation |
| `parent/measured-svt/` | Exact measured binary/source tar,607-source-file audit and fingerprints |
| `raw-evidence.tar.zst`, `raw-evidence-members.json`, `raw-evidence-validation.json` | Hash-verified original coefficients/predictors/quantizers/recons/entropy trace records and H264 QP CSVs |
| `parent/e04-entropy/`, `parent/e05-1440-entropy/` | Accepted entropy clone identity/population controls and summaries |
| `parent/real/` | Actual selected-q/FP strategies, packet/quantizer/retention evidence, streams |
| `parent/crosscodec/` | Real H264/HEVC streams, effective options, both pass logs, packets, controls, independent decoder and grid evidence |
| `parent/h264-qp/` | Validated full-frame QP maps, export receipts and allocation analyses; packed CSVs are in raw tar |
| `parent/scores/` | Campaign commands, versions/hashes, full per-frame GPU metrics, tails, source/score identities, all240 texture traces |
| `parent/summary/` | Complete results and standalone texture frontier/temporal plots |
| `parent/visuals/`, `parent/playback/` | Native stills, synchronized crop loops, exact panel validation, full references and blind keys |
| `worker/ATTEMPTS.md`, `worker/rejected-source.tar.zst` | Rejected instrumentation retained for methodological audit only |
| `report-source/` | Final report/scripts snapshot; repository commits remain authoritative |
| `retirement-preflight.json`, `retirement.json` | Jobs/mounts/schedules/worktrees checks and removed reproducible files |

[Reproduction](REPRODUCE.md) explains dependencies, patch order, exact4x commands,
calibration and extraction. [provenance.json](provenance.json) binds the original
fixtures and candidate streams. [results.json](results.json) contains measured
rates, runtime scope, controls, quiet signed tails and upstream evidence hashes.
Historical logs retain scratch paths; remap them to fresh scratch when replaying.
Full raw decodes, Y4M inputs, builds and the analysis venv were reproducible;
retained streams, source snapshots and manifests preserve the useful evidence.
