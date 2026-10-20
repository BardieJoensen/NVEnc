# R15 PSYEX TF-off / q-bound diagnostic preparation

Status: **prepared, not executed**. This directory owns the new runner and
provenance plan. It does not modify the admitted R8 source, binary, build, or
runs. The diagnostic is allowed to exceed the original packet ceiling; that
makes any over-cap result an unconstrained precision deliverability diagnostic,
ineligible as a practical candidate. An under-cap result still requires every
quality and playback gate; matched-rate comparability is recorded separately.

The planned arm is E05-1440, 336 frames, two fresh passes, request `10313`
kbps, with the R8 policy unchanged except `--enable-tf 0`, `--min-qp 1`, and
`--max-qp 1`. `--tf-strength 1` and `--kf-tf-strength 1` remain in the common
R8 policy but are inactive when TF is disabled. A fresh pass-1 stats file is
required because these settings change the encoder path; pass 2 must consume
that unchanged snapshot. No `--qp 1` is added and AQ remains the R8 policy.

## Exact unexecuted command shape

After the runner's preflight and fresh output directory are approved, it will
run these commands sequentially (the script adds the complete fixed-policy
argv shown in `encode_r15.py`):

```text
nice -n 10 taskset -c 0-7 <R8 SvtAv1EncApp> -i <fixture input10.y4m> -n 336 \
  [all R8 policy options] --enable-tf 0 --min-qp 1 --max-qp 1 \
  --tbr 10313 --stats <fresh pass.stats> --pass 1 -b <fresh pass1.ivf>

nice -n 10 taskset -c 0-7 <R8 SvtAv1EncApp> -i <fixture input10.y4m> -n 336 \
  [same options and same stats] --pass 2 -b <fresh out.ivf> -o <fresh recon.yuv>
```

`encode_r15.py --preview r15-tf0-q1` creates no encoder output and is not yet
run. It is the only intended entry point. The script uses a fresh output under
`worker/psyex-r15-real/runs/e05-1440/`; all binary/source/build dependencies
remain read-only under `worker/psyex-r8/`.

## Provenance bindings

The runner binds the R8 app SHA `f4867ae287fa34cc50f927b7aa52611973adbc7231785117e5d32ce077b2461c`, private library SHA `cd408a2f31f871cf9da924dd943607e2b8aa2e5366e513fc82d959434414f20b`, source manifest SHA `8cf0314d5ee329b662c32021020c8299ef47bb87681d87508328c1b28eeb5c69`, measured-runner SHA `4cf939e20445e130970fdf09983a774e1f71adf1ea6240038cc557fe9ef66a7b`, and input SHA `232abb5ffee869be4bedf682aa103c166eb473bb3fdad5daf28956cca60148d4`. It checks the historical 336-frame input identity and color/header fields before any subprocess. The runner records both IVF and remuxed MKV packet windows for positions 96:336, full 336 reconstruction identity/size, stream geometry, 10-bit format, BT.709 limited color metadata, commands, logs, versions, linked-library resolution, hashes, and per-pass wall times.

The R8 baseline remains immutable. The script records exact before/after identity
maps and fails on drift, inherited loader/observer overrides, missing stats,
failed pass/remux/probe, or invalid cadence. It does not score quality. A later
R11 trace may be reused as a separate pass-2 observer only after this runner and
its output are independently reviewed; no observer is implemented here.

See `source-audit.md` for the source evidence and the important limitation:
public min/max QP bounds constrain frame/RC qindex calculations, but do not
establish every final TU's realized qindex.

## Review-only validation receipt

`encode_r15.py` pycompiled successfully without executing the encoder; the
pre-review script was preserved separately.
A no-encode preview was run with Python 3 as:

```text
python3 worker/psyex-r15-real/encode_r15.py r15-tf0-q1-preview2 10313 --preview
```

It exited 0 and produced only the prepared receipt at
`runs/e05-1440/r15-tf0-q1-preview2/command.json` (SHA
`e75e7c0235a1de90a73448eb4e0bd5401ae9ed40a7736bc8a455d0a0625da68f`) and a
script snapshot with the same final SHA. The receipt's pass-2 argv confirms
`--enable-tf 0 --min-qp 1 --max-qp 1 --tbr 10313`; no pass process was
started and no encode result is claimed.

## Contract/provenance correction

