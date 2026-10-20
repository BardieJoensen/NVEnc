# R16 TF-off budget runner

`encode_r16.py` (SHA `2c14604755be12ae1f8fe996cc93ea9486963f629e44bc3a1a7d21d40076469b`) is an executable R16 runner derived from the verified R15 execution path, with R8 command receipt SHA `ceea9943cb7b0fd31331a7505089ac72bb06dc78c7e150589f0972d469cfa138`, build/input hardpins and fresh R16 output roots. It changes exactly one R8 policy option: `--enable-tf 1` to `--enable-tf 0`. It removes R15 public QP bounds and static-QP handling; no min/max-QP or static-QP flags are emitted. The runner compares normalized pass1/pass2 argv against the preserved R8 command receipt, allowing only TF, TBR, and fresh output/statistics paths to differ.

The runner binds contract SHA `5ed81849c12af6daeb206e2184fa7ad0ddacb4b6d7d3ec35fab3b845c9901c71`, fixture SHA `232abb5ffee869be4bedf682aa103c166eb473bb3fdad5daf28956cca60148d4`, R8 build manifests, app/library hashes, loaded library resolution, pass statistics, remux metadata, packet cadence and source-cap flags. It records status `encoded` independently from `within_source_ceiling` and `matched_rate_comparable`. Requests are integer kbps for the contract's initial 10313 request and later parent-authorized calibration.

`replay_r16.py` (SHA `03118968ab27f79146bb2d2d95cdcec709e0d7512c220b2d9a2053d084b3fae0`) is the R11 neutral observation wrapper adapted to consume a completed R16 receipt. It uses fresh R16 pass2 statistics and requires the R16 encoder receipt's real command/contract lineage; R11 pins remain only for the observer build. It is not executed during preparation.

Preview command used: `python3 encode_r16.py preview-10313-full 10313 --preview`. No encoder execution, scoring, or playback was performed.

Calibration lineage is recursively checked by the module-level `validate_chain` function and imported by the replay wrapper from this hash-pinned encoder source. Every predecessor must be encoded successfully under the same policy, contract, R8 receipt, input, binary/library/source provenance, and pass TBR; each attempt increments by one and uses the exact 0.997 formula only when its scored rate is outside 99–100% of source. All predecessor and packet-window identities are included in live identity bindings.

Final lineage checks rehash every recorded identity_before/identity_after path, validate the recorded validity identity and exact 9.6765224 Mbps source value, recompute the scored MKV packet rate from packet sizes at [96:336], and recursively bind all calibration predecessors. The no-media lineage smoke receipt is `lineage-smoke.json` SHA `f2bbb0f33e47af15ce12242b435cf0239b3791fa3fb37131b8ae211d2e997b96`; it covers one valid attempt, a policy mismatch rejection, and a cycle rejection.

`preparation-sha256.txt` is an initial-only inventory from before final lineage corrections; the hashes above are the final inventory.
