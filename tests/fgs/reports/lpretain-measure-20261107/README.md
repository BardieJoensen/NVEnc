fgs-lpretain-measure (2026-11-07): retain-lp vs prod at equal size, 12 windows, 5 arms x QVBR 26/30/34.
Scripts: common.py prep.py cut.py metrics.py run.py summary2.py (copies from branch fix/fgs-clean-source-20261006 retention-chromaqp-20261107, paths/encoder adapted); src/ = originals + control results.json.
Encoder: nvencc-lpretain-ff65b832 via docker nvenc-fgs-build:cuda13.3-deps. Rebuild: python3 cut.py; python3 run.py. Keep: results.json, summary.md, q30 encodes in win/*/enc.
Results: results.json, summary.md (python3 summary.py). q30 encodes kept; q26/q34 encodes deleted. Run took ~58 min (12 windows x ~4.5 min).
