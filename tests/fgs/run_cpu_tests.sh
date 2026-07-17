#!/bin/sh -e
# Build and run the GPU-free film grain unit tests (solver + filmgrn1 parser).
cd "$(dirname "$0")/../.."
CXX=${CXX:-g++}
OUT=${TMPDIR:-/tmp}
$CXX -std=c++17 -O2 -Wall -I NVEncCore -I NVEncSDK/Common/inc \
    tests/fgs/solver_test.cpp NVEncCore/NVEncFilmGrainModel.cpp -o "$OUT/fgs_solver_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore -I NVEncSDK/Common/inc \
    tests/fgs/parser_test.cpp NVEncCore/NVEncFilmGrain.cpp -o "$OUT/fgs_parser_test"
"$OUT/fgs_solver_test"
"$OUT/fgs_parser_test"
python3 tests/fgs/test_filmgrn.py
python3 tests/fgs/test_quality_metrics.py
