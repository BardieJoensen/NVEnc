# Encoder failure cleanup and EOS lifetime

September 27, 2026 — D70 implementation; full encoder build and controlled
failure/output comparison are pending. Production is unchanged.

D68's deliberate 10-bit source-to-model rejection reached the expected
independent covariance check, then exited 139 while destroying the encoder
task. Its output was never accepted or installed. The log shows the initial
drain failing with an EOS entry still queued, followed by another drain from
the task destructor.

`PipelineTaskNVEncode::flushEncoder` queued a pointer to a local EOS wrapper.
An earlier output failure could return before consuming that entry, leaving a
pointer to an expired local object. The output recycler could also put that
temporary EOS wrapper into the ordinary free-input queue. A later flush would
encounter the invalid entry. This lifetime pattern also exists in the deployed
source, but the observed trigger uses an experimental model hook; no production
file damage or library-wide scope has been established.

The EOS wrapper now belongs to the encoder task, survives until its output
thread stops, and never enters the free-input queue. A flush records its result
and subsequent calls return that result without submitting EOS or invoking
failed output callbacks again. The asynchronous branch also propagates a failed
or unavailable output-thread result. The quality check, source preservation,
grain model and rejection threshold are unchanged. The legacy header's CRLF
format is preserved.

Qualification must reproduce a clean nonzero exit for the original rejection
and other early/late failures, with no successful capture/model report. Fresh
ordinary SDR/HDR and successful modeled outputs must preserve their packet
payloads, clocks, metadata and independent decoded pixels. This host qualifies
the Linux path; asynchronous Windows runtime testing remains separate.

Local evidence is in `roadmap-r3-flush-lifecycle-20260927/` under the evidence
root linked by [the current handoff](WORK-TO-PRODUCTION.md). The originating
record is `roadmap-r3-constant-chroma-20260927/failure-cleanup-issue.json`.
D68 encoder qualification remains open until this failure path is resolved.
