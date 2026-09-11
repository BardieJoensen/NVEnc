# Existing campaign evidence recovered during repair preparation

The older campaign exists, with substantially more surviving evidence than the
three recent full-source retention trials. This inventory reads existing reports
and directory metadata. It does not run encoders, decoders, probes, quality
metrics or media hashes. No media was changed, and the seven-window comparison
manifest remains unchanged until additional references are verified.

The campaign the user recalled is documented in
`/opt/docker-apps/docs/fgs-measurement-campaign.md`, dated July 30. Its phases
cover grain energy, the libaom comparison, NVENC settings, SVT comparisons,
brightness and grain-scale coverage, and playback review. Surviving experiments
are primarily under `/media/merged-storage/media/test-encodes/`, rather than
the absent `/tmp/nvenc-fgs-tests/campaign` default in `campaign.py`.

## What survives

Counts below are historical records or files, not current damaged titles,
independent successful trials, or current-build qualification.

| Dataset | Existing evidence | Useful next use |
| --- | --- | --- |
| Main `media/test-encodes` archive | 143 top-level experiment directories; 8,445 files, including 4,496 JSON files, 636 grain tables and 118 MKV/Y4M files | Recover previous controls, failures, source/model diagnostics and rejected approaches |
| `fgs-quality-size`, `silo-retest`, `silo-aq` | Silo S03E01/E02 ordinary FGS, auto, QVBR, UHQ and AQ results; raw per-frame metrics remain | Earlier quality/size curves and banding controls |
| `svt-three-arm`, `phaseA3`, `svt-compare-20260804` | July campaign narrative, grain tables, residual metric files and August 4 Taxi SVT metrics | Design the base-encoder versus grain-analyzer comparison; keep build and model distinctions |
| `knob-sweep` | 25 MKVs, including two reference files and multiple setting/quantizer outputs | Revisit a promising setting only when the current build or evidence warrants it |
| `tdarr-temp/av1-optimization-bench` | 105 encode records across 12 cases; 69 rows carry VMAF in `results/raw.json`; 18 reference MKVs; additional full-metric reports | Historical HQ/UHQ, lookahead, quantizer, speed, size and SVT controls |
| `tdarr-temp/project-hail-mary-quality-20260728` | 15 numbered source/encode pairs, aggregate samples, quantizer/bitrate-cap candidates, alignment checks and HDR-labelled CVVDP arrays | Candidate UHD source windows and earlier quality/bitrate investigations |
| `tdarr-temp/vqm-results` | 13 reports for 11 distinct titles, with raw metric files; three reports concern the same HotD episode | Whole-title historical distributions and difficult-scene selection after provenance review |
| `grain-sweep/results.csv`, `library-cambi/results.csv` | 1,660 grain-screening rows and 2,390 CAMBI-screening rows | Broaden content selection; do not reuse flags as current damage diagnoses |
| `/tmp/downloads/clean-digital-20260807`, `animation-gate-20260806`, `animation-bucket-20260807`, `base-floor-20260808` | Small aggregate reports plus some per-frame metrics/logs | Earlier clean-digital, animation and base/synthesized-grain controls |

The `tdarr-temp` paths above are under `/tmp/downloads/tdarr-temp`. The main
archive also includes multiple source-fit, chroma, temporal, grain-amplitude,
motion, holdout and blind-review experiments. Review instructions survive in
some directories whose playback media no longer does; instructions alone do
not establish completed visual review.

## Silo results checked against surviving raw metrics

Six operating points each still have exactly 600 VMAF and 600 SSIMULACRA2
samples. Recomputed SSIMULACRA2 means and recorded VMAF aggregates agree with
the rounded values in [the July 29 findings](FINDINGS-2026-07-29-PERFORMANCE.md).
That report identifies the r4033-era path and 60-second clips scored over the
first 600 frames. Sizes below come from its historical rounded MiB table;
the original comparison media is absent from `fgs-quality-size`.

| Clip / mode | Historical MiB | VMAF mean | SSIMULACRA2 mean |
| --- | ---: | ---: | ---: |
| S03E01 ordinary QVBR 29 | 13.39 | 93.419 | 80.706 |
| S03E01 ordinary QVBR 27 | 17.02 | 93.789 | 81.617 |
| S03E01 auto QVBR 29 | 13.93 | 94.186 | 81.515 |
| S03E02 ordinary QVBR 29 | 13.45 | 93.867 | 78.075 |
| S03E02 ordinary QVBR 27 | 17.09 | 94.173 | 78.989 |
| S03E02 auto QVBR 29 | 14.19 | 94.796 | 79.252 |

Old auto gained about 0.77/0.93 VMAF at 4.0/5.5% more reported bytes. The same
historical report records 7–11% lower grain energy, so that gain is not evidence
of simultaneously preserving every aspect of the source. Its `retain` cap and
model behavior differ from the current optional mode. The ordinary QVBR 27
arms cost about 27% more than QVBR 29 and provide another useful comparison.
These are prior operating points to explain and learn from, not a current
auto-mode allowance or an estimate of visible improvement.

## Whole-title evidence and identity limits

The reports cover four Anja and Viktor films, the three Fantastic Beasts films,
House of the Dragon S03E01, Scarface, Casino and The Shining. The September 2
`vqm-keeporig-campaign.log` records successful completion for the final three.
Earlier queue failures also survive; a failure log is not interchangeable with
the completed campaign. Sampling cadence differs between metric tracks, so a
report's single `frames scored` field must not be treated as complete coverage
by every metric.

The three original paths named in that log are absent at those exact locations.
That observation does not establish whether another original exists elsewhere.
Today's Scarface and Shining library sizes also differ substantially from the
old encoded sizes. Those historical scores cannot be assigned to the current
files by title/path alone. Casino's similar rounded size does not prove identity.

Historical metric labels and definitions need review before combining scores,
including CIEDE2000 transformations, HD/4K VMAF selection and HDR display setup.
The old campaign itself records timing/source mistakes and superseded
hypotheses. In particular, reject the uncorrected Planet Earth clip; the
corrected `clip_planet_earth_deserts_24p.mkv` remains a candidate for verification.

## How this changes the next trial

Use the existing records before proposing another broad settings sweep. The
surviving bright Phineas and Ferb, Grave of the Fireflies, corrected Planet
Earth, coarse 1080p Coming to America, Ju-on references and Hail Mary samples
are candidates to broaden the current content coverage. The older benchmark's
reference filenames often originate in the library, so original provenance
must be established before they can qualify source fidelity.

The private inventory records 42 reference candidate files, including aggregate
samples and older benchmark references; this is not 42 independent source
scenes. Their paths, size, mtime and inode were recorded without reading media
payloads. None has been admitted to the current comparison manifest. The next
post-repair work is to verify a small useful subset, select original-source
windows, and compare current ordinary FGS, auto and ordinary FGS at a similar
video-byte budget, with bounded SVT controls. Existing negative examples remain
regressions even when their old average scores looked acceptable.

The index is
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/existing-campaign-inventory-20260911.json`.
It contains directory counts, media identities, selected-report hashes, the six
Silo metric summaries, whole-title report text and explicit provenance limits.
It catalogs existing data; it does not preserve missing media or authorize any
new download, production change or heavy work during the repair.
