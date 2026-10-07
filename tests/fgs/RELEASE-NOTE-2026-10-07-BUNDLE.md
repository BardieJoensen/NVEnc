# Release note: FGS kernel speedup + clean-source fix (not deployed)

This release combines the qualified film-grain kernel speedup with a fix that stops grain being added to exactly flat luma (letterbox bars, black frames, flat fills, white skies) and to flat mid-level colour. It does not change file sizes materially and keeps legitimate film grain. It has not been deployed; the steps below are for the user.

## Artifact

- Branch `fix/fgs-clean-source-20261006`; runtime commit `e78e97f223f3cececc29ddcd47504e2dd828c4b7` (on qualified kernel runtime `a1ac278a`, itself on production `aeb14263`). Later branch commits change only tests, fixtures pins and documents.
- **Release binary** `nvencc`, SHA256 `46d6781cab9995de227ebe668765cb91869706bd8399f0c57a86ae4a6fcfdfb8`, at `/tmp/downloads/codex-work/fgs-submission-20261005/bin/nvencc-release-46d6781c`. It is a from-scratch build: fresh clone at `e78e97f2`, pinned submodules, new meson configure, all 230 targets, in `nvenc-fgs-build:cuda13.3` (`sha256:031ff182…`), 708 s. Version string `NVEnc (x64) 9.37 (r4389) … Oct 7 2026`.
- It is trace-identical to the qualified incremental build `5cb5a80ac98694aff71dfb9d7843d594a54bcc65d1cd9bf84baeeaa58e05f86c`: all 1,496 submitted frames match (full-pitch surfaces and exact grain objects) on 21 KAT and 5 real fixtures, so every measurement below applies to it.

## What changed

1. **Kernel speedup** (from the qualified candidate): bilateral shared-tile/tap work and full-block flat-metric specialization; about 0.12 ms less FGS GPU work per 1080p frame. On its own it submits pictures and grain parameters identical to production.
2. **Clean-source fix (variant D)**: exactly constant source luma is protected at every level (the old ≤20/≥232 exclusion is gone). Constant chroma loses the 0.25-code small-excess allowance but keeps production's active-luma requirement near black/white. Protection is held apart from production's quiet-chroma gate, and source is blended back only at clean-protected levels.
3. Opt-in submission tracing (`NVENC_TRACE_SUBMISSION`), off by default; keep it unset.

## Measured effects

| Area | Result |
|---|---|
| Flat luma (panels at 16/20/232/234, letterbox bars, all 15 census windows with full history) | zero added grain in the protected range; production added up to ~2 codes RMS on panels/bars and 0.83 on the Insidious witness |
| Flat mid-level colour (Knightfall, Homegrown witnesses) | zero; production 0.20–0.23 |
| Flat chroma near black/white | unchanged from production by decision: Insidious hair Cb 0.64, Toy Story sky Cr 0.29, about 1 code on Taxi bars |
| Legitimate grain (Lost Tapes, Gentlemen, 4K PQ Taxi) | all-band amplitude within ±0.2% except Taxi luma −1.7%; worst band −4.0% (Taxi luma 0–32; HF −11% there) |
| Fixed-QVBR bytes | Insidious full history +0.92%; Lost Tapes −0.6%; Gentlemen −0.1%; Taxi −0.8% |
| Equal-bytes FR metrics | VMAF/NEG/PSNR/SSIMU2 match production; Taxi Butteraugli max p95 +1.3 on 24 frames |
| Library-scan detector | Clean on full Amphibia and Lost Tapes episodes, as production |
| CPU tests | pass (119 Python, all C++) |
| Full gate (`local_gate.sh --full`, unchanged) | 22/23 on `5cb5a80a`; the periodic-stage change detector flagged the intended chroma change, which the user reviewed and accepted. After the baseline update (`733a4fe0`) the periodic stage passes with the release binary, and the mesh negative is still rejected |
| Submission trace vs kernel candidate | changes only in scaling-curve fields (and pictures alongside them); identical on 21 KAT + Silo |
| Throughput | not measured before release (see below) |

