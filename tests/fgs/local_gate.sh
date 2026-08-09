#!/bin/bash
# Tier 2 of the film-grain test suite: the checks that need a GPU, real film,
# and libaom as an external oracle.
#
# THIS CANNOT RUN ON A HOSTED RUNNER, AND MUST NOT BE MADE TO.
# Every defect this catches is invisible to conventional signals -- both
# 2026-07-29/30 regressions made files SMALLER, VMAF and SSIMULACRA2 BETTER,
# CAMBI clean, and all 18 GPU fixtures green. They were found only by comparing
# against libaom on real film. A hosted runner has no GPU, no libaom, no media
# and no labelled negatives, so a hosted copy of this gate would report success
# for all of them. See tests/fgs/TIERS.md.
#
# The gate therefore REFUSES TO RUN when a prerequisite is missing (exit 2)
# rather than skipping the stage. A skipped stage in a green run is the exact
# failure mode this whole framework exists to prevent.
#
# VALIDATION AGAINST KNOWN-BAD INPUT
# Three labelled negatives are asserted here, not merely documented:
#   1. r4047 NVEncC (the rejected correlation widening) must make the
#      base-fidelity canary ALERT, and r4050 must not.
#   2. taxi_ceiling_q.json (a deliberate metric-gamer) must be REJECTED by the
#      texture model gate, while the shipping model is accepted.
#   3. The r4047-vs-r4050 texture pair must separate on the texture detector.
# A gate that has only ever seen good input cannot be distinguished from one
# that cannot fail.
#
# USAGE
#   tests/fgs/local_gate.sh [--quick|--full] [--stage NAME]... [options]
#
#   --quick   GPU fixtures, synthetic oracle and both offline model negatives.
#             Minutes. This is what the pre-push hook runs.
#   --full    Everything, including real-film oracle, texture negative and the
#             base-fidelity canary negatives. Tens of minutes.
#   --stage   Run only the named stage; repeatable. Overrides --quick/--full.
#   --candidate-commit SHA
#             Build NVEncC from a pinned clone at SHA and test that binary.
#             Never builds from the live worktree; see robustness backlog 12.
#   --candidate-nvencc PATH
#             Test an already-built binary instead of building one.
#   --list    Print the stages and exit.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"

# ---------------------------------------------------------------------------
# Persistent locations.
#
# /tmp/aomref and /tmp/nvenc-pin4 were where these lived while the framework
# was being built, and both vanish on reboot. A durable gate cannot depend on
# them: the pinned libaom revision and the pinned encoder are the two things
# that make any of these numbers comparable across runs.
# ---------------------------------------------------------------------------
CACHE="${FGS_GATE_CACHE:-$HOME/.cache/fgs-gate}"
AOM_REVISION="${AOM_REF_REVISION:-18c52422b835ba6cdde1b2342d760c6037a7fd86}"
AOM_DIR="$CACHE/aom-${AOM_REVISION:0:12}"
BIN_DIR="$CACHE/bin"
BUILD_DIR="$CACHE/builds"
REPORT_DIR="${FGS_GATE_REPORTS:-$CACHE/reports/$(date -u +%Y%m%dT%H%M%SZ)}"

# Pinned, immutable references. Docker image IDs rather than tags: a tag can be
# repointed, and the point of a reference binary is that replacing a bad
# production binary cannot also replace the thing it is measured against.
REF_R4050_IMAGE="${FGS_GATE_R4050_IMAGE:-docker-apps/tdarr-node:2.85.01-nvencc927-r4050}"
REF_R4050_SHA256="5a8e198a4ab5da3167278d340de038ae5a5606de5be49eb7f6bcc26a4d570edd"
NEG_R4047_IMAGE="${FGS_GATE_R4047_IMAGE:-docker-apps/tdarr-node:2.85.01-nvencc927-grainfix}"
NEG_R4047_SHA256="28c1cae74f5e9002ce0d0d54240398df59098ea6f3f8e7f7f75ae61806145338"
NVENCC_IMAGE_PATH="/usr/bin/nvencc"
BUILD_IMAGE="${FGS_GATE_BUILD_IMAGE:-nvenc-fgs-build:cuda13.3}"

DOCKER_APPS="${DOCKER_APPS:-/opt/docker-apps}"
CANARY="$DOCKER_APPS/scripts/grain-base-canary.sh"

