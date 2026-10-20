# Parent inspection before native review disposition

Inspected frozen patch `120773258760fc0f1506c8dce4ff6bce77c5501aef2dd855a671c770932c5fab`.
No compiler, build or encode has run.

- `pc_skip` calls the companion skip/begin before its target216 guard, then
  target216 calls `pc_begin` which begins the companion again. A selected skipped
  target TU therefore encounters the new live-context rejection.
- `pb_r18_accept` correctly receives the captured pre-decision generation in its
  JSON, but `r18_emit` still places the post-reset `loop_count` in its binary
  header. Metadata and header can disagree after recoding.
- `pc_commit` computes and checks the new offset before checking whether R18
  observation is active. Move that new work into the active companion function,
  keeping cap-off/observation-off routing free of new validation assumptions.
- The parent lambda helper now refreshes only an already active lambda path.
  The earlier outer TPL condition did not prove `sb_setup_lambda` had run:
  `r0_based_qps_qpm && tpl_is_valid` controls that inner path.

These are source-level preparation defects, not encode outcomes or technical
blockers. Fix and re-review before execution; preserve each rejected draft.
