# Private real-film fixtures

The local GPU gate verifies every required input against [fixtures.json](fixtures.json).
The default directory is `/media/merged-storage/validation-fixtures/nvenc-fgs/v1`,
outside the disposable `media/test-encodes` tree. Override its location with
`FGS_GATE_FIXTURES`; the expected hashes remain fixed. Media is not committed.

```sh
python3 tests/fgs/fixtures.py
tests/fgs/local_gate.sh --full --candidate-commit HEAD --denoiser bilateral
```

Missing or changed inputs stop the gate. Restore the exact files from this
directory's backup, or reconstruct them from the original sources and commands
recorded in the manifest. A different cut, decoder, or generation may produce
different bytes. Do not update hashes merely to make the gate run: a replacement
must be revalidated against both the known-bad and corrected controls.

| Files | Purpose |
|---|---|
| `taxi-coarse-24f.mkv` | 24 original-source HEVC frames at 1365.5658 seconds; coarse 4K grain, texture and base-fidelity controls |
| `alien-coarse-24f.mkv` | 24 original-source HEVC frames at 1200 seconds; coarse 4K oracle |
| `silo-fine-24f.mkv` | 24 original-source H.264 frames at 1200 seconds; fine 1080p oracle |
| `taxi-source-6f.y4m`, `taxi-clean-6f.y4m`, `taxi-reference.tbl` | First six Taxi frames and the pinned r4050 bilateral clean base/model |
| `taxi-metric-gamer.json` | Unmodified historical adversarial model, previously named `taxi_ceiling_q.json` |
| `taxi-widened-r4047.mkv` | Rejected r4047 encoder's output from the same pinned Taxi clip; file-mode negative control |

The FFV1 clips preserve decoded source pixels. The manifest records their hashes,
source locations, extraction commands, reference binary identities, and recovery
measurements. It also lives beside the media as `manifest.json`.

## Recovery on 2026-09-05

The old test-encodes fixtures were missing. The original Taxi Driver HEVC remux
survived, as did original-source Alien and Silo inputs. The available Casino
library file was already AV1; it was not reused as an original source. The active
real-film set is now Taxi, Alien, and Silo; historical Casino and The Shining
coverage is not claimed.

The recovered Taxi clip distinguishes the pinned rejected and corrected encoders
at the existing canary thresholds. Relative to the r4033 base reference:

| Binary | SSIMULACRA2 mean delta | Butteraugli mean delta | Verdict |
|---|---:|---:|---|
| r4047, rejected widening | -2.436 | +0.076 | ALERT, exit 1 |
| r4050, corrected control | +0.023 | -0.001 | ok, exit 0 |
| r4141, deployed at recovery | +0.023 | -0.001 | ok, exit 0 |

The unchanged metric-gamer also remains REJECTED on the recovered six-frame
pair: its gated ACF and radial-spectrum errors improve, while held-out
anisotropy and diagonal ACF errors regress. The incumbent remains accepted.
The full gate separately asserts encoded texture separation and degraded
base fidelity in the retained r4047 output.

`/opt/docker-apps/scripts/grain-base-canary.sh` uses the same pinned Taxi clip.
Its helper publishes a fresh running/error record if validation or measurement
fails, replacing any old successful result. It defaults to the deployed
`tdarr-node` binary; `GRAIN_CANARY_NVENCC` selects the exact local candidate for
the full gate. Canary encoding always uses the production bilateral settings.

The September 6 ripple fixtures add a lossless 150-second Gentlemen source
(starting at episode 33:00) and the d3008e74 candidate as a labelled negative.
That candidate passes the 0.95 pole-radius test but visibly synthesizes a
diagonal mesh at 34:24.5. `periodic_regression.py` must reject it and verify
that the tested candidate preserves source frames at 33:24, 34:06 and 34:24.5.
These private media files are stored only under the fixture root, with hashes
and extraction/encoder provenance in fixtures.json.

The September 7 whole-sequence regression also pins
`gentlemen-guard-positive-33m-150s.mkv`, the complete e778a88b output from the
September 6 release gate. Candidate and positive are independently rendered
through dav1d for all 3,600 displayed frames. Luma/red/blue patch measurements
check texture, amplitude and temporal changes, while the retained negative must
fail. The positive is a reviewed regression reference, not proof of perfect
texture everywhere. Changing its grain scheduling or amplitude requires explicit
review of a new baseline; do not regenerate it automatically from a candidate.

`hornets-invalid-chroma-1495-35s.mkv` retains original AV1 packets from an older
library output. Both dav1d and libaom reject a one-sided chroma grain model in
the passage. The syntax gate requires the specific chroma-rule failure, rather
than accepting an unrelated decode or model-quality error as its negative
control. The source encoder version is not established. The current encoder
and table parser already enforce paired 4:2:0 chroma; the scanner now does too.
