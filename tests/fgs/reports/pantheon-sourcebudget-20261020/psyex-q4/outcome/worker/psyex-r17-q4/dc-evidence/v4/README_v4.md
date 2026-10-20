# Corrected R17 DC evidence extraction v4

Fresh read-only extraction preserving v1–v3. No native loading, build, encode, decode, GPU, Git, or production work.

All 502 syntax events, packet event indices, and OBU bounds pass. Overlap rejection is `next_start < previous_end`; valid gaps remain allowed. Target event 314 / coded ordinal 210 is packet 209's second header and has OBU SHA `e68353e010c09239253e1b9de07d481d452547d5c4a9e973b3df3d2dc9353ed3`.

The target broad interval is derived in zero-based coordinates, with explicit round-trip assertions: marker line 22319 (1-based) through the line before the next marker at zero index 22413 (physical 22414). Thus the included interval is physical lines 22319–22413, and the end-exclusive physical line is 22414. No interior `Frame Header` marker is allowed. This interval is intentionally labeled broad because it can include Tile Group/OBU fields.

The exact DC line is physical 1-based line **22349**, splitlines index **22348**, asserted by direct indexing to equal `delta_q_y_dc.delta_coded 0 = 0`. This traced syntax supports frame-level luma DC delta zero.

R12 receipt validation records that receipt `inputs_before/after` are identity dictionaries pointing to 275-entry list payloads; all payload and command/library/object/source identities are checked.
