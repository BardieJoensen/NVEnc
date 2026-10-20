#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"; SRC="$ROOT/source"; BUILD="$ROOT/build-proposed"
REVIEWED="$ROOT/source-manifest.json"; PRE="$ROOT/source-manifest-before-build.json"; POST="$ROOT/source-manifest-after-build.json"
LOG="$ROOT/build-receipt.log"; CONFIG_LOG="$ROOT/configure.log"; BUILD_LOG="$ROOT/build.log"; RECEIPT="$ROOT/build-receipt.json"
for p in "$BUILD" "$PRE" "$POST" "$LOG" "$CONFIG_LOG" "$BUILD_LOG" "$RECEIPT"; do [ ! -e "$p" ] || { echo "refusing_existing_output=$p" >&2; exit 2; }; done
[ -d "$SRC" ] && [ -f "$REVIEWED" ] || { echo missing_source_or_manifest >&2; exit 2; }
[ -z "${LD_LIBRARY_PATH:-}" ] && [ -z "${LD_PRELOAD:-}" ] && [ -z "${LD_AUDIT:-}" ] || { echo inherited_loader_override >&2; exit 2; }
mkdir "$BUILD"
start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
start_epoch=$(date +%s)
exec > >(tee "$LOG") 2>&1
python3 - "$SRC" "$PRE" "$REVIEWED" <<'PY'
import hashlib,json,os,sys
def manifest(root):
 d={}
 for dp,dn,fn in os.walk(root):
  for f in fn:
   p=os.path.join(dp,f); r=os.path.relpath(p,root); h=hashlib.sha256()
   with open(p,'rb') as q:
    for b in iter(lambda:q.read(1<<20),b''): h.update(b)
   d[r]=h.hexdigest()
 return d
root,out,reviewed=sys.argv[1:]; x=manifest(root); e=json.load(open(reviewed))
if x != e: raise SystemExit(f'manifest_mismatch actual={len(x)} expected={len(e)}')
json.dump(x,open(out,'w'),sort_keys=True,indent=2); open(out,'a').write('\n'); print('source_manifest_match=1')
PY
CONFIG=(-G Ninja -S "$SRC" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=ON -DENABLE_TESTS=0 -DCONFIG_LIBYUV=0 -DCONFIG_WEBM_IO=0 -DCONFIG_MULTITHREAD=1 -DFORCE_HIGHBITDEPTH_DECODING=0 -DAOM_TARGET_CPU=x86_64 -DCONFIG_BIG_ENDIAN=0 -DGIT_EXECUTABLE=/nonexistant-binary)
ccbin=$(command -v cc); cmakebin=$(command -v cmake); ninjabin=$(command -v ninja)
echo "tool_cc=$ccbin"; sha256sum "$ccbin"; echo "tool_cmake=$cmakebin"; sha256sum "$cmakebin"; echo "tool_ninja=$ninjabin"; sha256sum "$ninjabin"; echo "cmake_version=$(cmake --version | head -1)"; echo "ninja_version=$(ninja --version)"
echo "configure_command=nice -n 10 taskset -c 0-7 cmake ${CONFIG[*]}"
nice -n 10 taskset -c 0-7 cmake "${CONFIG[@]}" >"$CONFIG_LOG" 2>&1
cat "$CONFIG_LOG"
echo "build_command=nice -n 10 taskset -c 0-7 cmake --build $BUILD --target aom aomdec --parallel 4"
nice -n 10 taskset -c 0-7 cmake --build "$BUILD" --target aom aomdec --parallel 4 >"$BUILD_LOG" 2>&1
cat "$BUILD_LOG"
python3 - "$SRC" "$POST" "$PRE" <<'PY'
import hashlib,json,os,sys
def manifest(root):
 d={}
 for dp,dn,fn in os.walk(root):
  for f in fn:
   p=os.path.join(dp,f); r=os.path.relpath(p,root); h=hashlib.sha256()
   with open(p,'rb') as q:
    for b in iter(lambda:q.read(1<<20),b''): h.update(b)
   d[r]=h.hexdigest()
 return d
root,out,pre=sys.argv[1:]; x=manifest(root); e=json.load(open(pre))
if x != e: raise SystemExit('source_changed_during_build')
json.dump(x,open(out,'w'),sort_keys=True,indent=2); open(out,'a').write('\n'); print('source_after_build_match=1')
PY
for f in "$BUILD/libaom.so.3.8.2" "$BUILD/aomdec"; do [ -f "$f" ] || { echo "missing_artifact=$f" >&2; exit 1; }; done
real=$(realpath "$BUILD/libaom.so.3.8.2"); case "$real" in "$BUILD"/*) ;; *) echo "library_not_private=$real" >&2; exit 1;; esac
printf 'private_library=%s\n' "$real"; sha256sum "$real"; ldd "$BUILD/aomdec" | tee "$ROOT/ldd-aomdec.txt"
python3 - "$ROOT/ldd-aomdec.txt" "$real" <<'PY2'
import os,re,sys
text=open(sys.argv[1]).read(); expected=os.path.realpath(sys.argv[2]); paths=[]
for line in text.splitlines():
 m=re.search(r'=>\s+(\S+)',line)
 if m: paths.append(os.path.realpath(m.group(1)))
if expected not in paths: raise SystemExit(f'private_soname_not_resolved expected={expected} resolved={paths}')
print('private_soname_resolved=1')
PY2
end_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ); end_epoch=$(date +%s)
python3 - "$RECEIPT" "$real" "$BUILD/aomdec" "$BUILD/config/aom_config.h" "$start_utc" "$end_utc" "$((end_epoch-start_epoch))" <<'PY'
import json,sys,hashlib,os
p,lib,app,cfg,start,end,elapsed=sys.argv[1:]
def ident(x):
 h=hashlib.sha256(open(x,'rb').read()).hexdigest(); return {'path':x,'sha256':h,'size':os.path.getsize(x)}
json.dump({'status':'build_complete','start_utc':start,'end_utc':end,'elapsed_seconds':int(elapsed),'library':ident(lib),'aomdec':ident(app),'config':ident(cfg),'compiler':os.popen('cc --version').read().splitlines()[0],'cmake':os.popen('cmake --version').read().splitlines()[0],'ninja':os.popen('ninja --version').read().strip()},open(p,'w'),indent=2); open(p,'a').write('\n')
PY
