#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
SRC="$ROOT/source"
BUILD="$ROOT/build"
PRE="$ROOT/source-manifest-before.json"
POST="$ROOT/source-manifest-after.json"
RECEIPT="$ROOT/build-receipt.log"
CONFIG_LOG="$ROOT/configure.log"
BUILD_LOG="$ROOT/build.log"
RUNNER_COPY="$ROOT/measured-runner.sh"
status=starting
exit_rc=0
receipt_owned=0
on_exit() {
  rc=$?
  [ "$rc" -eq 0 ] || exit_rc="$rc"
  if [ "$rc" -ne 0 ] && { [ "$status" = starting ] || [ "$status" = prepared ]; }; then status=failed; fi
  echo "final_status=${status}" >&2 || true
  echo "end_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >&2 || true
  echo "exit_code=${exit_rc}" >&2 || true
}
trap on_exit EXIT
for p in "$BUILD" "$PRE" "$POST" "$RECEIPT" "$CONFIG_LOG" "$BUILD_LOG" "$RUNNER_COPY" \
         "$ROOT/build-bin-files.tsv" "$ROOT/app-ldd.txt" "$ROOT/app-version.txt" "$ROOT/app-help.txt" \
         "$ROOT/build-artifact-hashes.txt" "$ROOT/tool-identities.txt" "$ROOT/tool-identities-before.txt" "$ROOT/tool-identities-after.txt"; do
  [ ! -e "$p" ] || { echo "refusing_existing_output=$p" >&2; status=refused_existing_output; exit 2; }
done
[ -d "$SRC/.git" ] || { echo "missing_git_source=$SRC" >&2; status=missing_source; exit 2; }
AVAIL_GB=$(df --output=avail -BG "$ROOT" | tail -1 | tr -dc '0-9')
[ "${AVAIL_GB:-0}" -ge 130 ] || { echo "resource_floor_failed_available_gb=${AVAIL_GB:-0}" >&2; status=resource_floor_failed; exit 1; }
for var in LD_LIBRARY_PATH LD_PRELOAD LD_AUDIT CFLAGS CXXFLAGS CPPFLAGS LDFLAGS CC CXX; do
  [ -z "${!var:-}" ] || { echo "rejected_inherited_env=$var" >&2; status=unsafe_environment; exit 1; }
