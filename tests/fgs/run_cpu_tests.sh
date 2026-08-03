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
$CXX -std=c++17 -O2 -Wall -I NVEncCore -I NVEncSDK/Common/inc \
    tests/fgs/solver_test.cpp NVEncCore/NVEncFilmGrainModel.cpp -o "$OUT/fgs_solver_test"
$CXX -std=c++17 -O2 -Wall -I NVEncCore -I NVEncSDK/Common/inc \
    tests/fgs/parser_test.cpp NVEncCore/NVEncFilmGrain.cpp -o "$OUT/fgs_parser_test"
"$OUT/fgs_solver_test"
"$OUT/fgs_parser_test"
python3 -m unittest discover -s tests/fgs -p 'test_*.py'
