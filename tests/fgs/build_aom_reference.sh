#!/bin/sh -eu

# Build the official libaom noise_model example outside the NVEnc tree.
# The pinned revision makes benchmark reports reproducible; override it only
# deliberately with AOM_REF_REVISION.

if [ "$#" -ne 1 ]; then
    echo "usage: $0 <empty-output-directory>" >&2
    exit 2
fi

DEST=$1
REVISION=${AOM_REF_REVISION:-18c52422b835ba6cdde1b2342d760c6037a7fd86}
if [ -e "$DEST" ]; then
    echo "output path already exists: $DEST" >&2
    exit 2
fi

mkdir -p "$DEST"
git -C "$DEST" init src
git -C "$DEST/src" remote add origin https://aomedia.googlesource.com/aom
git -C "$DEST/src" fetch --depth 1 origin "$REVISION"
git -C "$DEST/src" checkout --detach FETCH_HEAD
cmake -S "$DEST/src" -B "$DEST/build" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DENABLE_TESTS=0 \
    -DENABLE_DOCS=0 \
    -DENABLE_EXAMPLES=1 \
    -DENABLE_TOOLS=1
cmake --build "$DEST/build" --target noise_model --parallel

echo "AOM_NOISE_MODEL=$DEST/build/noise_model"
echo "AOM_NOISE_MODEL_REVISION=$REVISION"