MEDIA="${FGS_GATE_MEDIA:-/media/merged-storage/media/test-encodes}"
CEILING_DIR="$MEDIA/ceiling"
TAXI_SRC="$CEILING_DIR/taxi_src.y4m"
TAXI_CLEAN="$CEILING_DIR/taxi_clean.y4m"
TAXI_MODEL="$CEILING_DIR/taxi.tbl"
CEILING_MODEL="$CEILING_DIR/taxi_ceiling_q.json"
TAXI_CLIP="$MEDIA/keep-original/ms_Taxi_Driver_20.mkv"
CASINO_WIDENED="$MEDIA/widening-evidence/casino_widened_r4047.mkv"
# The ORIGINAL download, never the library copy. Scoring an encode against a
# library file measures two stacked lossy generations instead of one and
# flattens every metric, which would quietly turn this negative control into a
# pass.
CASINO_SOURCE="${FGS_GATE_CASINO_SOURCE:-/media/merged-storage/media/downloads/keep-original-holds/Casino (1995) [tmdbid-524] - [Remux-2160p][DTS-X 7.1][HDR10][HEVC]-EPSiLON.mkv}"

ALL_STAGES=(tools kat synthetic_oracle model_negative real_oracle texture_negative canary_negative)
# ~3.5 minutes on this box: all GPU fixtures plus the offline adversarial
# specimen. Deliberately excludes the libaom oracles and the canary, which need
# real-film encodes. A pre-push hook long enough to be bypassed with
# --no-verify protects nothing, so the slow stages belong to the full run.
QUICK_STAGES=(tools kat model_negative)

CANDIDATE_NVENCC=""
CANDIDATE_COMMIT=""
STAGES=()
MODE="full"

while [ $# -gt 0 ]; do
    case "$1" in
        --quick) MODE="quick"; shift ;;
        --full)  MODE="full"; shift ;;
        --stage) STAGES+=("$2"); shift 2 ;;
        --candidate-nvencc) CANDIDATE_NVENCC="$2"; shift 2 ;;
        --candidate-commit) CANDIDATE_COMMIT="$2"; shift 2 ;;
        --list) printf '%s\n' "${ALL_STAGES[@]}"; exit 0 ;;
        -h|--help) sed -n '1,50p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

if [ "${#STAGES[@]}" -eq 0 ]; then
    if [ "$MODE" = "quick" ]; then STAGES=("${QUICK_STAGES[@]}");
    else STAGES=("${ALL_STAGES[@]}"); fi
fi

# A typo in --stage must be an error, not a quiet no-op: "0 failed" from a run
# that executed nothing is the same green-tick-checking-nothing problem this
# gate exists to avoid.
for requested in "${STAGES[@]}"; do
    known=0
    for stage in "${ALL_STAGES[@]}"; do
        [ "$stage" = "$requested" ] && known=1
    done
    if [ "$known" -eq 0 ]; then
        echo "unknown stage: $requested" >&2
        echo "known stages: ${ALL_STAGES[*]}" >&2
        exit 2
    fi
done

mkdir -p "$CACHE" "$BIN_DIR" "$BUILD_DIR" "$REPORT_DIR"

PASSES=(); FAILURES=()

log()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
info() { printf '   %s\n' "$*"; }
die()  { printf '\nlocal_gate: %s\n' "$*" >&2; exit 2; }

record() {
    local status="$1" name="$2"
    if [ "$status" = "pass" ]; then
        PASSES+=("$name"); printf '   \033[32mPASS\033[0m %s\n' "$name"
    else
        FAILURES+=("$name"); printf '   \033[31mFAIL\033[0m %s\n' "$name"
    fi
}

want_stage() {
    local wanted="$1" stage
    for stage in "${STAGES[@]}"; do
        [ "$stage" = "$wanted" ] && return 0
    done
    return 1
}

require_file() {
    [ -f "$1" ] || die "missing required input: $1
This gate refuses to skip a stage. Either provide the input or drop the stage
explicitly with --stage, so a missing negative control can never be mistaken
for a passing one."
}

verify_sha256() {
    local path="$1" expected="$2" what="$3" actual
    actual="$(sha256sum "$path" | awk '{print $1}')"
    [ "$actual" = "$expected" ] || die "$what hash mismatch
  expected $expected
  actual   $actual"
}

