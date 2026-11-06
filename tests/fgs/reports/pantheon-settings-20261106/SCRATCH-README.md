# pantheon-settings-20261106
Task: does any NVENC AV1 setting recover Pantheon background texture at acceptable size? Measurement only.
- pset.py (helpers), setup_run.py/fixmbps.py (windows), sweep.py (encode+score+base-detail), summary.py (tables). Imports the fgs-retention-reopen instrument unedited.
- manifest.json (windows), rows.json (raw rows), results.json + summary.md (final), logs/ (encoder commands/logs), raw/ (vmaf/ffvship json), sweep.log.
- Encodes (q34 only kept): /tmp/downloads/tdarr-temp/pantheon-settings-20261106/<win>/enc/ (root-owned; delete via docker exec tdarr-node).
Rebuild: python3 setup_run.py; python3 sweep.py p04a,p04b,p01,p05 all; python3 summary.py. Needs tdarr-node, vmaf fork, FFVship image.
Keep: results.json, summary.md.
