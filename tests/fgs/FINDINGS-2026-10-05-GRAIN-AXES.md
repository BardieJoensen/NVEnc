# Grain amplitude, size and brightness response

Production still loses grain energy and changes grain size on the short 4K HDR Taxi fixture: played luma amplitude is 32% below the source, while HF energy is 12% lower and lag correlations also fall. Both chroma planes lose amplitude and correlation. A separate controlled fine-grain test gives amplitude-response slopes near one, not the historical 0.63. These measurements support further coarse-grain work eventually, but the confirmed additions to clean 1080p regions are the higher priority for this library.

## Ruler and sample

This is measurement of the deployed `aeb14263` binary, not a candidate quality improvement or a matched-bitrate comparison. The same-bitstream grain-on/off decodes, source-only selection, every-frame scoring, clipping controls and held-out sample are described in [clean-source findings](FINDINGS-2026-10-05-CLEAN-SOURCE-GRAIN.md). No additional plain controls were run; they belong to the proposed future quality comparison.

All fifteen held-out windows have per-frame, per-luma-band Y/Cb/Cr amplitude, HF sigma and horizontal/vertical lag 1/2, with occupancy and selection coverage. The supporting original regression windows are 32 Lost Tapes frames, 32 Gentlemen frames and 24 TaxiHDR frames. Taxi is a 3840×2160 PQ FFV1 reference decoded from the original base layer, with FEL off; it is not library AV1 or a throughput workload. SDR and PQ remain separate, and chroma lags are measured in native chroma samples.

The spatial amplitude removes a fitted plane; HF sigma uses the calibrated cross-neighbor residual. They measure spatial residuals that can include picture texture, not perfectly separated natural grain. Source-only core selection uses the least structured quarter within each occupied band, with an expanded 60% sensitivity mask and a minimum of eight patches for band-level inference; constant-patch safety uses neither restriction. The reported occupancy is conditional on source-selected measured bands, not a statement that the entire frame is a flat grain field. Source-self and quantity-only generated controls passed before media conclusions.

## Supporting original-source numbers

The table combines measured bands by their source occupancy and averages energy before taking the square root. All strengths are in 8-bit-equivalent native code values; this is not an SDR/PQ perceptual normalization.

| Window / plane | Source amplitude | Played amplitude | Source HF sigma | Played HF sigma |
|---|---:|---:|---:|---:|
| Lost Tapes /Y |3.221|3.146|0.865|0.745|
| Lost Tapes /Cb |0.364|0.339|0.114|0.107|
| Lost Tapes /Cr |1.546|1.525|0.313|0.266|
| Gentlemen /Y |2.245|2.086|0.538|0.454|
| Gentlemen /Cb |0.713|0.614|0.257|0.119|
| Gentlemen /Cr |0.834|0.728|0.317|0.136|
| TaxiHDR /Y |2.247|1.536|0.641|0.566|
| TaxiHDR /Cb |1.351|1.021|0.715|0.643|
| TaxiHDR /Cr |0.699|0.453|0.350|0.286|

HF must be read with correlation. In Taxi's luma band 32–64 (about 35% occupancy), source versus played horizontal lag 1/2 is 0.772/0.366 versus 0.697/0.292. Cb is 0.585/0.147 versus 0.382/−0.061, and Cr0.590/0.172 versus 0.386/−0.032. The 64–96 band (about 38%) agrees in direction. Thus the result has lower amplitude **and** less correlated, finer texture, particularly in chroma; a single HF score would hide much of this error.

On Gentlemen's digital material, the opposite correlation movement accompanies HF loss: Cb in 32–64 has horizontal lag 1/2 rising from 0.658/0.394 to 0.850/0.622. That is consistent with smoothing of source residual structure, but this source selection cannot assign all of it to photographic grain. Likewise, an animation drawing's spatial detail is not evidence for adding synthetic grain. Do not rank titles by their aggregate amplitude deficit alone.

The 24-frame HDR witness has limited temporal coverage and a short model history. It demonstrates a finite production discrepancy, not a4K-library prevalence estimate, a format ceiling, or a measured quality/size improvement. A separator or coarse-grain proposal needs its own causal experiment after clean safety.

## Does source^0.63 still hold?

A quantity-only control varies overall grain amplitude at 0, 0.5, 1, 2, 4, 6 while retaining the same random white-grain field, static flat panels, geometry, frame count and production QVBR30 command. Its 960×540 panels cover luma 48, 80, 112, 144, 176, 208; Y/Cb/Cr amplitudes vary together. Each encode has 96 frames and the last 32 are measured, with no fitted parameter changed between levels. The zero-grain control stays zero in every measured plane/band.

| Plane | Per-band fitted positive-level exponent | Played/source amplitude at strongest level |
|---|---|---|
|Y|0.975–0.993|0.923–0.935|
|Cb|0.983–0.996|0.903–0.931|
|Cr|0.983–0.991|0.922–0.937|

At the 0.5 level, Y ratios range0.958–1.002, Cb0.947–0.969 and Cr0.962–0.978. The test therefore does **not** reproduce a broad low-grain boost/heavy-grain compression with exponent 0.63 for fine white grain. It does show roughly 7–10% strongest-level amplitude loss and small negative lag correlations where the source is nearly uncorrelated. The historical claim is not disproved for other grain sizes, source estimators or histories; its exact August fitting procedure was not recovered. Do not fit a population exponent by pooling unrelated textured scenes, animation and PQ code values.

## Retained evidence and priority

`task4/axes-report/all-window-band-axes.csv` has 2,892 rows covering both masks, all measured bands, all four layers and all 18 windows; `amplitude-control.csv` has 108 plane/band/level observations. The source census hashes, raw-alignment receipts, mask reviews and full per-frame files are preserved under `/tmp/downloads/codex-work/fgs-submission-20261005/`. The branch retains the compact tables, receipt bundle and exact measurement tools.

No population weighting beyond the user's91%1080p GPU-hour fact is justified by these sources. The strongest supported priority is unwanted synthesis across clean digital/animation regions, then the confirmed temporal excess. Coarse HDR amplitude/size and weak digital chroma residuals follow; a new global amplitude compensation does not have supporting evidence. See [the bounded fix plan](CLEAN-SOURCE-FIX-PLAN-2026-10-05.md).
