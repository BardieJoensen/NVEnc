# R16 selected-rate review

The real midpoint refinement at request **10042 kbps** has a valid calibration and rate selection. Its command receipt is `00bb9243453fb55f1c878842e2ecfd3760f8403144e1e5b507530477a03ef497` and outer receipt is `e82ff2212660e0453797c5e2383ce910a27099f80252e9c79dc3d5f93517d7d2`. The corrected public validator reconstructed all 35 live dependencies, including the canonical 10014/10070 bracket. The outer command uses the exact endpoint arguments, returned zero, and its before/after identities agree.

The scored MKV packet window contains **12,087,309 bytes** over positions 96:336, independently yielding **9.6698472 Mbps**. This is **99.931017%** of the 9.6765224 Mbps source rate, 0.0066752 Mbps below the ceiling, and inside the unchanged [9.579757176, 9.6765224] Mbps matched interval. It is also within 1% of R8 (+0.435634%).

Pass one took 65.073485s and pass two 307.180646s; their sum exactly matches the recorded **372.254131s**. Fresh pass statistics and the pass-one snapshot are byte-identical.

This establishes rate eligibility only. Decoder/native admission, stage and support evidence, full-window quality and playback remain pending. No quality conclusion follows from selecting this rate.
