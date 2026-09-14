#!/usr/bin/env bash
set -euo pipefail
export PATH=/trial/venv/bin:/trial/prefix/bin:$PATH
export PKG_CONFIG_PATH=/trial/prefix/lib/pkgconfig:/usr/local/lib/pkgconfig
export LD_LIBRARY_PATH=/trial/prefix/lib:/usr/local/lib:${LD_LIBRARY_PATH:-}
export PYTHONPATH=/trial/prefix/lib/python3.12/site-packages:/trial/scripts
export CARGO_TARGET_DIR=/trial/build/cargo-target
export CARGO_BUILD_JOBS=4
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
exec "$@"
