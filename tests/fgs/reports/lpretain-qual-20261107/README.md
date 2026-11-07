fgs-lpretain-qual (2026-11-07): qualification of retain=0.9,retain-lp=3 vs prod FGS on 9 reserved windows (bear1-3, pan1-3, tf1-3), 2 arms x QVBR 26/30/34.
Scripts (copied from ../fgs-lpretain-measure, adapted): common.py prep.py metrics.py run.py summary.py. Rebuild: python3 prep.py; python3 run.py; python3 summary.py.
Encoder nvencc-lpretain-ff65b832 (docker nvenc-fgs-build:cuda13.3-deps), prod args as in the measure run. Keep: results.json, summary.md, manifest.json, q30 encodes in win/*/enc.
Added vs previous run: sigma 6 (amp/err_Y_s6.0), ssimu2 mean (already from campaign.score).
tf (Transformers TLK): DV P7 base layer decoded by ffmpeg to FFV1 yuv420p10le from a copy-cut (keyframe preroll), first half of its frames (~150); bt2020/smpte2084/bt2020nc tags set on cut and passed to nvencc (--colorprim/--transfer/--colormatrix). That cut is encode input and reference (ffvhuff ref10 for FFVship).
Scoring in native PQ: no tone-mapping; vmaf 4k model (vmaf_4k_v0.6.1) and FFVship fed the 10-bit PQ-coded yuv directly, identically for both arms. Grain stats use same pixel sigmas (3/1.5/6) at 4K as at 1080p.
Windows: 25/50/75% (bear, pan), 30/55/80% (tf); +60 s once when >50% scored frames had active-area mean luma <32 (see manifest shift_note).