# ---------------------------------------------------------------------------
# preflight: fail loudly, never silently degrade
# ---------------------------------------------------------------------------
log "preflight"
command -v docker  >/dev/null || die "docker is required"
command -v ffmpeg  >/dev/null || die "ffmpeg is required"
command -v ffprobe >/dev/null || die "ffprobe is required"
command -v nvidia-smi >/dev/null || die "no nvidia-smi: this gate needs a GPU"
nvidia-smi -L >/dev/null 2>&1 || die "nvidia-smi found no GPU"
# Not `ffmpeg ... | grep -q`: grep exits on the first match, ffmpeg takes
# SIGPIPE, and `set -o pipefail` then reports the whole pipeline as failed even
# though the decoder is present.
decoders="$(ffmpeg -hide_banner -decoders 2>/dev/null)"
case "$decoders" in
    *libdav1d*) ;;
    *) die "ffmpeg has no libdav1d decoder; AV1 film grain needs a
grain-applying decoder or every measurement reads the denoised base instead" ;;
esac
info "GPU     : $(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)"
info "cache   : $CACHE"
info "reports : $REPORT_DIR"
info "stages  : ${STAGES[*]}"

# ---------------------------------------------------------------------------
# stage: tools
# ---------------------------------------------------------------------------
extract_binary() {
    local image="$1" expected="$2" output="$3" container
    if [ -f "$output" ] && \
       [ "$(sha256sum "$output" | awk '{print $1}')" = "$expected" ]; then
        return 0
    fi
    container="$(docker create "$image" 2>/dev/null)" \
        || die "cannot create a container from $image"
    docker cp "$container:$NVENCC_IMAGE_PATH" "$output" >/dev/null 2>&1
    local status=$?
    docker rm "$container" >/dev/null 2>&1
    [ $status -eq 0 ] || die "cannot copy $NVENCC_IMAGE_PATH out of $image"
    chmod +x "$output"
    verify_sha256 "$output" "$expected" "$image"
}

build_candidate_from_pin() {
    # Robustness backlog item 12: never build from the live tree. Three silent
    # failure modes are handled here:
    #   * a clone WITHOUT tags breaks meson (`git describe` exits 128 and
    #     build.ninja is never written);
    #   * a plain clone has empty submodules and dies ~78 files in on
    #     dtl/dtl.hpp, so they are copied from the live tree;
    #   * the container writes the build dir as root, so a retry must use a
    #     FRESH path rather than reusing the old one.
    local commit="$1"
    local pin="$BUILD_DIR/pin-$commit-$(date -u +%s)"
    local submodule_source=""
    log "building candidate from pinned clone $commit"
    git clone --quiet "$REPO" "$pin" || die "clone failed"
    git -C "$pin" checkout --quiet "$commit" || die "no such commit: $commit"

    # A linked worktree has its own empty submodule directories even when the
    # main worktree has the pinned submodules checked out.  Copying from $REPO
    # unconditionally therefore looks successful and then fails at rgy_cmd.cpp
    # with a missing dtl/dtl.hpp. Discover a sibling worktree in the shared
    # repository which has every required submodule populated, and refuse the
    # build if none exists.
    local candidate path populated
    while IFS= read -r line; do
        case "$line" in
            "worktree "*)
                candidate="${line#worktree }"
                populated=1
                while read -r _ path; do
                    [ -n "$path" ] || continue
                    if [ ! -d "$candidate/$path" ] || \
                       [ -z "$(find "$candidate/$path" -mindepth 1 \
                                      -maxdepth 1 -print -quit 2>/dev/null)" ]; then
                        populated=0
                        break
                    fi
                done < <(git -C "$REPO" config --file .gitmodules \
                               --get-regexp path)
                if [ "$populated" -eq 1 ]; then
                    submodule_source="$candidate"
                    break
                fi
                ;;
        esac
    done < <(git -C "$REPO" worktree list --porcelain)
    [ -n "$submodule_source" ] || die "no worktree has every submodule populated"
    info "submodules      : $submodule_source"

    while read -r _ path; do
        [ -n "$path" ] || continue
        cp -a "$submodule_source/$path" "$pin/$(dirname "$path")/"
    done < <(git -C "$REPO" config --file .gitmodules --get-regexp path)
    docker run --rm --gpus all -v "$pin:/work" -w /work "$BUILD_IMAGE" \
        bash -lc 'git config --global --add safe.directory /work
                  apt-get update -qq
                  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
                      libass-dev libx11-dev libplacebo-dev
                  export PATH=/usr/local/cuda/bin:$PATH
                  meson setup build-gate . --buildtype=release \
                      -Denable_vmaf=disabled -Denable_libvship=disabled \
                  && ninja -C build-gate' \
        || die "candidate build failed; retry with a fresh path (the container
