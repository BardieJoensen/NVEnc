# R15 independent outcome review

## Evidence and independent derivation

Contract: `ROUND15_REAL_CONTRACT.md` SHA256 `65abe8440193c14cd4925961f2cf712081e2c9876d18de8ab90440ac8d5099f3`.

Native admission: `parent/psyex-real-r15/admitted-1/admission.json` SHA256 `10e7bc21ae29e3913fc022ae0d472929b829df0ef3cd6393fef46aa08cf66ecf`. Encoder receipt: SHA256 `8234fcf3c6c8d69522646d6e4b34973639dcdbce30696f4bb0474b583630996a`. Stage diagnostic: SHA256 `52f50218e8bc873db29b9a7feab71361183a238cce4e93a7f6280ff80f300c4f`.

I independently loaded the admitted native surfaces, reparsed the admitted token manifest's committed fields, and recomputed the fixed-ROI descriptors with the pinned descriptor helper. Script `reviewer/round15-outcome/derive_admission.py` SHA256 `f683a77dc971bf242df4a6de4a24d920689f0aaf257b1264e35da891635bb5a5`; result `admission-check.json` SHA256 `c56c155ec347019c8b85b961fcc9cd6a9759ab2ab4bacdfc9bdea09bbb1adcec`. Command:

```text
/usr/bin/nice -n 10 /usr/bin/taskset -c 8-11 analysis-venv/bin/python derive_admission.py admission-check.json
```

## Native delivery observations

- The independent syntax lifecycle binds display 216 to hidden coded event 314/coded ordinal 210/order hint 88/refresh slot 4, and the exact packed OBU is joined through encoder and decoder observations. Neutral off/on replays reproduce the unmodified IVF and reconstruction. All 336 independent decoder outputs agree.
- The target coding input is byte-identical to the untouched original on all planes. The admitted target preloop and postloop are byte-identical; thus this frame has no observed loop-filter sample change. This does not establish that filtering is inactive or immaterial across other frames.
- All 4,809 traced final committed tokens are non-skip, EOB-positive coefficient-bearing TUs. Every traced shirt, background, and face pixel is covered by an invoked final quantizer with actual/committed qindex 4; no traced pixel is above q4. Encoder DQ, EOB, effective IQM, q, source, predictor, and preloop join the normative decoder exactly within the explicitly traced population. This proves public QP1 delivered q4 there; it does not describe every TU in all 336 frames.
- On frame 216, the original/coding-input shirt has HF sigma 0.606320 and ACF1 -0.222415. The final/postloop surface has 0.577348 and -0.193460 (HF ratio 95.22%, ACF error 0.02895). Background changes from 1.676388/-0.178995 to 1.650112/-0.172056 (HF ratio 98.43%, ACF error 0.00694). These independently reproduce the admitted stage report and pass the prescribed numeric screen for this one frame. They are not the five-frame acceptance screen.
- The fixed-decision stage diagnostic shows near-original raw reconstruction, then the main remaining local error appears at scalar q4; later optimize/noise stages make comparatively small nonmonotonic changes. Because R15 allowed coding decisions and references to change while also changing source preprocessing and quantization, comparison with R8 does not isolate any one cause. Stage descriptors are nonlinear and are not additive loss attribution.

## Rate and runtime observation

The scored packet window is 190.4115432 Mbps versus the 9.6765224 Mbps original cap: 19.6777× source. Two-pass wall time is 692.477 seconds. The arm is therefore neither a practical candidate nor a matched-rate comparator regardless of its eventual quality result. Requested TBR 10,313 kbps did not constrain the stream under the public min/max QP1 bound.

## Full-window quality

Fresh scorer execution 2 completed with return code zero; receipt SHA256 `9c21f322f656e907b87f948d92ad23115b3fa9c68f86a6ab744f1baa3af193a0`. Assessment SHA256 `a099d5799c7bbc4d218043d0dd79267c03c892b02f8a7def81515bb9e54ad1e5`; controls SHA256 `4cc7aed424ba59923ac701959da60cf6f4055396f0987a5ca221960f571886c4`; campaign result SHA256 `2597792b19ae4e0b3790d1d58395d7be642ad3cfd7d236f3e50b96515470bc7c`. The preserved scorer execution 1 stopped before metrics on a receipt-schema comparison and carries no quality outcome.

I independently summarized all 240 texture/campaign rows and the 51 frozen quiet rows with `reviewer/round15-outcome/derive_quality.py` SHA256 `45d1125cdf888ea3b77ab4a47a0d7e66ddeb966a8f8d6a91aa55508a9a992ce8`; result `quality-check.json` SHA256 `f04b22193aa2fd676f5b18728c28e8b9e8657fbd16d19162823310a4b22aca7f`.

### Prescribed texture screens

The five-frame midpoint screen passes both predeclared ROIs:

| ROI | HF relative error | ACF1 absolute error | paired source HF correlation |
|---|---:|---:|---:|
| Shirt | -3.622% | 0.02189 | 0.93081 |
| Background | -1.427% | 0.00542 | 0.98936 |

