#!/bin/sh
# Build and run the GPU-free film grain unit tests (solver + filmgrn1 parser).
#
# `set -e` is here in the body, not only on the shebang line.  The shebang's
# options are ignored when the script is invoked as `sh run_cpu_tests.sh` or
# `bash run_cpu_tests.sh` -- which is how README.md and CI call it -- and
# without it the script exits with the status of the LAST command, so a failing
# solver test would still report success.
set -e
cd "$(dirname "$0")/../.."
CXX=${CXX:-g++}
OUT=${TMPDIR:-/tmp}
$CXX -std=c++17 -O2 -Wall -I NVEncCore tests/fgs/population_envelope_test.cpp -o "$OUT/fgs_population_envelope_test"
"$OUT/fgs_population_envelope_test"
$CXX -std=c++17 -O2 -Wall tests/fgs/seed_patch_test.cpp -o "$OUT/fgs_seed_patch_test"
"$OUT/fgs_seed_patch_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore \
    tests/fgs/source_preservation_test.cpp -o "$OUT/fgs_source_preservation_test"
"$OUT/fgs_source_preservation_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore \
    tests/fgs/model_evidence_test.cpp -o "$OUT/fgs_model_evidence_test"
"$OUT/fgs_model_evidence_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore \
    tests/fgs/joint_template_test.cpp -o "$OUT/fgs_joint_template_test"
"$OUT/fgs_joint_template_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore \
    tests/fgs/native_scaling_test.cpp -o "$OUT/fgs_native_scaling_test"
"$OUT/fgs_native_scaling_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore \
    tests/fgs/colour_fidelity_test.cpp -o "$OUT/fgs_colour_fidelity_test"
"$OUT/fgs_colour_fidelity_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore \
    tests/fgs/retention_select_test.cpp -o "$OUT/fgs_retention_select_test"
"$OUT/fgs_retention_select_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore \
    tests/fgs/joint_collect_contract_test.cpp -o "$OUT/fgs_joint_collect_contract_test"
"$OUT/fgs_joint_collect_contract_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore \
    tests/fgs/balanced_model_test.cpp -o "$OUT/fgs_balanced_model_test"
"$OUT/fgs_balanced_model_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore \
    tests/fgs/joint_fidelity_test.cpp -o "$OUT/fgs_joint_fidelity_test"
"$OUT/fgs_joint_fidelity_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore \
    tests/fgs/luma_template_test.cpp -o "$OUT/fgs_luma_template_test"
"$OUT/fgs_luma_template_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore \
    tests/fgs/joint_spectrum_test.cpp -o "$OUT/fgs_joint_spectrum_test"
"$OUT/fgs_joint_spectrum_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore \
    tests/fgs/joint_model_test.cpp -o "$OUT/fgs_joint_model_test"
"$OUT/fgs_joint_model_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore -I NVEncSDK/Common/inc \
    tests/fgs/grain_scale_test.cpp NVEncCore/NVEncFilmGrainModel.cpp -o "$OUT/fgs_grain_scale_test"
"$OUT/fgs_grain_scale_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore -I NVEncSDK/Common/inc \
    tests/fgs/solver_test.cpp NVEncCore/NVEncFilmGrainModel.cpp -o "$OUT/fgs_solver_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore -I NVEncSDK/Common/inc \
    tests/fgs/local_strength_test.cpp NVEncCore/NVEncFilmGrainModel.cpp -o "$OUT/fgs_local_strength_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore -I NVEncSDK/Common/inc \
    tests/fgs/chroma_restore_test.cpp NVEncCore/NVEncFilmGrainModel.cpp -o "$OUT/fgs_chroma_restore_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore -I NVEncSDK/Common/inc \
    tests/fgs/model_hold_test.cpp NVEncCore/NVEncFilmGrainModel.cpp -o "$OUT/fgs_model_hold_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore -I NVEncSDK/Common/inc \
    tests/fgs/parser_test.cpp NVEncCore/NVEncFilmGrain.cpp -o "$OUT/fgs_parser_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore \
    tests/fgs/stability_test.cpp -o "$OUT/fgs_stability_test"
$CXX -std=c++17 -O2 -Wall tests/fgs/scan_packet_test.cpp -o "$OUT/fgs_scan_packet_test"
$CXX -std=c++17 -O2 -Wall tests/fgs/av1_grain_syntax_test.cpp -o "$OUT/fgs_grain_syntax_test"
$CXX -std=c++17 -O2 -Wall tests/fgs/display_spatial_test.cpp -o "$OUT/fgs_display_spatial_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore \
    tests/fgs/synthesis_recovery_test.cpp -o "$OUT/fgs_synthesis_recovery_test"
"$OUT/fgs_synthesis_recovery_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore \
    tests/fgs/source_guard_test.cpp -o "$OUT/fgs_source_guard_test"
"$OUT/fgs_source_guard_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore \
    tests/fgs/scene_schedule_test.cpp -o "$OUT/fgs_scene_schedule_test"
"$OUT/fgs_scene_schedule_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore \
    tests/fgs/training_history_test.cpp -o "$OUT/fgs_training_history_test"
"$OUT/fgs_training_history_test"
"$OUT/fgs_solver_test"
"$OUT/fgs_local_strength_test"
"$OUT/fgs_chroma_restore_test"
"$OUT/fgs_model_hold_test"
"$OUT/fgs_parser_test"
"$OUT/fgs_stability_test"
"$OUT/fgs_scan_packet_test"
"$OUT/fgs_grain_syntax_test"
"$OUT/fgs_display_spatial_test"
python3 tests/fgs/test_filmgrn.py
python3 tests/fgs/test_quality_metrics.py
python3 tests/fgs/test_texture_metrics.py
python3 tests/fgs/test_reference_occupancy.py
python3 tests/fgs/test_model_gate.py
python3 tests/fgs/test_gate.py
python3 tests/fgs/test_fixtures.py
python3 tests/fgs/test_decoded_sequence.py
python3 tests/fgs/test_review_window.py
python3 tests/fgs/test_review_batch.py
python3 tests/fgs/test_production_compare.py
python3 tests/fgs/test_trial_admission.py
python3 tests/fgs/test_retention_cost_regression.py
python3 tests/fgs/test_retention_diagnostics.py
python3 tests/fgs/test_retention_tradeoff.py
python3 tests/fgs/test_hdr_metadata_trace.py
python3 tests/fgs/test_dovi_conversion_regression.py
python3 tests/fgs/test_flicker_regression.py
python3 tests/fgs/test_fel_metadata.py
python3 tests/fgs/test_fel_layer_order.py
python3 tests/fgs/test_fel_prepare.py
python3 tests/fgs/test_fel_process.py
python3 tests/fgs/test_fel_parameter_bounds.py
python3 tests/fgs/test_kat_startup.py

python3 tests/fgs/test_amplitude_regression.py
python3 tests/fgs/test_native_pq_compare.py
