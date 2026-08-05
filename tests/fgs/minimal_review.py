#!/usr/bin/env python3
"""Distil the motion playback gate to the shortest decisive clip.

The gate has been open since 2026-08-02 and the packages have not been watched.
They are 4.7--5.1 GiB and ask for timecoded observations across four titles.
That is the barrier, not the question: every remaining blocker in this project
terminates at one perceptual judgement that full-reference metrics are provably
unable to make -- production wins base SSIMULACRA2 and Butteraugli on 6/6 while
the candidate wins base VMAF on 6/6, and the disagreement is precisely about
retained grain-like structure.

So this picks the moment where ghosting, if present, is most measurable, and
cuts one short side-by-side from the existing review files.  Nothing is
re-encoded from source: the crops come from the sealed package, so the A/B
labels and their mapping are untouched.

Selection is data-driven.  ``temporal_drag.py`` reports per-frame joint
previous/next projection; the window with the largest sustained lag asymmetry
on the arm that has any is where a trailing edge would show.  Ranking uses the
grain-disabled ``base`` pair, because synthesis only masks the question.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FFMPEG = os.environ.get("FGS_FFMPEG", "/usr/local/bin/ffmpeg")
# the CUDA/dav1d build carries no libx264; the review cut needs it
X264_FFMPEG = os.environ.get("FGS_X264_FFMPEG", "/usr/bin/ffmpeg")
PACKAGE = ("/media/merged-storage/media/test-encodes/"
           "sourcefit-motion-finish-review-20260803/blind")
REFS = "/media/merged-storage/media/test-encodes/review-vmaf-20260802"
TITLES = ("The_Deer_Hunter", "The_Shining", "Scarface", "Taxi_Driver")


def run(cmd, log=None):
    proc = subprocess.run([str(p) for p in cmd], capture_output=True, text=True,
                          timeout=7200)
    if log:
        with open(log, "w", encoding="utf-8") as handle:
            handle.write(proc.stdout + proc.stderr)
    if proc.returncode != 0:
        raise RuntimeError(f"failed: {' '.join(str(p) for p in cmd[:8])}\n"
                           f"{(proc.stdout + proc.stderr)[-2500:]}")
    return proc.stdout


def per_frame_drag(reference, base, frames, out_json):
    """Per-frame lag asymmetry of one arm's base against the reference."""
    if not os.path.isfile(out_json):
        run([sys.executable, os.path.join(HERE, "temporal_drag.py"),
             reference, base, str(frames), "--output", out_json])
    with open(out_json, encoding="utf-8") as handle:
        return json.load(handle)


def worst_window(per_frame, length, key="lag_asymmetry"):
    """Centre of the highest mean-|asymmetry| window of `length` frames."""
    values = []
    for row in per_frame:
        value = row.get(key)
        if value is None:
            for candidate in ("asymmetry", "lag", "previous"):
                if row.get(candidate) is not None:
                    value = row[candidate]
                    break
        values.append((row["frame"], abs(value) if value is not None else 0.0))
    best, best_score = 0, -1.0
    for start in range(0, max(1, len(values) - length + 1)):
        window = values[start:start + length]
        score = sum(v for _, v in window) / len(window)
        if score > best_score:
            best, best_score = window[0][0], score
    return best, best_score