This is a clear numerical preservation result under the unchanged ±10% HF/0.05 ACF criteria. It is not solely a favorable five-frame mean: across all 240 rows, shirt HF relative error ranges -8.760% to +1.690% (p95 +0.789%), and background ranges -5.362% to +0.484%. Shirt ACF error has mean 0.00618, p95 0.02122, and maximum 0.05528; that one maximum exceeds 0.05, but no all-frame maximum gate was preregistered. Background ACF maximum is 0.03789.

Temporal texture traces are also close descriptively. Across 239 transitions, absolute source-versus-candidate temporal-HF-correlation error is shirt mean 0.00415/p95 0.01415/max 0.03613 and background mean 0.00135/p95 0.00459/max 0.01032. These correlated traces are neither a motion-quality gate nor playback evidence.

### Frozen controls and tails

All 12,870 tile keys and source descriptors are exact. The independently reviewed R8 pairing (`controls-versus-r8-1.json` SHA256 `147b2a06989d58deda82123f951340837d11189a5b37368678c0bd59df545ef6`) shows R15 lowers MSE on every tile. Across all tiles, R15 MSE mean/p95/max is 0.0977/0.1688/0.2779; HF absolute-error mean/p95/max is 0.0307/0.0790/0.1784; ACF1 absolute-error mean/p95/max over 12,869 evaluable pairs is 0.0168/0.0631/0.3365. The result is not uniformly better than R8 on every descriptor: 41 HF-error pairs and 612 ACF-error pairs increase, even though the aggregate and tails improve strongly.

The source-predeclared quiet population contains only 51 tiles over 15 frames, with 50 evaluable ACF pairs. R15 quiet MSE mean/p95/max is 0.0267/0.0564/0.0628 and HF absolute error is 0.0172/0.0470/0.0666. Signed HF excess is negative on 41 tiles, zero on one, and positive on nine; mean is -0.01533, p95 +0.00615, and the maximum is +0.01066 at frame 200, x=920, y=728. Thus the quiet control does not indicate broad added high-frequency energy, but it contains a small positive tail and is not an exhaustive source-clean/noise test. Ten of 50 evaluable quiet ACF errors increase versus R8.

The fixed face check improves to MSE 0.07465, edge-gradient MAE 0.27432, and gradient ratio 0.99844. Campaign tails are likewise high quality: SSIMULACRA2 mean 96.21/min 94.30/p5 95.48; Butteraugli 2-norm mean 0.152/max 0.204 and max-distance p95 0.842/max 1.100; VMAF mean 99.64/min 97.35; PSNR-Y mean 59.54/min 56.21. CAMBI mean/p95/max is 0.0226/0.1326/0.5419 and `cambi_full_reference` is zero for all 240 rows. These measures do not reveal a broad edge, tail, or banding regression, but they do not replace motion playback.

## Interpretation

R15 is a successful **high-rate numerical feasibility diagnostic** and a failed practical repair. It establishes that this legal bundled PSYEX policy—TF disabled, public QP1 delivered as actual q4 over every traced target/control pixel, with prediction/partition/transform/reference decisions free to change—can preserve the two target texture statistics and substantially improve frozen full-window controls. It costs 190.412 Mbps, 19.678 times the original packet rate, and takes 692.48 seconds for two passes versus R8's 370.34 seconds. Therefore it is disqualified by the user's source-rate ceiling and cannot support a matched-rate superiority or repair claim.

The evidence does not isolate TF removal from global q4, establish a minimum sufficient precision/rate, show that selective q4 is affordable, prove every frame used q4, or imply an AV1/encoder limit. The exact frame-216 stage result localizes its residual numerical error under R15's chosen decisions; comparison with R8 cannot turn that into additive causal attribution because the decisions and references changed. Static panels were exported, but no actual player/display playback was observed.

## Cheapest next discriminator

Run the missing practical factorial arm once: exact admitted R8 PSYEX policy at the original packet budget with **only** `--enable-tf 0`, no public min/max-QP bound. Use fresh two-pass statistics and rate-only request calibration to land at or below 9.6765224 Mbps and within 1% of R8, then apply the unchanged full campaign and native target-frame observer. This is cheaper and more informative than immediately implementing a spatial allocator: it tests whether source-off search/reference/support changes alone can produce a qualifying candidate under the hard cap, while R15 shows that the same source policy is capable of preservation when precision is abundant.

Predeclare the interpretation. If it passes, it is the first source-budget candidate and still requires playback. If it fails with source-identical coding input but retained coarse q/skip support, the next justified mechanism is the already audited absolute per-SB cap applied consistently to MD and final EncDec, with rate compensation outside the frozen source-defined regions. If residual support grows but texture remains precision-limited, that same cap is directly motivated. If legal support remains absent despite source-off search, investigate the search/objective/partition decision rather than spending another quantizer point. This is one policy contrast, not a parameter sweep.
