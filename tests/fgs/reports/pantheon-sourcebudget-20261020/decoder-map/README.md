# R10 reproduction and preserved evidence

The repository stores source patches, observers, build/command/admission scripts,
source manifests, compact results and independent reviews. Complete raw traces,
outputs, detailed units/control results, revisions and visual artifacts are under
`/tmp/downloads/codex-work/pantheon-sourcebudget-20261020/`; exact paths/hashes are
in `../decoder-map-result.json`. Session archival remains pending while R11 runs.
Do not rebuild/delete completed source or evidence trees.

Pristine source: libaom3.8.2 upstream archive SHA
63238bcefc514e3e454e7ebab8470174c9a237a578e3e4ee3e9872e9bfc70078
plus seven patches from Ubuntu3.8.2-2ubuntu0.2 archive SHA
d1fb459395296901e6aed6348828c6a5a29e2364d5b0c809a5ba1def73d599e7.
Full1344-file baseline manifest is preserved; instrumented1345-file source adds
one observer header and hooks only decoder.c/decodeframe.c. Full source/build
provenance and loaded private SONAME are in completed-build-pins.json.

Observed commands (paths are exact; use a fresh sibling for intentional reruns):

```sh
ROOT=/tmp/downloads/codex-work/pantheon-sourcebudget-20261020
P="$ROOT/parent/aom-decoder-r10-v2"
# Already completed: do not repeat unchanged checks.
bash "$P/build_runner.sh"
python3 "$P/replay.py" "$P/build-proposed" "$P/runs/off-1"
python3 "$P/replay.py" "$P/build-proposed" "$P/runs/on-1" --trace
"$ROOT/analysis-venv/bin/python" "$P/validate.py" "$P/runs/off-1" "$P/runs/on-1" "$P/admitted-1"
"$ROOT/analysis-venv/bin/python" "$P/faultchecks.py"
"$ROOT/analysis-venv/bin/python" "$ROOT/worker/decoder-r10-analysis/analyze_decoder_units.py" "$P/admitted-1" "$ROOT/worker/decoder-r10-analysis/result-1.json" --validator-sha fde9fa7a79c52de70b0098d38fe291670472e8250f629c4c5f3c648d322b471b
"$ROOT/analysis-venv/bin/python" "$ROOT/worker/decoder-r10-analysis/full-roi-supplement-v2/full_roi_supplement-v2.py" "$P/admitted-1" "$ROOT/worker/decoder-r10-analysis/full-roi-supplement-v2/full-roi-supplement-result-v2.json" --validator-sha fde9fa7a79c52de70b0098d38fe291670472e8250f629c4c5f3c648d322b471b
"$ROOT/analysis-venv/bin/python" "$P/inspect_coefficients.py"
"$ROOT/analysis-venv/bin/python" "$P/render_r10.py"
```

Main analysis inner argv, interpreter/helper and input identities are bound in
analysis-command-correction.json; its original outer affinity/timing are not
independently corroborated. Supplement-v2 records actual inner/outer argv and
elapsed. Replay/validator/analyzer/supplement reject optimized Python; structural
fault/render/coefficient helpers are narrower diagnostics, not admission drivers. Archived pinned paths are provenance;
for a fresh reproduction recreate the reviewed source in a new scratch tree,
rerun build and regenerate explicit completed-build/driver pins after review.
Never transplant old pins onto a different build.

The native predictor mosaic contains sequential local predictors (intra uses
already reconstructed neighbors); it is not a coherent whole-frame predictor-
only counterfactual. Quantized/EOB-absent syntax does not report whether encoder
forward quantization ran. IQMstate−1=no inverse contribution,0=normative flat,
1=copied actual matrix. Intra refs/MVs are invalid sentinels. Show-existing
frame_type/showable are−1; independent parser owns slot lifecycle. Coefficient
counts are never coded-bit proxies in conclusions.
