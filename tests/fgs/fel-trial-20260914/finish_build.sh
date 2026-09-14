#!/usr/bin/env bash
set -euo pipefail
export PATH=/trial/venv/bin:/trial/prefix/bin:$PATH
export PKG_CONFIG_PATH=/trial/prefix/lib/pkgconfig:/usr/local/lib/pkgconfig
export LD_LIBRARY_PATH=/trial/prefix/lib:/usr/local/lib:${LD_LIBRARY_PATH:-}
export PYTHONPATH=/trial/prefix/lib/python3.12/site-packages
export CARGO_TARGET_DIR=/trial/build/cargo-target
export CARGO_BUILD_JOBS=4
cd /trial/src/ffms2
# Bind the privately embedded static FFmpeg symbols inside this trial plugin.
make -j4 LDFLAGS=-Wl,-Bsymbolic
make install LDFLAGS=-Wl,-Bsymbolic
cd /trial/src/felbaker
meson setup /trial/build/felbaker --buildtype=release -Dcpu_tier=generic
meson compile -C /trial/build/felbaker -j4
python3 -c 'import vapoursynth as vs; print(vs.__version__); vs.core.std.LoadPlugin("/trial/prefix/lib/libffms2.so"); vs.core.std.LoadPlugin("/trial/build/felbaker/libfelbaker.so"); print(list(vs.core.plugins()))'
