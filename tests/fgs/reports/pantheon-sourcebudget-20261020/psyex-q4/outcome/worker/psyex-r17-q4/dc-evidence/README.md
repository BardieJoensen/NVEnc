# R17 read-only frame-header DC evidence

This directory contains a read-only extraction from the already preserved R16 syntax binding. It did not load a native library and did not build, encode, decode, use GPU, or modify any input evidence.

`extract_dc_evidence.py` checks the complete 502-event binding, all per-packet event indices and OBU ranges, coded/show-existing populations, and the target event. It binds event 314 (coded ordinal 210) to packet 209's second frame header and OBU `e68353e010c09239253e1b9de07d481d452547d5c4a9e973b3df3d2dc9353ed3`. The target header occupies trace log lines 22319–22412 (inclusive); its `delta_q_y_dc.delta_coded` field is line 22350, exactly `0 = 0`. In the trace_headers syntax output, that flag means no frame-header luma DC delta is signaled, so the frame-level delta is zero. This is a traced syntax interpretation, not a claim about per-block quantizer deltas.

The packet contains five frame headers (events 313–317); event 314 is the second. Display event 325 (packet 216) is show-existing and resolves to coded ordinal 210, proving the scored/displayed frame link without treating show-existing as a new coded frame.

The R12 build receipt correction is recorded in `result.json`: receipt fields `inputs_before` and `inputs_after` are identity dictionaries pointing to JSON payloads; those payloads are lists of 275 identities. The script validates both receipt identities, both payload lists, equality, every payload identity, every command return code/log identity, and library/object/source-manifest identities. It does not treat the receipt dictionaries as lists.

Inputs and exact execution are bound in `execution.json`; the output is `result.json`. All hashes are SHA-256. Playback or quality conclusions are outside this evidence task.