def divergence_windows(left, right, frames, length, width=1920, height=1080):
    """Mean |A-B| per frame, on 8x8 box means, and the best window.

    Directional lag is no longer the right target: both arms of the current
    candidate measure 0.00003..0.0039 lag asymmetry, inside the bilateral band
    of 0.00010..0.00036 and far below the 0.118..0.141 of the motion arm the
    review packages were built for.  The open disagreement is instead whether
    retained grain-like structure in the base is detail or residue, so the
    useful window is simply where the two bases differ most -- that is where a
    viewer has any chance of seeing which.
    """
    import numpy as np
    from temporal_grain_report import decode_selected
    # Subsample: 280 4K-decoded frames at once exhausts memory, and window
    # choice does not need every frame.  Every 4th is ample.
    step = 4
    indices = list(range(0, frames, step))
    # The package clips are lossless FFV1 copies of the grain-disabled decode,
    # not AV1, so filmgrain= must not be passed: it would force libdav1d.
    a = decode_selected(left, width, height, indices, bits=10)
    b = decode_selected(right, width, height, indices, bits=10)
    per = [(i, float(np.abs(a[i] - b[i]).mean())) for i in indices]
    span = max(1, length // step)
    best, best_score = 0, -1.0
    for start in range(0, max(1, len(per) - span + 1)):
        window = per[start:start + span]
        score = sum(v for _, v in window) / len(window)
        if score > best_score:
            best, best_score = window[0][0], score
    return best, best_score, per


def cut_side_by_side(left, right, start, count, out, fps, log):
    """One clip, both arms, no labels burned in -- the package stays sealed."""
    if os.path.isfile(out):
        return out
    run([X264_FFMPEG, "-hide_banner", "-nostdin", "-v", "error",
         "-i", left, "-i", right,
         "-filter_complex",
         f"[0:v]trim=start_frame={start}:end_frame={start + count},setpts=PTS-STARTPTS[l];"
         f"[1:v]trim=start_frame={start}:end_frame={start + count},setpts=PTS-STARTPTS[r];"
         f"[l][r]hstack=inputs=2,scale=1920:-2[v]",
         "-map", "[v]", "-r", str(fps), "-c:v", "libx264", "-preset", "slow",
         "-crf", "12", "-pix_fmt", "yuv420p", "-y", out], log=log)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", default=PACKAGE)
    parser.add_argument("--out", default="/media/merged-storage/media/"
                        "test-encodes/minimal-review-20260805")
    parser.add_argument("--titles", default="")
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--fps", type=float, default=23.976)
    parser.add_argument("--frames", type=int, default=280)
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    length = int(round(args.seconds * args.fps))
    ranked = []
    for title in (args.titles.split(",") if args.titles else TITLES):
        a = os.path.join(args.package, f"{title}-A-base.mkv")
        b = os.path.join(args.package, f"{title}-B-base.mkv")
        ref = os.path.join(REFS, f"{title}-ref.mkv")
        if not (os.path.isfile(a) and os.path.isfile(b) and os.path.isfile(ref)):
            print(f"MISSING {title}", flush=True)
            continue
        # Each arm against the true source, not against each other: the
        # A-vs-B projection would measure their difference, not either one's
        # lag.  Whichever arm carries asymmetry decides where to look; the
        # label is never printed, so the package stays sealed.
        docs = {}
        for label, path in (("A", a), ("B", b)):
            docs[label] = per_frame_drag(
                ref, path, args.frames,
                os.path.join(args.out, f"{title}-{label}-drag.json"))
        overall = {k: (v.get("projection") or {}).get("lag_asymmetry")
                   for k, v in docs.items()}
        if all(value is None for value in overall.values()):
            raise RuntimeError("no lag_asymmetry in projection; drag JSON shape "
                               "changed and the arm choice would be arbitrary")
        lagging = max(overall, key=lambda k: abs(overall[k] or 0.0))
        lag_start, lag_score = worst_window(
            docs[lagging].get("per_frame", []), length)
        start, score, _ = divergence_windows(a, b, args.frames, length)
        ranked.append({"title": title, "start_frame": start,
                       "window_score": score,
                       "arm_overall_lag_asymmetry": overall,
                       "lag_ranked_start": lag_start,
                       "lag_window_score": lag_score,
                       "ranked_on": "mean |A-B| on grain-disabled bases"})
        print(json.dumps(ranked[-1], default=str)[:400], flush=True)

    ranked.sort(key=lambda row: -row["window_score"])
    for row in ranked:
        title = row["title"]
        out = os.path.join(args.out, f"{title}-worst.mp4")
        cut_side_by_side(os.path.join(args.package, f"{title}-A-base.mkv"),
                         os.path.join(args.package, f"{title}-B-base.mkv"),
                         row["start_frame"], length, out, args.fps,
                         os.path.join(args.out, f"{title}-cut.log"))
        row["clip"] = out
        row["bytes"] = os.path.getsize(out)
        print(f"{title}: frames {row['start_frame']}..{row['start_frame']+length} "
              f"-> {out} ({row['bytes']:,} bytes)", flush=True)

    with open(os.path.join(args.out, "ranking.json"), "w",
              encoding="utf-8") as handle:
        json.dump(ranked, handle, indent=1)


if __name__ == "__main__":
    main()
