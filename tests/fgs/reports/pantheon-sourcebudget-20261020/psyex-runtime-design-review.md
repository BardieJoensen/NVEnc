# R8 fixed bundle and runtime-delivery review

## Bundle disposition

The fixed public configuration `preset=4, tune=0, psy-rd=1.0, sharp-tx=1, noise-norm-strength=1, hbd-mds=1, complex-hvs=0` is a defensible single bundled-policy test. Preset 4 keeps the intended deep search; `hbd-mds=1` explicitly forces the 10-bit mode-decision path; tune/psy/sharp/noise settings select the fork's intended texture-sensitive policy; and `complex-hvs=0` avoids adding a second optional high-complexity HVS policy. `hbd-mds=1` is likely redundant with P4 plus psy-rd 1.0's automatic HBD selection, but making it explicit removes a runtime ambiguity rather than adding a distinct hypothesis.

The command and effective log must still bind random access, two-pass VBR, 10-bit 4:2:0, and the remaining fork settings. This is an end-to-end PSYEX configuration test. It cannot isolate psy-rd, sharp-tx, noise normalization, HBD search, or the fork from each other.

## Smallest sound observation

Process-lifetime relaxed atomic counters are sufficient for **policy delivery**, without per-pixel tracing, if they are described as search/decision invocations rather than final bitstream block populations.

Use one private trace build and a dedicated pass-2 process with one encoder channel. Enable counters only through an explicit inherited trace FD; with the FD absent, every hook must return without side effects. Static zeroed `uint64_t` arrays indexed by `picture_number` 0..335 and `MdStage` 0..3 can use GCC `__atomic_fetch_add(..., __ATOMIC_RELAXED)` because this tree builds as C99 and has no suitable lock-free project counter API. Track out-of-range POC, invalid stage, overflow, duplicate dump, and unexpected encoder-instance/pass conditions separately and reject any nonzero value.

Minimum hook families:

1. **Coefficient optimizer/sharp branch.** In `full_loop.c:1764-1817`, count RDOQ-eligible calls reaching `svt_av1_optimize_b`. Inside `:1153-1182`, separately count early skip-cost returns, fast-mode/EOB-zero returns, luma+delta-Q+sharpness eligibility, and the `sharp_tx=1` branch that sets `rweight=0`. A completion count after the optimizer distinguishes branch entry from work that survives early exits. The existing noise-normalization call at `:1819-1829` should have a call count because it is an explicit member of this bundle. No coefficient payload or per-TU hash is needed for delivery.

2. **Psy distortion.** Count calls and nonzero returned terms at the existing call sites, without recomputing the metric. At minimum cover fast luma candidate distortion, transform-type prediction/reconstruction (`product_coding_loop.c:4863,4889`), and full spatial prediction/reconstruction (`:5822,5846`). Report each family separately, plus `ctx->mds_spatial_sse` true/false and `ctx->hbd_md` true/false. Do not call this exhaustive coverage of every psy use; there are additional inter-prediction, chroma, quadrant, and temporal-filter call sites.

3. **Residual/skip comparisons.** In `rd_cost.c:1543-1578`, count coefficient-skip comparisons and choices; separately count the subset with `psy_rd>0 && ctx->mds_spatial_sse`. At `:1596-1630`, do the same for skip-mode comparisons and choices. These prove the psy-bearing distortion route and actual skip comparisons coexist in the tested search. They do not prove every compared candidate carried a nonzero psy term unless the nonzero value is propagated with that candidate, which is unnecessary for this bundled-delivery question.

4. **Mode selection.** Immediately after `lowest_cost_index` is resolved in `mode_decision.c:4311-4353`, count selection calls, candidate totals, selected inter/intra, selected skip-mode, coefficient/no-coefficient, spatial-SSE, and HBD mode by POC/stage. These are selections within mode-decision search. Some may later be discarded by partition selection, so they must not be reported as encoded block/mode counts. No partition-specific causal claim should follow from them.

Emit the header/configuration and all counters exactly once in `svt_enc_handle_dctor`, immediately after `svt_enc_handle_stop_threads` (`enc_handle.c:979-983`) and before the sequence/config pools are freed. The stop routine joins every worker thread (`enc_handle.c:927-975`; `svt_threads.c:231-239`), making this the first safe complete snapshot. Require a dedicated pass-2 invocation; otherwise one app process with multiple passes/handles could produce cumulative or multiple dumps.

## Admission and limits

- The trace header must record the seven effective settings, pass, dimensions, bit depth, channel count, and expected 336 inputs. Require POC/stage coverage appropriate to each hook and report zeros rather than omitting cells.
- Compare three streams: unmodified private build, trace build with observation off, and trace build with observation on. Both trace streams must exactly match the unmodified IVF and use the same pass-1 stats, input, command, and resolved library. Any on/off stream difference rejects the instrumentation as observationally invasive.
- Counters establish that guarded code paths ran and quantify search activity. They do not establish that a specific term changed a winning decision, isolate one component, describe final entropy-coded blocks, or explain a quality result. The real encode's unchanged full-window scoring provides the outcome; no pixel trace is needed unless a later causal question specifically requires final-block attribution.