Evidence: [clean-source findings](FINDINGS-2026-10-06-CLEAN-SOURCE-FIX.md), [bundle qualification](FINDINGS-2026-10-07-BUNDLE-QUALIFICATION.md), [kernel qualification](FINDINGS-2026-10-05-KERNEL-QUALIFICATION.md).

## Throughput: measure from production after deployment

The quiet-GPU timing matrix was cancelled: it could only start with no other GPU work, which rarely happens on this host, and the expected gain is small. None of the Tdarr pause allowance was used; the remaining allowance is released and no pause is held by this work. Instead, compare production Tdarr job reports from a few days before deployment with a few days after, using `/opt/docker-apps/benchmarks/tdarr-throughput/encode_throughput.py --days N` (per-stage pipeline time and NVEncC fps). Report NVEncC fps by resolution class. Treat host load (other batch jobs cut fps by about 23%), the number of active Tdarr workers, Emby-yield pauses and the content mix as confounders, and record them for both periods. The kernel saving measured in isolation was about 0.12 ms of GPU work per 1080p frame.

## Risks and known limits

- The periodic stage's pinned positive is now the reviewed bundle output (`gentlemen-clean-source-positive-33m-150s.mkv`, SHA256 `da7f25e4…`, added to the validation fixture store; no existing fixture changed). A future candidate that changes texture again will need its own review.
- Letterboxed films lose luma grain synthesis at codes 12–20 (the bars' level); source grain is blended back there. On Taxi this cost 4% of dark-band luma amplitude and no bytes.
- NVENC still smears motion over flat black on some frames; grain then follows the decoded level. Production has the same.
- The Knightfall same-shot strength jump is unchanged (separate future slice).
- HDR evidence is one 24-frame 4K PQ fixture plus the Play Dirty gate history.
- NVENC repeat variability means IVF hashes are not a regression signal; use submission traces.

## Deploy (user-operated, existing `Dockerfile.fidelity` recipe)

The timing run was cancelled and no Tdarr pause is held by this work; deploy whenever the node is idle, with the safe redeploy script (step 4).


1. Copy `/opt/docker-apps/build/tdarr-node/` to a private staging context. Keep production's `nvencc` as `nvencc-aeb14263`, and copy the release binary in as `nvencc`; verify SHA256 `46d6781c…`.
2. In `Dockerfile.fidelity` change only the final encoder check (line with `c6cbd528…  /usr/bin/nvencc` → `46d6781cab9995de227ebe668765cb91869706bd8399f0c57a86ae4a6fcfdfb8`) and the labels: `org.opencontainers.image.version="2.94.02-nvencc-e78e97f2-opus16"`, `fgs.encoder.core="e78e97f223f3cececc29ddcd47504e2dd828c4b7"`, `fgs.encoder.sha256="46d6781cab9995de227ebe668765cb91869706bd8399f0c57a86ae4a6fcfdfb8"`. Leave the Tdarr application digest, base image, `fgs-scan`, `packet-audit`, `dovi_tool` checks, plugins and flow untouched.
3. `docker build -f Dockerfile.fidelity -t nvenc-fidelity/tdarr-node:2.94.02-e78e97f2-<date> .`, then verify the image's `/usr/bin/nvencc` hash and labels and run the existing release image/flow qualification and source canary. Keep `NVENC_TRACE_SUBMISSION` unset.
4. Update the `docker-compose.yml` image line with a dated comment naming the rollback tag, and deploy only with `scripts/tdarr-node-safe-redeploy.py` (never a plain `compose up` while encodes run).

## Rollback

Set the image back to `nvenc-fidelity/tdarr-node:2.94.02-aeb14263-20261004` and redeploy with `tdarr-node-safe-redeploy.py`. Verify `/usr/bin/nvencc` SHA256 `c6cbd5280440c62b51c3b43ced4570dad40295748d42f562a867ac6a525be72b`, the original node limits and the flow. Keep that image and both binaries until the rollback window closes.
