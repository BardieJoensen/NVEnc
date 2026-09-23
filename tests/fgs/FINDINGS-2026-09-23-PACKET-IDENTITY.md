# Streaming models and reconstructed-picture identity

R3 now has a qualified experimental [streaming complete-model writer](model_filter/README.md)
and a bounded packet-identity helper. Neither has an encoder output call site or
automatic quality/source approval. Production remains ordinary `cb903a17`.

D43 preserves the seven previously qualified manual outputs byte for byte,
including reordered reference reuse and HDR. Concurrent contexts, shared native
input buffers, output lifetime and terminal failures are covered. The private
parser stays isolated from the encoder's FFmpeg. See its README and local ledger
for the ABI, limits and exact qualification scope.

## Why output buffering is required

An AV1 packet can contain a coded future picture as well as the picture displayed
now. A reconstruction-derived model for that future picture may become available
after its coded header first arrives. Assigning models by packet number or coded
picture number would therefore use the wrong picture's evidence.

D44 adds a packet observer carrying coded IDs, shown-reference IDs and order
hints. The host identity helper has eight reference slots and a bounded FIFO
plan. It requires an independently verified association between the displayed
packet and its received **encoded-input ordinal**, after filtering. That ordinal
is distinct from the original-file frame ID. The caller must also qualify a
forward-reference bound smaller than half the order-hint modulus; wrapping hints
alone cannot identify arbitrarily distant pictures.

The helper rejects missing/repeated/ambiguous identities, noncontiguous receive
order, nonincreasing clocks, missing display anchors, hidden pictures without
references, unsupported hint widths and packet/byte-budget overflow. A packet
cannot be released before all required reconstructions are available. Incomplete
drain fails. This is an availability check, not a picture-quality gate.

Seven existing streams supply 603 checked header bindings, including 445 matches
to unique active seeds independently reported by dav1d. Displayed clocks and
grain state agree; all transformed output bytes remain exact. One HDR IVF copy
starts 125 ms earlier than its original Matroska timeline. Every timestamp agrees
after that single verified translation; the failed unshifted comparison is kept.

The replay needs at most six pending packets, five future pictures and 251,745
compressed bytes. These are measured reconstruction-only buffering requirements
on the declared controls. They exclude source/model storage, GPU surfaces and
any further quality-window delay. Immediate release would precede required
reconstruction in 123 packets; treating coded IDs as input ordinals mislabels
328 bindings. Raw order hints also fail after wrap. These deliberate incorrect
alternatives confirm that the checks exercise the relevant cases.

## Remaining actual-pipeline evidence

The replay simulates contiguous reconstruction availability using independently
decoded display ordinals and timestamps. It does not prove NVENC's live callback
order or integrate a FIFO into the encoder. The explicit reconstruction probe
now records `receive_ordinal` alongside its encoded-input/source IDs and PTS, so
the next diagnostic build can check that assumption directly. This extra field
is not yet GPU-qualified.

D42's changing-picture trial is prepared, but has encoded no pictures. A node
restart interrupted its drain; the replacement Tdarr node was already unpaused,
so the owned pause no longer exists. Resume that finite trial manually after
verifying runtime ownership and the diagnostic build. No trial restarts on its own.

The full CPU suite passed 214 Python tests in 30 suites and 37 C++ programs.
Subsequent encoded-input naming and hidden-reference checks pass their targeted
unit/reference builds and all seven replays. The private stream observer also
rejects mid-packet sequence transitions before output, rather than using a later
sequence's state to interpret an earlier picture.

Local evidence: `roadmap-r3-model-stream-20260923/` and
`roadmap-r3-model-identity-20260923/` under the current evidence root. Read
`report.json`, `shared-buffer.json`, `report-ordinal.json`, `mapping-negatives.json`,
`sequence-negative.json` and `cpu-suite.json`. Continue the
[retention roadmap](RETENTION-ROADMAP.md); these prerequisites do not finish R3–R8.