The runner now binds `ROUND15_REAL_CONTRACT.md` (SHA256
`65abe8440193c14cd4925961f2cf712081e2c9876d18de8ab90440ac8d5099f3`) and
records API default QP 35 from
`enc_settings.h:22` and `enc_settings.c:974`, then records predicted effective VBR static QP 30 from the explicit recalculation at `enc_handle.c:3877-3898`. Public QP 1 is explicitly documented as internal
qindex 4 via `md_process.h:1266-1271`; realized TU q remains unclaimed.
Additional cited source hashes are listed in `source-audit.md`. The practical
scope is the TF-off/public-QP-bound bundle as an unconstrained preservation
diagnostic; practical acceptance remains at or below the untouched original
packet ceiling.

The pre-review runner is preserved as `encode_r15-pre-review.py` (SHA256
`6588a0e6d0718a725ddaba7e776d445df80e4e9c3d10aa5c79a1b10adaa1f211`). The
revised runner SHA is `97ce1e2732946a59f4df5162f6c1d953849853ad43cc009180f7f566e0b656aa`.
A fresh no-encode preview exited 0:
`python3 encode_r15.py r15-tf0-q1-preview3 10313 --preview`.
Its prepared receipt is `runs/e05-1440/r15-tf0-q1-preview3/command.json`
(SHA256 `7c78d792add6aa0540bf8995445087863fa857856319fca852f8707e4eb08757`)
and records the contract/static-QP bindings. No encoder process was launched.

## Final rate-status correction

The reviewed runner now accepts exactly the prescribed `10313` kbps request. A
validated encode is always recorded as `status="encoded"`; measured packet
results separately report `within_source_ceiling` and
`matched_rate_comparable`. Overshoot remains diagnostic, while an under-cap
result still requires the full quality, decoder and playback admissions. The
runner no longer invents a `.995` target rate.

The preserved contract-review runner is `encode_r15-contract-review.py`; the
current runner SHA is `18201c3da613854e5d2a9072113fcf87e1a85b076f127f478d754a6e4dbb4c82`.
No-encode preview4 exited 0. Receipt: `runs/e05-1440/r15-tf0-q1-preview4/command.json`,
SHA256 `088a6e416ba694cf862727c047c47b7e40b3b8aacb3a1ba852e38ba8a591d549`.

## Static-QP provenance correction

The earlier draft incorrectly called `min_qp_allowed=4`
(`enc_settings.c:995-996`) the static QP default. That was a neighboring
field and is retained only in the preserved draft history. The corrected
source path is `enc_settings.h:22` (`DEFAULT_QP 35`) →
`enc_settings.c:974` (`config_ptr->qp = DEFAULT_QP`); VBR setup may later derive
an effective value, so the runner records 35 as the untouched default and
makes no effective-QP claim. The current runner places `--min-qp 1` and
`--max-qp 1` directly in `POLICY`, with no appended duplicate. It binds
`README.md` and `source-audit.md` in the identity-before/after map.

Current runner SHA: `37ac081cd34720e043018133e6bbef30d81a89efe5c9a4f3ab65a9ee320d3196`.
Final no-encode preview5 exited 0; receipt SHA256:
`ea32fb6214748423cfd61d93cf37b00e5c4c52040975f3bca12334107a5f5870`.
The preview receipt records static default 35, min/max 1, and the audit/README
hashes. No encoder process was launched.

## Effective VBR static-QP correction

The API default is 35, but it is not the effective VBR static QP. At
`enc_handle.c:3877-3898`, VBR recomputes it from normalized target bitrate.
For this arm, `10313*1000*60/(24*1920*1080) = 12.4336902006`, above the final
band threshold 8, so the predicted effective VBR static QP is 30. The runner
records all three distinct facts: API default 35, predicted VBR static QP 30,
and public bounds 1/1 (internal bound qindex 4). Realized TU q remains
unknown until the admitted trace; no effective-Q or quality claim is made.

Current runner SHA: `025b95e47e873e6e3230151483f6f04e8340cc8aea43c0aa1c7e792826f7158a`.
The final no-encode preview7 receipt is SHA256
`8e7034d48a1b8c5ab3ad9919231f445725fd930d62b1c3aa3dc938f326b4527f` and
contains the API/effective-Q metadata plus current README/audit identity pins.
