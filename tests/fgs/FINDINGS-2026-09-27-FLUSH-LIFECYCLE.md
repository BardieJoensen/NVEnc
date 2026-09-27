# Encoder failure cleanup and EOS lifetime

September 27, 2026 — D70 Linux qualification complete in `c7a4b827`.
Production is unchanged; R3–R8 remain open.

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

The complete encoder build has SHA
`2328b1ed3d88b7e17cd072df4df3d08221d42a2c994b3e66c15cd7a09e367d27`.
The 28-run manual comparison reproduces the old crash twice (exit 139), then
passes ten clean expected rejections (exit 1), fourteen modeled encodes and
two ordinary SDR/HDR encodes with no diagnostic hook. Every new run flushes
at most once; failures publish no completed model/capture report. The original
constant-colour and independent covariance quality vetoes remain intact.

Independent AOM/dav1d checks agree across 928 decoded observations. Ordinary
packet payloads, clocks and metadata match exactly. Modeled runs match earlier
models, readiness and packet bytes, including full 1080p/UHD. Complete pixel
comparisons cover 399,826,944 original, candidate and reconstructed samples per
role, 118,595,584 copied candidate samples, and 380,952,576 synthesis-oracle
samples. All 200 modeled frames, 24 source frames and 102 windows pass.

The unchanged CPU baseline passes 259 Python tests in 36 suites and 52 C++
programs; D70's pipeline-header change is compiled and exercised in the real
encoder. This host qualifies Linux synchronous output. Asynchronous Windows
runtime testing remains separate. Tdarr's pause is released with current limits
preserved; no experiment restarts automatically. This closes D68's cleanup
follow-up, not automatic retention or a production deployment decision.

Local evidence is in `roadmap-r3-flush-lifecycle-20260927/` under the evidence
root linked by [the current handoff](WORK-TO-PRODUCTION.md). The originating
record is `roadmap-r3-constant-chroma-20260927/failure-cleanup-issue.json`.
D68 encoder qualification is closed by `report.json` and `phase2-comparison.json` here.