writes the build directory as root, so the old one cannot be removed as you)"
    CANDIDATE_NVENCC="$pin/build-gate/nvencc"
    [ -x "$CANDIDATE_NVENCC" ] || die "build produced no nvencc"
}

if want_stage tools; then
    log "stage: tools"

    R4050="$BIN_DIR/nvencc-r4050"
    R4047="$BIN_DIR/nvencc-r4047"
    extract_binary "$REF_R4050_IMAGE" "$REF_R4050_SHA256" "$R4050"
    extract_binary "$NEG_R4047_IMAGE" "$NEG_R4047_SHA256" "$R4047"
    info "r4050 corrected : $R4050"
    info "r4047 negative  : $R4047"

    # libaom, pinned by revision. A distro package would silently compare
    # against a different analyzer; pinning is what makes the oracle an oracle.
    AOM_NOISE_MODEL="$AOM_DIR/build/noise_model"
    if [ ! -x "$AOM_NOISE_MODEL" ]; then
        info "building pinned libaom $AOM_REVISION (absent from cache)"
        rm -rf "$AOM_DIR"
        AOM_REF_REVISION="$AOM_REVISION" "$HERE/build_aom_reference.sh" "$AOM_DIR" \
            || die "libaom reference build failed"
    fi
    [ -x "$AOM_NOISE_MODEL" ] || die "libaom noise_model missing after build"
    info "libaom oracle   : $AOM_NOISE_MODEL ($AOM_REVISION)"

    if [ -n "$CANDIDATE_COMMIT" ]; then
        build_candidate_from_pin "$CANDIDATE_COMMIT"
    fi
    if [ -z "$CANDIDATE_NVENCC" ]; then
        CANDIDATE_NVENCC="$R4050"
        info "candidate       : none given, testing the pinned r4050 reference"
    fi
    [ -x "$CANDIDATE_NVENCC" ] || die "candidate binary is not executable: $CANDIDATE_NVENCC"
    info "candidate       : $CANDIDATE_NVENCC"
    info "candidate sha256: $(sha256sum "$CANDIDATE_NVENCC" | awk '{print $1}')"
else
    R4050="$BIN_DIR/nvencc-r4050"
    R4047="$BIN_DIR/nvencc-r4047"
    AOM_NOISE_MODEL="$AOM_DIR/build/noise_model"
    [ -n "$CANDIDATE_NVENCC" ] || CANDIDATE_NVENCC="$R4050"
fi

# ---------------------------------------------------------------------------
# stage: kat -- 18 bilateral GPU fixtures
# ---------------------------------------------------------------------------
if want_stage kat; then
    log "stage: kat (GPU known-answer fixtures)"
    info "these passed throughout both shipped regressions; they bound the"
    info "synthetic behaviour only, and cannot see real-film aliasing"
    if NVENCC="$CANDIDATE_NVENCC" FGS_KAT_DIR="$REPORT_DIR/kat" \
            python3 "$HERE/fgs_kat.py" > "$REPORT_DIR/kat.log" 2>&1; then
        record pass "kat: all GPU fixtures"
    else
        record fail "kat: all GPU fixtures (see $REPORT_DIR/kat.log)"
        tail -25 "$REPORT_DIR/kat.log"
    fi
fi

# ---------------------------------------------------------------------------
# stage: synthetic_oracle -- libaom on generated fixtures
# ---------------------------------------------------------------------------
if want_stage synthetic_oracle; then
    log "stage: synthetic oracle (libaom, generated fixtures)"
    [ -x "$AOM_NOISE_MODEL" ] || die "libaom oracle missing; run the tools stage"
    if AOM_NOISE_MODEL="$AOM_NOISE_MODEL" \
       AOM_NOISE_MODEL_REVISION="$AOM_REVISION" \
       python3 "$HERE/reference_compare.py" \
            --nvencc "$CANDIDATE_NVENCC" \
            --aom-noise-model "$AOM_NOISE_MODEL" \
            --aom-revision "$AOM_REVISION" \
            --output "$REPORT_DIR/reference-synthetic.json" \
            > "$REPORT_DIR/reference-synthetic.log" 2>&1; then
        record pass "synthetic oracle vs libaom"
    else
        record fail "synthetic oracle vs libaom (see $REPORT_DIR/reference-synthetic.log)"
        tail -25 "$REPORT_DIR/reference-synthetic.log"
    fi
