# Minimal playback gate — 2026-08-05

Clips and this brief live at:

```text
/media/merged-storage/media/test-encodes/minimal-review-20260805/
```

Four side-by-side clips, 8 seconds each, left half is one encoder arm and right
half is the other. **Watch The Deer Hunter first — it is the one where the two
arms differ most.** If you only watch one, watch that.

## The question

> In the left half or the right half, does the picture look like it has more
> **real detail** — or does one side look like it has more **mush / smeared
> residue** where detail should be?

Answer per clip: `left`, `right`, or `no difference`. A timecode is a bonus,
not required. `no difference` is a real and useful answer.

That is the whole ask. Then open `REVEAL.md`.

## What NOT to look for

**Do not look for ghosting, trailing or smearing behind moving objects.** That
was the original concern and it is measurably gone: directional lag asymmetry
now reads 0.00003--0.0039 on both arms, inside the bilateral separator's own
0.00010--0.00036 band and 30--3500x below the 0.118--0.141 that blocked the
earlier motion arm. Looking for trails would spend your attention on a solved
problem.

Also ignore grain pattern differences. Film grain is synthesized at independent
positions by design, so a paused-frame mismatch is expected and means nothing.
These clips are the **grain-disabled** bases precisely so grain cannot distract
from the question.

## Why this needs eyes at all

Two respected metrics disagree, and the disagreement is about exactly the thing
this project has proven metrics cannot judge:

- the candidate wins base VMAF on 6/6 titles;
- production wins base SSIMULACRA2 and Butteraugli on 6/6 titles.

They are arguing over whether the extra grain-like structure the candidate
leaves in the base is *useful detail* or *residue*. No further measurement can
settle that — full-reference metrics score grain presence and coarseness, not
correctness. Your answer decides whether the 46.4% compression arm is viable.

## The clips, ranked by how much the two arms actually differ

Selection is measured, not guessed: mean absolute difference between the two
grain-disabled bases, 8-second window, highest first.

| clip | difference | start frame | size |
| --- | ---: | ---: | ---: |
| `The_Deer_Hunter-worst.mp4` | **4.15 codes** | 0 | 17.2 MB |
| `Scarface-worst.mp4` | 3.69 | 0 | 10.3 MB |
| `Taxi_Driver-worst.mp4` | 3.60 | 88 | 12.7 MB |
| `The_Shining-worst.mp4` | 1.95 | 0 | 4.8 MB |

45 MB total, against the 5.1 GB package these were cut from. Nothing was
re-encoded from source — the halves come straight from the sealed blind
package, so the A/B mapping is untouched and neither side is labelled.
