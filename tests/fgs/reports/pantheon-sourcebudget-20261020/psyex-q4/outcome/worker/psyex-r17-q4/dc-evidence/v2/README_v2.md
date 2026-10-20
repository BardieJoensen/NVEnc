# Corrected R17 DC evidence extraction v2

This is a fresh read-only extraction preserving the original v1 artifacts in the parent directory. It performs no native loading, build, encode, decode, GPU, Git, or production work.

The extraction checks all 502 syntax events, contiguous packet event positions, and OBU bounds. Overlap rejection is `next_packet_offset < previous_packet_end`; gaps are valid and are not rejected. The target remains event 314 / coded ordinal 210, packet 209 second header, with OBU SHA `e68353e010c09239253e1b9de07d481d452547d5c4a9e973b3df3d2dc9353ed3`.

The trace interval is explicitly labeled a broad interval from the target `Frame Header` marker through immediately before the next marker; it can include Tile Group and next OBU fields. The target line is physically line 22350 (1-based), or splitlines index 22349 (0-based), with exact text `delta_q_y_dc.delta_coded 0 = 0`. The traced syntax therefore supports frame-level luma DC delta zero.

The R12 receipt correction remains: receipt `inputs_before/after` are identity dictionaries whose referenced JSON payloads are lists of 275 identities. Both payloads and all recorded command/log/library/object/source identities are checked.