fi

# ---------------------------------------------------------------------------
# stage: model_negative -- LABELLED NEGATIVE 3, the adversarial specimen
#
# No GPU and no encoding: this is descriptor mathematics on a stored source
# residual, so it is cheap enough for a pre-push hook. It needs the Taxi raw
# pair, which is why it is tier 2 and not CI.
# ---------------------------------------------------------------------------
if want_stage model_negative; then
    log "stage: texture model gate (labelled negative: metric-gamer)"
    require_file "$TAXI_SRC"; require_file "$TAXI_CLEAN"
    require_file "$TAXI_MODEL"; require_file "$CEILING_MODEL"

    info "negative control: the optimised specimen beats the gated descriptors"
    info "by ~3x and must still be rejected on the held-out ones"
    if python3 "$HERE/model_gate.py" \
            --source "$TAXI_SRC" --clean "$TAXI_CLEAN" \
            --incumbent "$TAXI_MODEL" --candidate "$CEILING_MODEL" \
            --expect reject \
            --json-out "$REPORT_DIR/model-gate-ceiling.json" \
            > "$REPORT_DIR/model-gate-ceiling.log" 2>&1; then
        record pass "model gate REJECTS taxi_ceiling_q.json"
    else
        record fail "model gate did not reject taxi_ceiling_q.json -- the gate
        is measuring the wrong thing (see $REPORT_DIR/model-gate-ceiling.log)"
        tail -20 "$REPORT_DIR/model-gate-ceiling.log"
    fi

    info "positive control: a gate that rejects everything is not a gate"
    if python3 "$HERE/model_gate.py" \
            --source "$TAXI_SRC" --clean "$TAXI_CLEAN" \
            --incumbent "$TAXI_MODEL" --candidate "$TAXI_MODEL" \
            --expect accept \
            --json-out "$REPORT_DIR/model-gate-self.json" \
            > "$REPORT_DIR/model-gate-self.log" 2>&1; then
        record pass "model gate ACCEPTS the shipping model"
    else
        record fail "model gate rejected the shipping model (see $REPORT_DIR/model-gate-self.log)"
        tail -20 "$REPORT_DIR/model-gate-self.log"
    fi
fi

# ---------------------------------------------------------------------------
# stage: real_oracle -- libaom on real film, occupancy-weighted
#
# This is the stage that actually caught the 2026-07-29 sampling defect. The
# fixtures did not, because synthetic fine grain does not alias against the
# lattice; only coarse real film does.
# ---------------------------------------------------------------------------
if want_stage real_oracle; then
    log "stage: real-film oracle (libaom, occupancy-weighted)"
    [ -x "$AOM_NOISE_MODEL" ] || die "libaom oracle missing; run the tools stage"
    require_file "$TAXI_CLIP"
    if python3 "$HERE/reference_compare_real.py" \
            --nvencc "$CANDIDATE_NVENCC" \
            --aom-noise-model "$AOM_NOISE_MODEL" \
            --frames 24 --denoiser bilateral --texture \
            --work "$REPORT_DIR/real-oracle-work" \
            --json-out "$REPORT_DIR/reference-real.json" \
            > "$REPORT_DIR/reference-real.log" 2>&1; then
        record pass "real-film oracle vs libaom"
    else
        record fail "real-film oracle vs libaom (see $REPORT_DIR/reference-real.log)"
        tail -30 "$REPORT_DIR/reference-real.log"
    fi
    # A fine-grain-only pass recreates the blind spot this stage closes.
    if grep -q "no COARSE clip passed" "$REPORT_DIR/reference-real.log" 2>/dev/null; then
        record fail "real-film oracle covered no coarse clip -- aliasing bias is
        scale-dependent and fine grain cannot detect it"
    fi
fi

