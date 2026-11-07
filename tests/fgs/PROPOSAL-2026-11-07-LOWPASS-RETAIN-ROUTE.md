# Proposal: low-pass residual retention in the AV1 FGS routes (2026-11-07)

Status: **proposal only.** Nothing is deployed, and the flow is unchanged. The user decides.

## What changes

Branch `exp/fgs-lowpass-retain-20261107`, commit `7df761c8`, is the production commit `f1327e14` plus one option.

`--av1-film-grain ...,retain=0.9,retain-lp=3` adds `0.9 × G₃(orig − clean)` back to the denoised luma before encoding:
- `G₃` is a Gaussian blur with sigma 3 px, so only the smooth part of what the denoiser removed comes back.
- Fine grain stays with synthesis, at full strength.
- Chroma is untouched.

With `retain-lp` absent or 0, the filter output is byte-identical to `f1327e14`. This was checked by md5 for retain 0 and 0.5. In 48 control encodes, the encodes were byte-identical as well.

## Why

Plain `retain=` restores real detail, but it puts grain back into the luma. NVENC then codes the colour worse, and no flag fixes that; this was shown in [FINDINGS-2026-11-06-RETENTION-REOPEN.md](FINDINGS-2026-11-06-RETENTION-REOPEN.md) on `fix/fgs-clean-source-20261006`. Retaining only the low-frequency part avoids the colour loss.

## Evidence

Both runs measured equal size against the production ladder at QVBR 30. The rules were frozen before results.

| | Dev, 12 grain windows (`reports/lpretain-measure-20261107`) | Reserved corpus, 9 windows (`reports/lpretain-qual-20261107`) |
|---|---|---|
| Luma structure err_Y3 | better 12/12, median −0.0020 (plain retain −0.0008) | better 9/9, median −0.0005 |
| Colour amp/peak within 0.002 | 12/12 (plain retain 3/12) | 9/9 |
| HF ratio, acf1 | flat | flat |
| Butteraugli p95 | +0.00 | −0.04 (tf2 +0.80, pan3 +0.40) |
| vmaf_p1 | +0.91 | +0.27 |
| Size at fixed QVBR 30 | +0.5% median (−2.1 to +1.8) | +0.18% median (−0.6 to +0.6) |

The gain is largest on grainy 35mm film, small on WEB, animation and 4K digital, and never negative on err_Y3. The encode is about 4% slower on the filter's side.

## Proposed route rule

Use the same string in all three FGS routes of `configs/tdarr-flow/flows/AV1NVENCflow1.json`:

`--av1-film-grain denoise=auto,chroma=auto,denoiser=bilateral,retain=0.9,retain-lp=3`

There is no per-class split, because no class was hurt.

## Library size impact

New transcodes only; nothing is re-encoded. Expect about +0.2 to +0.5% per file at the same QVBR, so the library grows by under 1% over time.

## Steps before it can go live (each needs the user)

1. **Blind TV review** of the set in Nextcloud, folder `FGS lowpass retain AB 2026-11-07`. Ship only if the review prefers the candidate, or at least shows no loss.
2. Add a `retain-lp` known-answer case to the GPU fixtures. That is: retained part ≈ 0.9 × G₃ residual, chroma unchanged, synthesis unscaled. Then run the full release gate with the option on. The canary stages currently cannot run because their pinned reference images are gone; coord `nvenc/fgs-gate-reference-images` tracks this.
3. **Build and deploy** a tdarr-node image whose nvencc is built from this branch, using `scripts/tdarr-node-safe-redeploy.py`. The binary must be in place before the flow change, because an older nvencc rejects `retain-lp`.
4. **Flow change:** one string, three routes, committed in docker-apps.

## Rollback

Revert the flow string; the new binary with the option off is identical to production. If the binary itself is suspect, redeploy the previous image `nvenc-fidelity/tdarr-node:3.01.00-f1327e14-20261016`.
