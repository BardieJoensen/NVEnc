# Motion-separator perceptual review set, 2026-08-02

## Status

**Playback judgement pending. Nothing in this set is a deployment candidate on
its own.** The purpose is to decide whether motion separation's measured 46.4%
corpus saving is compatible with acceptable base fidelity.

The clips are under:

```text
/media/merged-storage/media/test-encodes/sourcefit-review-20260802/blind/
```

Each title has four lossless 1920x1080 centre crops:

- `A-base` and `B-base`: AV1 decoded by libdav1d with `filmgrain=0`;
- `A-finished` and `B-finished`: the same streams with synthesis enabled.

The A/B mapping is constant between the base and finished pair for a title.
All review files are 10-bit FFV1, cropped without scaling, and retain the
BT.2020/PQ/limited-range tags. Review the base pair first: it isolates the
separator from random grain synthesis and makes misplaced detail easier to see.

## What to look for

Do not score general sharpness. Look specifically for:

- a trailing edge after a moving face, hand, coat or rifle;
- texture remaining at the old position after an object uncovers a background;
- doubled or displaced hair, facial detail and high-contrast contours;
- a clean base that looks stable while paused but smears during motion.

Record the title, A or B, approximate time and whether the difference remains
visible in the corresponding `finished` pair. A preference without a timecode
is still useful; the finished pair determines whether synthesis masks a base
defect during normal playback.

The Shining has a subject walking across a detailed office and hallway. The
Deer Hunter has face, hand and rifle motion against trees. Scarface has several
independently moving faces, hands and bodies against a static kitchen. These
were chosen for disocclusion, not for flattering grain.

## Reproducibility

Candidate binary:

```text
commit  1f20fb1c4502290015b665cd0856cb30b6a87226
sha256  d119abd866e0689d90c477ca43784fa8fe979c9624cf83751cc739eb0076f06d
```

Both arms used AV1 10-bit, qvbr 29, max bitrate 20000, tune hq and
`modelsrc=on`; only `denoiser=bilateral|motion` changed. All six complete AV1
streams pass a full `libdav1d -xerror` decode. Tdarr and library files were not
used or modified.

## Mapping -- reveal only after reviewing

| title | A | B |
| --- | --- | --- |
| The Shining | motion | bilateral |
| The Deer Hunter | bilateral | motion |
| Scarface | motion | bilateral |

