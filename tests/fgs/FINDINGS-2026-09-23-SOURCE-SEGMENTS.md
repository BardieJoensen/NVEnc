# Explicit whole-source and modeled intervals

D62 is complete as `b8e56dc4`, with strict source-only identity validation in
`221862ff`. This finite diagnostic can preserve complete source pictures next
to modeled pictures without carrying fitting history or grain across that
boundary. It does not select fractions or qualify source populations.

The opt-in `pre_encode_source_segments: true` accepts only all-partial rows or
complete `[1,1,1]` source rows. Every modeled interval needs at least eight
pictures; the whole trial still has at most sixteen. Each interval has its own
fitter and explicitly mapped local/global ordinals. Original source, input/packet
identity and PTS remain bound. Source rows require their matching immutable
preservation decision and explicitly emit `apply: false`. An all-source run
never opens a fitting context. Layout, source/reconstruction ranges and strict
integer timestamps remain validated even on this path. Existing manifests
retain their original behaviour.

A failed partially retained candidate remains a failed experiment. Its compressed
base cannot be relabelled as source preservation. Unsupported component mixtures,
short model intervals, missing source data and stale decisions reject; the
controller must preserve the original file or make a fresh source encode.

The full CPU suite passes 214 Python tests in 30 suites and 47 C++ programs.
All 65,536 binary schedules were checked; 46 meet the eight-picture interval
contract. Stateful controls verify separate fitter ordinals/readiness, zero-grain
source decisions and terminal errors. The later strict-validation change passes
its targeted controls, six byte-identical CPU report/packet replays, five typed
negatives and six positive/two negative GPU reruns.

Overall qualification includes 24 positive and six negative GPU encodes,
1,344 fresh independent decoded observations, 376,074,240 exact source and
reconstruction samples per role and 25,165,824 independent synthesis samples.
Both depths pass model-to-source, source-to-model and all-source cases. All
96 interval decisions match their CPU models/readiness/packet references:
32 modeled pictures and 64 grain-free preserved-source pictures. The all-source
outputs match the corresponding capture packets exactly. Two earlier model
controls and ordinary SDR/HDR output remain unchanged.

The 32 independent frame guards, four spatial windows and 192 separate-half
means pass. Original strict full-spatial per-picture results remain 31/32; the
one 10-bit model-to-source failure is retained. These are constructed transition
controls, not real-media quality or complete R4 qualification. Fourteen negative
CPU replays leave no accepted output; late failures include already released
packets but correctly mark the trial failed/incomplete. The late GPU clock
mismatch likewise fails without accepting a partial result.

Latest diagnostic `build-221862ff/nvencc`, SHA256
`bee13e878a780fabb0784197fad210e3ad101c655c37461a7d8c20f0bdf2b852`.
Native library v7 / ABI2 and model writer v5 are unchanged. Evidence, commands,
source derivation, rejected controls and cleanup/pause receipts are in
`roadmap-r3-source-segments-20260923/` under the evidence root in
[the handoff](WORK-TO-PRODUCTION.md). All owned pauses are released with current
worker limits preserved. Production remains ordinary `cb903a17`; retention/FEL
remain off. Reserved footage is unopened and nothing restarts automatically.

Next bind the bounded selector's decisions to actual pre-encode plans, preserving
unsupported mixtures and intervals too short to qualify. Independent measured
source/fraction evidence and R3–R8 remain open. These explicit schedules are not
an automatic admission policy or production-speed qualification.
