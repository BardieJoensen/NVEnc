# Round8 preflight: a distinct texture-sensitive coding policy

Primary question: is there an existing, pinned policy that reaches the measured
coefficient/transform/skip decision paths and warrants one source-budget trial?
R7 delivers finer quantization but fails preservation at4×source. More global
qmax trials, final-only coefficient retention and undirected settings sweeps do
not answer the next question.

The candidate for source inspection is BlueSwordM/SVT-AV1-PSYEX, exact master
commit59d1a025698f2ca7b4c4b0e833937dd15e382494, independently observed by parent
`git ls-remote` on2026-10-20. This is not the v3.0.2-B tag, which resolves to
3beb4aee471c686ecb05089b29b0e676026aea1b. Keep fork/commit provenance explicit.
[Project documentation](https://github.com/BlueSwordM/svt-av1-psyex) describes
AC-energy-sensitive psy-RD and a default sharp-transform policy, giving a
mechanistic reason to inspect it after the measured optimizer/skip losses.
Documentation is not proof that the desired paths execute or improve quality.

This phase authorizes source retrieval/provenance and read-only source review.
It does not yet release a build or encode. Parent will select exactly one policy
and freeze its settings/controls after the source findings, without another user
approval round. Scratch builds/experiments are already user-authorized.

Worker owns fresh `worker/psyex-r8/`: README, pinned source checkout, retrieval
receipt, complete tracked-source manifest and source-policy map. No edits to R6,
R7, original fixtures, preserved archives or production. No NVEnc Git index.
Parent owns repo report/integration/index and eventual harness/scoring. Reviewer
owns `reviewer/round8-*.md`. Two children maximum, no recursion; preserve others'
work. Review the fetched repository's applicable instructions before building.

Required source deliverables:

- Verify remote HEAD and exact requested commit, record UTC/source URL/tool
  versions, clean checkout status, complete tracked-file hashes and symlinks;
  no partial manifest omitting build-support files. Record submodules/LFS and
  stop for missing source rather than silently replacing it. Bound retrieval
  to250MB; no system packages, installs or external side effects.
- Follow concrete calls from defaults/CLI validation to psychovisual coefficient
  selection, TU residual-vs-zero and full mode/skip decisions. Show guards,
  relevant bit-depth/preset/rate-control limitations and effective value sources.
  A name or README promise does not establish all three paths.
- Identify whether `sharp-tx` changes initial quantizer route or just later
  optimization. Compare with previously tested standard SVT ac-bias2, tune0,
  variance boost and preset0. Record bundled defaults including QM, filtering,
  variance AQ, noise normalization and hbd mode decisions.
- Confirm native input support for the established 10-bit exact lift and the
  available two-pass VBR/statistics path. The original is8bit; native10bit and
  installed-public-only are preferences for reuse, not invented user gates.
- Deliver a bounded build plan with out-of-tree paths, <=4 compile jobs,
  nice10/CPU0–7, no install, source/config/binary manifests and test/help commands.
  Do not build until parent releases this reviewed plan.

Reviewer independently checks the three decision paths and confounds before
receiving parent's preferred outcome. Existing R3 native decision-margin capture
remains the alternative if the fork does not actually supply a relevant policy.
No new snapshot is justified solely because it is possible.

A later real arm, if admitted, must use untouched original fixtures, actual
packet rates99–100% of source (E05 ceiling9.6765224Mbps), complete new-path
frame/color/decoder checks, required campaign GPU metrics and all unchanged
texture/quiet/detail/banding/temporal controls. No source-specific setting fit or
manual ROI allocation; E04 transfer follows any E05 success. Full-episode and
actual playback qualification remain necessary for a production proposal.

Resource preflight at12:37UTC: staging616GB free, home76GB, availableRAM19GiB,
GPU0%/183MiB. Another unrelated external-drive qualification job is active and
must remain untouched; later runtime results need contemporaneous load records.
No heavy experiment runs in this source-inspection phase.
