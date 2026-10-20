# R17 target DC-syntax evidence review

Reviewed read-only on 2026-10-20:

- extractor SHA-256 `137ed87e224575fd27a1987c765c88dadbd053d748f1f790b08c54d03d1c64ee`
- result SHA-256 `b32c9491bb0a9ce822026c7a7d2bd92f198e39815f9bded3620dfd05c2dd0b31`
- execution receipt SHA-256 `91f84ec60b5eb971b8431affcfdec5d4a6f9532c9fbb6a71807c6a7000673bd8`
- bound trace log SHA-256 `af82740d0c84a2a55c72aa9f1ba794e630431b3b2729618d5cf9ffd8fc2f5ee8`

## Independent finding

The substantive target and DC conclusion are correct. The preserved event graph has 502 frame-header events: 336 coded events with contiguous coded ordinals and 166 show-existing events. Event 314 is coded ordinal 210, packet 209's second of five headers, hidden/showable, order hint 88 and refresh flags 16. Its OBU is SHA-256 `e68353e010c09239253e1b9de07d481d452547d5c4a9e973b3df3d2dc9353ed3`. Show-existing event 325 resolves display packet 216 back to coded ordinal 210.

The independently inspected target header contains `base_q_idx = 91`, followed by `delta_q_y_dc.delta_coded 0 = 0`; it separately has `delta_q_present = 1` and `delta_q_res = 2`. FFmpeg's pinned CBS syntax implementation sets the frame-header delta value to zero when `delta_coded` is false (`cbs_av1.c:570-579`). The independent libaom decoder implements the same rule (`decodeframe.c:1766-1775`). Thus luma DC delta is zero for this coded frame. This says nothing about the active block-level delta-Q that produces the observed per-token qindices.

## Required extractor corrections before using its result as a pinned runner input

1. `extract_dc_evidence.py:96` uses `a > b` for `next_start` versus `previous_end`. That rejects gaps but does not reject overlap. The overlap condition must be `next_start < previous_end`; if contiguity is intended, assert equality separately. I independently checked the current 502-event data: it has zero overlaps and zero gaps, so this is a validator bug rather than an evidence failure.
2. Lines 132-135 add one twice when recording the delta line. In the extractor's own `splitlines()` coordinate system, the target header starts at 22319 and `delta_q_y_dc` is line **22349**, while the result and README report 22350. Remove `i+1` (or enumerate from `start-1`). Physical newline tools can differ by another line because the log contains a separator recognized by Python `splitlines()`; state the coordinate convention. The recorded text itself is exact.
3. The reported 22319-22412 slice is a between-frame-header-marker slice and includes Tile Group plus part of the following OBU header. Rename it accordingly; it is not solely the target frame-header syntax block. This does not affect the uniquely found delta field.

After these small corrections and a fresh result/receipt, the evidence is suitable as the parent runner's independent `y_dc_delta=0` input. No build, encode, decode, native diagnostic, or GPU work was run for this review.
