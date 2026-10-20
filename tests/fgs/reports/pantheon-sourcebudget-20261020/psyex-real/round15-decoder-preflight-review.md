# R15 decoder validator preflight

Reviewed `parent/psyex-real-r15/validate_decoders.py` SHA256 `d7c0d08e0cfa2d52fbc02f5bec2073b1b462a5f5922c54265a76a10306089175` without execution.

The adaptation correctly pins the previously admitted shared helper (`bb2e0256…`), accepts a caller-fixed completed encode-receipt SHA, binds live IVF/MKV/app reconstruction to it, rechecks all parent before/after identities, validates the one-stream 10-bit BT.709-limited 336-packet Matroska cadence, and places each software/GPU decoder selector before its input. Dav1d, libaom, and NVDEC are compared over all 336 frames/all planes against the app reconstruction; tools, launch wrappers, logs, outputs, input artifacts, and scripts are rehashed at completion. No quality/playback claim is made.

This validator proves decoder/sample agreement only. The caller and later aggregate admission must pin the final R15 receipt, runner, command/intervention, and GPU serialization; those are properly outside this helper. I found no blocking decoder-path or identity defect.
