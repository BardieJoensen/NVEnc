#!/bin/bash
# Prove the tier-1 CPU suite can fail.
#
# WHY THIS EXISTS
# Both defects that reached production on 2026-07-29/30 were invisible to every
# signal that was being watched: file sizes fell, VMAF and SSIMULACRA2 rose, and
# all 17-18 GPU fixtures passed.  The lesson recorded in
# /opt/docker-apps/docs/fgs-open-questions.md is that a monitor which has only
# ever seen good inputs is indistinguishable from one that cannot fail.  That
# applies to the automation itself: a green tick from a suite that is silently
# not running anything is worse than no tick at all.
#
# So this script injects known defects into a scratch copy of the tree and
# requires run_cpu_tests.sh to reject each one.  Mutation 1 is the real
# 2026-07-29 defect -- the fixed sampling lattice that inflated the fitted AR
# gain about 2x and halved signalled grain strength on coarse 35mm film.
#
# This is not mutation-test coverage; it is a wiring check on each leg of the
# suite (C++ solver, C++ parser, Python texture descriptors).  A mutation whose
# pattern no longer matches is a hard error, never a silent skip: that is
# exactly how a check quietly stops checking.

set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/fgs-selftest-XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# file : sed expression : literal pattern that must be present : description
MUTATIONS=(
  "NVEncCore/NVEncFilmGrainModel.h:s|random % static_cast<uint32_t>(span)|0u|:random % static_cast<uint32_t>(span):fixed sampling lattice (the shipped 2026-07-29 defect)"
  "NVEncCore/NVEncFilmGrain.cpp:s|if (x <= previousValue) {|if (false) {|:if (x <= previousValue) {:parser stops rejecting non-monotonic scaling points"
  "tests/fgs/texture_metrics.py:s|/ (2.0 \* variance)|/ 2.0|:/ (2.0 * variance):texture ACF stops being amplitude-independent"
)

failed=0
index=0
for mutation in "${MUTATIONS[@]}"; do
    index=$((index + 1))
    file="${mutation%%:*}"
    rest="${mutation#*:}"
    expression="${rest%%:*}"
    rest="${rest#*:}"
    pattern="${rest%%:*}"
    description="${rest#*:}"

    printf '\n[%d/%d] %s\n      %s\n' \
        "$index" "${#MUTATIONS[@]}" "$description" "$file"

    tree="$WORK/mutation-$index"
    mkdir -p "$tree"
    cp -a "$REPO/NVEncCore" "$REPO/NVEncSDK" "$REPO/tests" "$tree/"

    if ! grep -qF -- "$pattern" "$tree/$file"; then
        echo "      ERROR: mutation site not found in $file" >&2
        echo "      looked for: $pattern" >&2
        echo "      The code moved. Update the mutation rather than deleting it;" >&2
        echo "      an unverifiable suite is the failure mode this guards." >&2
        failed=1
        continue
    fi

    sed -i "$expression" "$tree/$file"
    if ! grep -qF -- "$pattern" "$tree/$file"; then
        : # the mutation applied, as expected
    else
        echo "      ERROR: sed did not change $file" >&2
        failed=1
        continue
    fi

    if TMPDIR="$tree" bash "$tree/tests/fgs/run_cpu_tests.sh" \
            > "$tree/output.log" 2>&1; then
        echo "      NOT CAUGHT: the suite passed with a known defect present" >&2
        tail -20 "$tree/output.log" >&2
        failed=1
    else
        echo "      caught (suite exited non-zero)"
    fi
done

echo
if [ "$failed" -ne 0 ]; then
    echo "meta-check FAILED: the CPU suite does not reject every injected defect" >&2
    exit 1
fi
echo "meta-check passed: ${#MUTATIONS[@]} injected defects, all rejected"