done
cp -- "$0" "$RUNNER_COPY"
RUNNER_SHA=$(sha256sum "$RUNNER_COPY" | awk '{print $1}')
: > "$RECEIPT"
receipt_owned=1
exec > "$RECEIPT" 2>&1
status=prepared
start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "status=$status"
echo "start_utc=$start_utc"
echo "source=$SRC"
echo "build=$BUILD"
echo "runner_copy=$RUNNER_COPY"
echo "runner_sha256=$RUNNER_SHA"
echo "available_gb=$AVAIL_GB"
echo "source_url=$(git -C "$SRC" remote get-url origin)"
echo "source_head=$(git -C "$SRC" rev-parse HEAD)"
[ "$(git -C "$SRC" rev-parse HEAD)" = 59d1a025698f2ca7b4c4b0e833937dd15e382494 ] || { echo status=head_mismatch; status=head_mismatch; exit 1; }
manifest() {
  python3 - "$SRC" "$1" <<'PY'
import hashlib,json,sys
from pathlib import Path
root,out=map(Path,sys.argv[1:])
rows=[]
for p in sorted(root.rglob('*')):
    rel=p.relative_to(root)
    if '.git' in rel.parts: continue
    if p.is_symlink(): raise SystemExit(f'unexpected symlink: {rel}')
    if p.is_file(): rows.append([str(rel),p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest()])
out.write_text(json.dumps(rows,indent=2)+'\n')
print(f'manifest_count={len(rows)}')
PY
}
manifest "$PRE"
[ "$(sha256sum "$PRE" | awk '{print $1}')" = 12f345e1f738b97fd00d9b9b2978864c53df995ad7590374edc21d31004124ce ] || { echo status=reviewed_manifest_mismatch; status=reviewed_manifest_mismatch; exit 1; }
cmp -s "$PRE" "$ROOT/source-manifest.json" || { echo status=reviewed_manifest_byte_mismatch; status=reviewed_manifest_byte_mismatch; exit 1; }
echo "reviewed_manifest_sha256=$(sha256sum "$PRE" | awk '{print $1}')"
record_tools() {
  local out="$1" tool path version first
  : > "$out"
  for tool in cc c++ cmake ninja nasm; do
    path=$(readlink -f "$(command -v "$tool")")
    version=$("$path" --version 2>&1)
    first=${version%%$'\n'*}
    printf '%s\t%s\t%s\t%s\n' "$tool" "$path" "$(sha256sum "$path" | awk '{print $1}')" "$first" >> "$out"
  done
}
record_tools "$ROOT/tool-identities-before.txt"
cp "$ROOT/tool-identities-before.txt" "$ROOT/tool-identities.txt"
CONFIG=( -G Ninja -S "$SRC" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF -DBUILD_APPS=ON -DBUILD_SHARED_LIBS=ON -DFETCHCONTENT_FULLY_DISCONNECTED=ON -DCMAKE_OUTPUT_DIRECTORY="$BUILD/bin" )
echo "configure_command=$(printf '%q ' nice -n 10 taskset -c 0-7 cmake "${CONFIG[@]}")"
set +e
nice -n 10 taskset -c 0-7 cmake "${CONFIG[@]}" > "$CONFIG_LOG" 2>&1
rc=$?
set -e
echo "configure_returncode=$rc"
cat "$CONFIG_LOG"
[ "$rc" -eq 0 ] || { echo status=configure_failed; status=configure_failed; exit "$rc"; }
for f in "$BUILD/CMakeCache.txt" "$BUILD/build.ninja"; do [ -f "$f" ] || { echo "missing_build_file=$f"; status=configure_missing_file; exit 1; }; done
CC_CACHE=$(awk -F= '/^CMAKE_C_COMPILER:FILEPATH=/{print $2; exit}' "$BUILD/CMakeCache.txt")
CXX_CACHE=$(awk -F= '/^CMAKE_CXX_COMPILER:FILEPATH=/{print $2; exit}' "$BUILD/CMakeCache.txt")
[ "$(readlink -f "$CC_CACHE")" = "$(readlink -f "$(command -v cc)")" ] || { echo status=c_compiler_path_mismatch; status=c_compiler_path_mismatch; exit 1; }
[ "$(readlink -f "$CXX_CACHE")" = "$(readlink -f "$(command -v c++)")" ] || { echo status=cxx_compiler_path_mismatch; status=cxx_compiler_path_mismatch; exit 1; }
echo "cmake_c_compiler=$CC_CACHE"
echo "cmake_cxx_compiler=$CXX_CACHE"
CACHE_SHA_BEFORE=$(sha256sum "$BUILD/CMakeCache.txt" | awk '{print $1}')
NINJA_SHA_BEFORE=$(sha256sum "$BUILD/build.ninja" | awk '{print $1}')
echo "cmakecache_sha256=$CACHE_SHA_BEFORE"
echo "build_ninja_sha256=$NINJA_SHA_BEFORE"
echo "build_command=nice -n 10 taskset -c 0-7 cmake --build $BUILD --parallel 4"
set +e
nice -n 10 taskset -c 0-7 cmake --build "$BUILD" --parallel 4 > "$BUILD_LOG" 2>&1
rc=$?
set -e
echo "build_returncode=$rc"
cat "$BUILD_LOG"
[ "$rc" -eq 0 ] || { echo status=build_failed; status=build_failed; exit "$rc"; }
CACHE_SHA_AFTER=$(sha256sum "$BUILD/CMakeCache.txt" | awk '{print $1}')
NINJA_SHA_AFTER=$(sha256sum "$BUILD/build.ninja" | awk '{print $1}')
[ "$CACHE_SHA_AFTER" = "$CACHE_SHA_BEFORE" ] || { echo status=cmakecache_changed; status=cmakecache_changed; exit 1; }
[ "$NINJA_SHA_AFTER" = "$NINJA_SHA_BEFORE" ] || { echo status=build_ninja_changed; status=build_ninja_changed; exit 1; }
record_tools "$ROOT/tool-identities-after.txt"
cmp -s "$ROOT/tool-identities-before.txt" "$ROOT/tool-identities-after.txt" || { echo status=tool_identity_changed; status=tool_identity_changed; exit 1; }
RUNNER_AFTER_SHA=$(sha256sum "$RUNNER_COPY" | awk '{print $1}')
[ "$RUNNER_AFTER_SHA" = "$RUNNER_SHA" ] || { echo status=runner_copy_changed; status=runner_copy_changed; exit 1; }
manifest "$POST"
[ "$(sha256sum "$POST" | awk '{print $1}')" = 12f345e1f738b97fd00d9b9b2978864c53df995ad7590374edc21d31004124ce ] || { echo status=post_manifest_mismatch; status=post_manifest_mismatch; exit 1; }
cmp -s "$POST" "$ROOT/source-manifest.json" || { echo status=post_manifest_byte_mismatch; status=post_manifest_byte_mismatch; exit 1; }
APP="$BUILD/bin/SvtAv1EncApp"
[ -x "$APP" ] || { echo status=missing_encoder_app; status=missing_encoder_app; exit 1; }
find "$BUILD/bin" -maxdepth 1 -type f -printf '%f\t%s\n' | sort | tee "$ROOT/build-bin-files.tsv"
echo "app_sha256=$(sha256sum "$APP" | awk '{print $1}')"
mapfile -t LIBS < <(find "$BUILD/bin" -maxdepth 1 -type f -name 'libSvtAv1Enc.so*' -print | sort)
LIB="${LIBS[0]:-}"
[ -n "$LIB" ] || { echo status=missing_encoder_library; status=missing_encoder_library; exit 1; }
LIB_REAL=$(readlink -f "$LIB")
[ "$LIB_REAL" = "$LIB" ] || { echo status=library_not_regular_versioned_file; status=library_not_regular_versioned_file; exit 1; }
LIB_SHA=$(sha256sum "$LIB_REAL" | awk '{print $1}')
echo "library_path=$LIB_REAL"
echo "library_sha256=$LIB_SHA"
echo "library_size=$(stat -c %s "$LIB_REAL")"
LD_LIBRARY_PATH="$BUILD/bin" ldd "$APP" | tee "$ROOT/app-ldd.txt"
RESOLVED=$(awk '/libSvtAv1Enc\.so\.3[[:space:]]*=>/ {print $3; exit}' "$ROOT/app-ldd.txt")
[ -n "$RESOLVED" ] || { echo status=library_soname_unresolved; status=library_soname_unresolved; exit 1; }
RESOLVED_REAL=$(readlink -f "$RESOLVED")
[ "$RESOLVED_REAL" = "$LIB_REAL" ] || { echo status=library_resolution_mismatch; status=library_resolution_mismatch; exit 1; }
[ "${RESOLVED_REAL#"$BUILD/bin/"}" != "$RESOLVED_REAL" ] || { echo status=library_outside_private_build; status=library_outside_private_build; exit 1; }
[ "$LIB_SHA" = "$(sha256sum "$RESOLVED_REAL" | awk '{print $1}')" ] || { echo status=library_hash_mismatch; status=library_hash_mismatch; exit 1; }
LD_LIBRARY_PATH="$BUILD/bin" "$APP" --version | tee "$ROOT/app-version.txt"
LD_LIBRARY_PATH="$BUILD/bin" "$APP" --help > "$ROOT/app-help.txt"
sha256sum "$PRE" "$POST" "$BUILD/CMakeCache.txt" "$BUILD/build.ninja" "$APP" "$LIB_REAL" "$ROOT"/{configure.log,build.log,build-bin-files.tsv,app-ldd.txt,app-version.txt,app-help.txt,tool-identities.txt,tool-identities-before.txt,tool-identities-after.txt,measured-runner.sh} | tee "$ROOT/build-artifact-hashes.txt"
status=build_complete
echo status=build_complete
