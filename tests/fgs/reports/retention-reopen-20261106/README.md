# fgs-retention-reopen (2026-11-06)
Task: measure whether FGS `retain=X` beats prod FGS (retain=0) and plain encode at equal file size on grain-off base detail, per content class. Measures only; no verdict.
Contents:
- common.py (titles, windows, helpers), prep.py/shift*.py (window cut, letterbox, low-luma rule), metrics.py (base-detail/chroma/grain metrics), run.py (encodes + scoring), controls.py (instrument controls), summary.py (tables).
- manifest.json (windows), results_rows.json (raw rows), controls.json, results.json + summary.md (final).
- Encodes/windows live in /tmp/downloads/tdarr-temp/fgs-retention-reopen/<win>/ (win.mkv = stream-copied window = encoder input and reference; enc/*.mkv; only q30 encodes kept).
Rebuild: python3 prep.py; python3 shift.py (+60 s shifts); python3 run.py <wins>; python3 controls.py; python3 summary.py. Needs the tdarr-node container (nvencc), vmaf fork, FFVship image.
Must keep: results.json, summary.md. Everything else is reproducible.
