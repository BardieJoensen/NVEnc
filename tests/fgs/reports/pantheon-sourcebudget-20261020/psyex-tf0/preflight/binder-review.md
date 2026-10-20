# R16 binder and final runner/replay review

Reviewed final encoder SHA256 `2c14604755be12ae1f8fe996cc93ea9486963f629e44bc3a1a7d21d40076469b`, replay SHA256 `03118968ab27f79146bb2d2d95cdcec709e0d7512c220b2d9a2053d084b3fae0`, contract SHA256 `5ed81849c12af6daeb206e2184fa7ad0ddacb4b6d7d3ec35fab3b845c9901c71`, and binder SHA256 `cc50a6c5ddda9e5d38742ff52886edc7b8722589d6f6980546641e3c9e66c23e`.

## Final runner and replay disposition

The prior calibration/provenance blockers are resolved. `validate_chain` now:

- requires the selected and predecessor receipts to have been issued by the live reviewed encoder hash and rehashes every equal before/after identity entry;
- pins policy, source commit, input, R8 receipt, app/library, exact 9.6765224 Mbps validity source, and both pass TBR values;
- recomputes scored Matroska rate from the exact 336-packet population at positions 96:336 over ten seconds and verifies receipt flags;
- recursively enforces attempt 1 at request 10313 or exact incrementing attempts through 3, target ratio .997, predecessor outside the 99–100% interval, proportional rounded request, exact stored predecessor identity, and cycle rejection; and
- returns every predecessor, packet window, comparator receipt, runner, and recorded identity path for the next run/replay live identity set.

The main runner carries those dependencies across both passes. Replay imports this exact encoder module, validates the chain again, and includes the complete lineage plus every selected-run identity in its before/after population. Under parent hard-pinning of the selected inner and outer receipts, both are accepted. The no-media smoke covers a positive initial receipt, policy rejection, cycle rejection, and packet-rate recomputation; it is useful coverage but the source inspection above is the admission basis.

The worker README remains descriptively stale at review time: it names replay `1ac1b129…` and preview `preview-10313-full`, rather than final replay `03118968…` and `preview-final-lineage3`; `preparation-sha256.txt` also lists initial drafts. Correct or label those before treating them as final manifests. This does not change the hash-pinned runner command or encoded output.

## Binder disposition

The R15 framing, header parser, implicit-key refresh normalization, slot lifecycle, one-display-per-packet invariant, and complete-type-6-OBU extraction are unchanged. New admission code hard-pins the final R16 runner while requiring caller-supplied exact selected command/outer receipt hashes, invokes the runner's recursive validator, independently rehashes rate and identity evidence, and binds the outer wrapper's command and inputs. The event/coded index/order hint/refresh/OBU remain outcome-derived.

Syntax compilation passes. No R16 media exists in this review, so the binder is accepted for execution but has no outcome result yet. Parent-derived wrappers that pinned provisional binder `7df374bd…` must be regenerated to pin final `cc50a6c…`.
