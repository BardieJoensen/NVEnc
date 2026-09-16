# September 16 follow-up encoder review

The deployed ordinary encoder remains `cb903a17`, SHA-256
`06dd65fc00773536f76d09eaf49b1d18032808742e8e13d8037262475c73af7c`.
This review found and corrected two release-harness defects. It did not find a
new encoder defect or establish further damaged library files. No encoder
binary, Tdarr flow, routine validation budget or worker limit changed.

The source-supported amplitude check previously measured only the diagonal
component of native 2x2 texture. Horizontal and vertical stripes of +/-0.8
normalized luma codes can have zero diagonal energy and zero displayed 8x8 mean
error while staying below the unchanged three-code synthesis cap. All 28 axial
examples, covering stripe widths 1/2/4 and every phase, incorrectly passed the
old check. The reproduction and old harness are retained privately.

The correction measures orthonormal horizontal, vertical and diagonal Haar
bands at 2-, 4- and 8-pixel scales on the same source-selected tiles. Each band
must pass independently; a deficit in one cannot hide excess in another. The
existing source coverage, picture-error and synthesis limits are unchanged.
Reports use assessment version 2 and explicitly name all nine bands. Independent
source-supported random grain still passes. Axial stripes, diagonal controls at
each scale, direction substitution, excessive noise, coarse overlays, base blur
and absent source coverage are rejected.

The second defect affected `local_gate.sh`: one executed, failed stage and no
passing stages returned exit 2 with “nothing ran”. It now returns exit 1 and
reports the stage failure. Empty execution still returns exit 2. An integration
test runs the real shell preflight/selection/summary with a deliberately failing
GPU witness stub; the previous shell fails this regression.

The full CPU suite passes, including 16 amplitude tests and 14 harness tests.
A fresh private-media release stage verifies the exact deployed binary hash,
four distinct source/control/output hashes, unique matching timestamps and
explicit grain-on/off decoding. Both retained Play Dirty witnesses pass all
nine texture bands; both known excessive-grain negatives fail all nine.

| Witness | Pictures | Current peak synthesis RMS | Negative peak synthesis RMS | Current bands passed |
|---|---:|---:|---:|---:|
| City, 856.333 s | 12 | 0.000 | 24.289 | 9/9 |
| Dialogue, 5727.583 s | 12 | 0.681 | 7.915 | 9/9 |

The stronger check does not replace temporal grain, picture-detail, chroma,
HDR or full-file checks in the existing 449-artifact qualification. The same
two SDR witnesses cannot clear the rest of a film or library. Original
qualification and failed reports remain unchanged. Evidence for this review is
under
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/followup-20260916/encoder-review-20260916/`:
`before/`, `cpu-final/run.json`, `amplitude/gate/amplitude-regression/report.json`,
`health.json` and `report.json`.

The runtime/source-history review found no additional ordinary-mode release
blocker. Optional `retain=auto` remains a separate development task: update the
prepared manual comparisons to the current ordinary baseline, reproduce the
selected fallback cases, then measure visible quality at matched actual byte
budgets before a size policy or broader rollout. Earlier 20–30% size costs are
historical measured arms, not measurements of this current build. No trial was
started automatically. FEL remains disabled and its restored originals remain
protected. The separate library review and source holds are not closed by this
encoder check. The deferred FFprobe XML investigation remains deferred.
