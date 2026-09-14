#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
export CARGO_TARGET_DIR=/trial/build/cargo-target
export CARGO_BUILD_JOBS=4
apt-get update
apt-get install -y --no-install-recommends autoconf automake libtool autoconf-archive \
  python3-dev python3-venv libzimg-dev libx11-dev libva-dev libvdpau-dev libdrm-dev \
  libbz2-dev zlib1g-dev nasm
python3 -m venv /trial/venv
/trial/venv/bin/pip install --no-cache-dir meson==1.10.0 Cython==3.1.2 pytest numpy pillow
export PATH=/trial/venv/bin:/trial/prefix/bin:$PATH
export PKG_CONFIG_PATH=/trial/prefix/lib/pkgconfig:/usr/local/lib/pkgconfig
export LD_LIBRARY_PATH=/trial/prefix/lib:/usr/local/lib:${LD_LIBRARY_PATH:-}
export PYTHONPATH=/trial/prefix/lib/python3.12/site-packages
cd /trial/src/vapoursynth
./autogen.sh
./configure --prefix=/trial/prefix PYTHON=/trial/venv/bin/python3
make -j4
make install
cd /trial/src/ffms2
./autogen.sh
./configure --prefix=/trial/prefix
make -j4
make install
cd /trial/src/felbaker
meson setup /trial/build/felbaker --buildtype=release -Dcpu_tier=generic
meson compile -C /trial/build/felbaker -j4
python3 -c 'import vapoursynth as vs; print(vs.__version__); vs.core.std.LoadPlugin("/trial/prefix/lib/libffms2.so"); vs.core.std.LoadPlugin("/trial/build/felbaker/libfelbaker.so"); print(vs.core.plugins())'
