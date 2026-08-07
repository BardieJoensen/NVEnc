#!/usr/bin/env python3
"""How many routes does the flow need, and what does VMAF 95 cost?

Two questions in one sweep, because both need the same rate-quality curves.

**1. Is one extra route enough?**  `cq29` is reached by the 4K override *and*
by the fall-through for everything without an animation NFO, and those want
different values: 4K film validated at 28, clean digital at ~30.1 (28.8 / 31.2
/ 30.4).  Adding one branch fixes that only if each resulting group is
internally tight.  Two things could still be lumped:

* the 4K override is *resolution*-based, so a 4K film remux and a 4K streaming
  episode take the same branch despite very different source characteristics;
* "clean digital" spans bright studio (Big Brother), mixed drama (Star Trek)
  and dark low-motion drama (Silo), whose first sweep already spread 28.8--31.2.

So this sweeps both 4K classes separately and widens the clean-digital sample.
If a group's spread is comparable to the gap between groups, further splitting
buys nothing and the answer is "one extra route is enough".

**2. What does moving to VMAF 95 cost?**  The buckets currently reproduce the
*old* quality.  Targeting a fixed VMAF instead is a different question, and the
existing sweeps top out around 91--94, so this extends low enough to bracket 95
rather than extrapolating past the measured range.

VMAF-neg is the working metric throughout -- FGS is on in every arm and the
default model pays an enhancement bonus for synthesized grain -- so the target
is stated in both: the run reports the qvbr for `vmaf_neg 95` and for `vmaf 95`,
which differ by roughly the measured neg gap (0.4--1.2 depending on content).

Sources are originals.  Cut once and encode from the cut.  Scoring goes through
the vmaf binary; `campaign.score`'s cache bug is fixed (`fa0c0d8e`) but this
keeps the direct path for continuity with the earlier sweeps.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from animation_bucket_calibration import cut, encode, interpolate, resolve

BIN = Path("/opt/docker-apps/build/tdarr-node/nvencc")
VMAF = Path.home() / "git-repos/vmaf/libvmaf/build/tools/vmaf"
OUT = Path("/tmp/downloads/route-target-20260807")
SEED_TV = Path("/media/merged-storage/media/downloads/long-term-seeding/tv-shows")
DL_TV = Path("/tmp/downloads/tv-shows")

# class -> (title -> source).  The class is the routing question; the titles
# inside it are the "is this group tight enough" question.
CLASSES = {
    "4K_film": {
        "Alien_1979": Path("/tmp/downloads/movies/"
            "Alien.1979.Directors.Cut.UHD.BluRay.2160p.DTS-HD.MA.5.1.HEVC.REMUX-FraMeSToR/"
            "Alien.1979.Directors.Cut.UHD.BluRay.2160p.DTS-HD.MA.5.1.HEVC.REMUX-FraMeSToR.mkv"),
    },
    "4K_webdl": {
        # Non-DV variant deliberately: DV dual-layer HEVC scores as garbage
        # through FFMS2 and is a known trap in this project's notes.
        "HotD_S03E07": SEED_TV / "House.of.the.Dragon.S03E07.2160p.HMAX.WEB-DL.DDP5.1.Atmos.H.265-N1H4L.mkv",
    },
    "clean_1080p": {
        "Silo_S03E06": DL_TV / "Silo.S03E06.The.Drive.1080p.ATVP.WEB-DL.DDP5.1.Atmos.H.264-playWEB.mkv",
        "StarTrek_SNW": DL_TV / ("Star.Trek.Strange.New.Worlds.S04E03.Human.Best.Friend."
                                 "1080p.AMZN.WEB-DL.DDP5.1.H.264-FLUX.mkv"),
        "BigBrother": DL_TV / "Big.Brother.US.S28E14.1080p.AMZN.WEB-DL.DDP2.0.H.264-NTb.mkv",
        "CapeFear": SEED_TV / ("Cape.Fear.S01E05.Faith.1080p.ATVP.WEB-DL.DDP5.1.Atmos."
                               "H.264-BYNDR.mkv"),
        "AbbottElementary": SEED_TV / "Abbott.Elementary.S04.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb",
    },
    "animation": {
        "Elemental": Path("/tmp/downloads/movies/"
            "Elemental 2023 BluRay 1080p TrueHD Atmos 7 1 AVC HYBRID REMUX-FraMeSToR/"
            "Elemental.2023.BluRay.1080p.TrueHD.Atmos.7.1.AVC.HYBRID.REMUX-FraMeSToR/"
            "Elemental.2023.BluRay.1080p.TrueHD.Atmos.7.1.AVC.HYBRID.REMUX-FraMeSToR.mkv"),
        "LongHalloween": Path("/media/merged-storage/media/downloads/long-term-seeding/movies/"
            "Batman The Long Halloween 2021 Deluxe Edition BluRay 1080p DTS-HD MA 5 1 AVC REMUX-FraMeSToR"),
    },
}

# What each class maps to today, and what its bucket used to be.
DEPLOYED = {"4K_film": 28, "4K_webdl": 28, "clean_1080p": 28, "animation": 34}
OLD_BUCKET = {"4K_film": 29, "4K_webdl": 29, "clean_1080p": 29, "animation": 34}

# Wide enough to bracket vmaf_neg 95 at the low end without extrapolating.
SWEEP = (20, 24, 28, 32, 36)


def vmaf_pair(ref: Path, enc: Path, height: int, work: Path) -> tuple[float, float]:
    model = "vmaf_4k_v0.6.1" if height > 1200 else "vmaf_v0.6.1"
    r_y4m, d_y4m, out = work / "r.y4m", work / "d.y4m", work / "o.json"
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(ref), "-pix_fmt", "yuv420p10le",
                    "-f", "yuv4mpegpipe", "-strict", "-1", "-y", str(r_y4m)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-c:v", "libdav1d", "-i", str(enc),
                    "-pix_fmt", "yuv420p10le", "-f", "yuv4mpegpipe", "-strict", "-1",
                    "-y", str(d_y4m)], check=True)
    r = subprocess.run([str(VMAF), "--reference", str(r_y4m), "--distorted", str(d_y4m),
                        "--model", f"version={model}:name=vmaf",
                        "--model", f"version={model}neg:name=vmaf_neg",
                        "--json", "--output", str(out)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"vmaf failed on {enc.name}: {r.stderr[-500:]}")
    d = json.loads(out.read_text())["pooled_metrics"]
    for f in (r_y4m, d_y4m):
        f.unlink(missing_ok=True)
    return d["vmaf"]["mean"], d["vmaf_neg"]["mean"]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--seek", type=float, default=900.0)
    p.add_argument("--frames", type=int, default=144)
    p.add_argument("--target", type=float, default=95.0)
    args = p.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    work = OUT / "work"; work.mkdir(exist_ok=True)
    report: dict[str, dict] = {}

    for cls, titles in CLASSES.items():
        for name, raw in titles.items():
            source = resolve(raw)
            if source is None:
                print(f"skip {name}: no source at {raw}", file=sys.stderr)
                continue
            height = json.loads(subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                 "stream=height", "-of", "json", str(source)],
                capture_output=True, text=True).stdout)["streams"][0]["height"]
            ref = OUT / f"{name}-ref.mkv"
            cut(source, ref, args.seek, args.frames)
            print(f"\n### [{cls}] {name} ({height}p)", flush=True)

            base = OUT / f"{name}-old-q{OLD_BUCKET[cls]}.mkv"
            bsize = encode(ref, base, OLD_BUCKET[cls], lookahead=False)
            _, bneg = vmaf_pair(ref, base, height, work)
            print(f"  baseline qvbr{OLD_BUCKET[cls]} no-LA  {bsize/1e6:8.2f}MB  "
                  f"neg {bneg:6.2f}", flush=True)

            row = {"class": cls, "height": height, "baseline_bytes": bsize,
                   "baseline_neg": bneg, "sweep": {}}
            pts_neg, pts_vmaf, sizes = [], [], {}
            for q in SWEEP:
                enc = OUT / f"{name}-q{q}.mkv"
                size = encode(ref, enc, q, lookahead=True)
                v, n = vmaf_pair(ref, enc, height, work)
                pts_neg.append((q, n)); pts_vmaf.append((q, v)); sizes[q] = size
                row["sweep"][q] = {"bytes": size, "vmaf": v, "vmaf_neg": n}
                print(f"  qvbr{q:<3} LA            {size/1e6:8.2f}MB  "
                      f"vmaf {v:6.2f}  neg {n:6.2f}", flush=True)

            def size_at(qv):
                if qv is None:
                    return None
                lo = max([q for q in SWEEP if q <= qv], default=min(SWEEP))
                hi = min([q for q in SWEEP if q >= qv], default=max(SWEEP))
                if lo == hi:
                    return sizes[lo]
                f = (qv - lo) / (hi - lo)
                return sizes[lo] + f * (sizes[hi] - sizes[lo])

            row["match_old_qvbr"] = interpolate(pts_neg, bneg)
            row["target_neg_qvbr"] = interpolate(pts_neg, args.target)
            row["target_vmaf_qvbr"] = interpolate(pts_vmaf, args.target)
            row["target_neg_bytes"] = size_at(row["target_neg_qvbr"])
            row["target_vmaf_bytes"] = size_at(row["target_vmaf_qvbr"])
            report[name] = row

    (OUT / "route-target.json").write_text(json.dumps(report, indent=2) + "\n")

    print(f"\n=== 1. routing: qvbr reproducing each title's OLD quality ===")
    print(f"{'class':14} {'title':18} {'qvbr':>6}   deployed")
    by_class: dict[str, list[float]] = {}
    for name, r in report.items():
        m = r["match_old_qvbr"]
        if m is not None:
            by_class.setdefault(r["class"], []).append(m)
        print(f"{r['class']:14} {name:18} "
              f"{'off-range' if m is None else f'{m:6.1f}'}   {DEPLOYED[r['class']]}")
    print("\n  class summary (spread within a class vs gap between classes):")
    for cls, vals in by_class.items():
        spread = max(vals) - min(vals)
        print(f"    {cls:14} mean {sum(vals)/len(vals):5.1f}  "
              f"spread {spread:4.1f}  n={len(vals)}")

    print(f"\n=== 2. cost of targeting {args.target:.0f} ===")
    print(f"{'title':18} {'qvbr(neg)':>10} {'qvbr(vmaf)':>11} "
          f"{'MB @neg':>9} {'MB @vmaf':>10} {'vs old':>9}")
    for name, r in report.items():
        tn, tv = r["target_neg_qvbr"], r["target_vmaf_qvbr"]
        bn, bv = r["target_neg_bytes"], r["target_vmaf_bytes"]
        f = lambda x, d=1: "off-range" if x is None else f"{x:.{d}f}"
        growth = ("n/a" if bn is None
                  else f"{bn/r['baseline_bytes']:.2f}x")
        print(f"{name:18} {f(tn):>10} {f(tv):>11} "
              f"{'n/a' if bn is None else f'{bn/1e6:9.2f}'} "
              f"{'n/a' if bv is None else f'{bv/1e6:10.2f}'} {growth:>9}")
    print("\n  'vs old' is size at VMAF-neg 95 relative to the pre-lookahead"
          "\n  bucket, i.e. what chasing 95 costs against today's library.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