# ---------------------------------------------------------------------------
# stage: texture_negative -- LABELLED NEGATIVE 1 (texture half)
# ---------------------------------------------------------------------------
if want_stage texture_negative; then
    log "stage: texture detector (labelled negative: r4047 widening)"
    require_file "$TAXI_CLIP"
    [ -x "$R4047" ] || die "r4047 negative binary missing; run the tools stage"
    [ -x "$R4050" ] || die "r4050 reference binary missing; run the tools stage"

    work="$REPORT_DIR/texture-negative"
    mkdir -p "$work"
    frames="${FGS_GATE_TEXTURE_FRAMES:-24}"
    fail=0

    # 1. Each analyzer measures the SAME source and writes its own table.
    #    --codec raw ... -o /dev/null runs the analyzer without encoding.
    for build in r4050 r4047; do
        binary="$R4050"; [ "$build" = "r4047" ] && binary="$R4047"
        "$binary" --codec raw --output-depth 10 \
            --av1-film-grain "denoise=auto,chroma=auto,denoiser=bilateral" \
            --film-grain-table-out "$work/$build.tbl" \
            -i "$TAXI_CLIP" --frames "$frames" -o /dev/null \
            > "$work/$build-analyze.log" 2>&1 || fail=1
    done

    # 2. One clean base, produced once by r4050. Both arms are then synthesised
    #    on top of THIS base, so the only difference between them is the grain
    #    table. Encoding the original grainy source instead would leave source
    #    grain under the synthesis and the comparison would measure nothing.
    if [ "$fail" -eq 0 ]; then
        "$R4050" --codec raw --output-depth 10 \
            --av1-film-grain "denoise=auto,chroma=auto,denoiser=bilateral" \
            -i "$TAXI_CLIP" --frames "$frames" -o "$work/clean.y4m" \
            > "$work/clean.log" 2>&1 || fail=1
    fi

    if [ "$fail" -ne 0 ]; then
        record fail "texture negative: analysis pass failed (see $work)"
    else
        # 3. Apply each table to that one clean base with the same encoder.
        #    --film-grain-table only signals synthesis; it does not denoise,
        #    which is why the input here must already be the clean base.
        for build in r4050 r4047; do
            "$R4050" --codec av1 --qvbr 29 --output-depth 10 \
                --film-grain-table "$work/$build.tbl" \
                -i "$work/clean.y4m" -o "$work/$build-applied.mkv" \
                > "$work/$build-apply.log" 2>&1 || fail=1
        done
        if [ "$fail" -ne 0 ]; then
            record fail "texture negative: could not apply both tables (see $work)"
        # --require-common-base turns "the two arms share a base" from a hope
        # into a hard requirement: it fails unless both grain-off decodes are
        # byte-identical.
        elif python3 "$HERE/texture_media_report.py" \
                --source "$TAXI_CLIP" --clean "$work/clean.y4m" \
                --arm corrected="$work/r4050-applied.mkv" \
                --arm widened="$work/r4047-applied.mkv" \
                --frames "$frames" \
                --labelled-negative widened,corrected \
                --require-common-base \
                --output "$REPORT_DIR/texture-negative.json" \
                > "$REPORT_DIR/texture-negative.log" 2>&1; then
            record pass "texture detector separates r4047 from r4050"
        else
            record fail "texture detector did NOT separate the known r4047
        change -- the detector is blind (see $REPORT_DIR/texture-negative.log)"
            tail -25 "$REPORT_DIR/texture-negative.log"
        fi
    fi
fi

# ---------------------------------------------------------------------------
# stage: canary_negative -- LABELLED NEGATIVES 1 and 2 (base-fidelity half)
# ---------------------------------------------------------------------------
if want_stage canary_negative; then
    log "stage: base-fidelity canary (labelled negatives: r4047, Casino)"
    [ -x "$CANARY" ] || die "base-fidelity canary not found at $CANARY"

    run_canary() {  # image -> exit status, output on stdout
        local image="$1" label="$2" container status
        container="$(docker create "$image" 2>/dev/null)" \
            || { echo "cannot create container from $image" >&2; return 3; }
        GRAIN_CANARY_CONTAINER="$container" \
        GRAIN_CANARY_REPORT_DIR="$REPORT_DIR/canary-$label" \
            "$CANARY" > "$REPORT_DIR/canary-$label.log" 2>&1
        status=$?
        docker rm "$container" >/dev/null 2>&1
        return $status
    }

    info "negative control: r4047 contains the rejected widening and must ALERT"
    info "(measured: SSIMULACRA2 -0.872, Butteraugli +0.030, exit 1)"
    run_canary "$NEG_R4047_IMAGE" r4047
    status=$?
    if [ "$status" -eq 1 ] && grep -q "ALERT" "$REPORT_DIR/canary-r4047.log"; then
        record pass "canary ALERTS on r4047"
    elif [ "$status" -eq 3 ]; then
        record fail "canary could not run against r4047 (docker create failed)"
    else
        record fail "canary did not alert on r4047 (exit $status) -- the
        substitution detector cannot see the regression it was built for
        (see $REPORT_DIR/canary-r4047.log)"
        tail -20 "$REPORT_DIR/canary-r4047.log"
    fi

    info "positive control: r4050 is the corrected build and must be clean"
    run_canary "$REF_R4050_IMAGE" r4050
    status=$?
    if [ "$status" -eq 0 ]; then
        record pass "canary is clean on r4050"
    else
        record fail "canary alerted on the corrected r4050 build (exit $status)
        (see $REPORT_DIR/canary-r4050.log)"
        tail -20 "$REPORT_DIR/canary-r4050.log"
    fi

    # LABELLED NEGATIVE 2. Casino's measured grain retention is 1.035/0.979/
    # 1.034 across three scenes -- as good as anything in the library -- on a
    # file whose base had been smoothed and its texture substituted. Retention
    # passes it; base fidelity must not. This is file mode, which deliberately
    # has no universal alert threshold, so the assertion is on the direction of
    # the delta rather than on a bound.
    if [ -f "$CASINO_WIDENED" ] && [ -f "$CASINO_SOURCE" ]; then
        info "forensic control: the widened Casino encode has PERFECT retention"
        if python3 "$DOCKER_APPS/scripts/grain-base-fidelity.py" \
                "$CASINO_SOURCE" "$CASINO_WIDENED" \
                --reference-image "$REF_R4050_IMAGE" \
                --expect-reference-sha256 "$REF_R4050_SHA256" \
                --json "$REPORT_DIR/casino-base-fidelity.json" \
                > "$REPORT_DIR/casino-base-fidelity.log" 2>&1; then
            if python3 - "$REPORT_DIR/casino-base-fidelity.json" <<'PY'
import json, sys
report = json.load(open(sys.argv[1]))
delta = report.get("delta", report)
ssimu2 = delta.get("ssimu2_mean")
if ssimu2 is None:
    print("no ssimu2_mean in the report", file=sys.stderr); sys.exit(2)
print(f"casino SSIMULACRA2 mean delta {ssimu2:+.3f}")
# Negative means the library base is worse than the freshly encoded control,
# which is the substitution signature. A positive delta here would mean base
# fidelity agrees with retention that the file is fine, and the axis that
# caught this regression has stopped working.
sys.exit(0 if ssimu2 < 0 else 1)
PY
            then
                record pass "base fidelity sees the widened Casino base as worse"
            else
                record fail "base fidelity did NOT see the widened Casino base
        as worse -- retention already passes this file, so nothing would catch
        it (see $REPORT_DIR/casino-base-fidelity.json)"
            fi
        else
            record fail "casino base-fidelity measurement failed (see $REPORT_DIR/casino-base-fidelity.log)"
            tail -20 "$REPORT_DIR/casino-base-fidelity.log"
        fi
    else
        record fail "the Casino negative control is not available:
          encode: $CASINO_WIDENED
          source: $CASINO_SOURCE
        Keep rejected builds and bad outputs; they are the only honest negative
        controls a quality monitor gets."
    fi
fi

# ---------------------------------------------------------------------------
log "summary"
for name in "${PASSES[@]}"; do printf '   \033[32mPASS\033[0m %s\n' "$name"; done
for name in "${FAILURES[@]}"; do printf '   \033[31mFAIL\033[0m %s\n' "$name"; done
printf '\n   %d passed, %d failed\n   reports: %s\n' \
    "${#PASSES[@]}" "${#FAILURES[@]}" "$REPORT_DIR"

if [ "${#PASSES[@]}" -eq 0 ]; then
    echo "
local_gate: nothing ran. That is a failure, not a pass." >&2
    exit 2
fi
[ "${#FAILURES[@]}" -eq 0 ] || exit 1
exit 0
