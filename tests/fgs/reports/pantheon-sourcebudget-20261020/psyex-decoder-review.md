# Round 8 PSYEX decoder admission review

Reviewed `validate_psyex_decoders.py` SHA
`f683b288f33ae223b684a549457d65b49a2db722d23183b225d5cdfb8e1f7505`
against pinned shared helper SHA
`bb2e0256100ad70e02753c0fc19c0cc62f2ed189f08d50335b3ab421983b5ca9`.

## Blocking correction before decoder execution

`validate_psyex_decoders.py:64` invokes `nice` and `taskset` through inherited
`PATH`, while `shared.tools()` records neither executable. This regresses the
absolute, before/after-bound resource wrapper used by the accepted encode
runner. Use `/usr/bin/nice` and `/usr/bin/taskset`, record their identities in
the PSYEX receipt before the commands, and recheck them at final admission. The
pinned shared helper need not change.

## Otherwise sound

- The immutable completed encode receipt binds IVF, MKV, and app reconstruction,
  including the encoder's live identity chain (`:28–36`).
- Probe admission requires the expected AV1 10-bit limited-BT.709 stream, exact
  336 integer-rounded Matroska PTS, and 24 fps (`:51–63`).
- Decoder selectors precede the input, raw output is explicit, and the three
  paths are dav1d with synthesis disabled, native libaom, and NVDEC with an
  explicit P010 download/conversion (`:64–73`).
- `raw_hashes` and the shared strict framemd5 parser compare a whole-frame digest
  containing every visible Y/U/V sample for all 336 frames. This supports the
  stated sample-identity claim, not quality or playback (`:74–99`).
- Tool/library/GPU state, logs, outputs, scripts, probe, and inputs are checked
  before final admission, with a persistent failed receipt after output creation.

**Status: conditionally accepted after the one absolute-tool/identity fix.**

## Focused re-review

Reviewed corrected SHA
`a32f685a4040cb10f7028ef8280920c2eb6d85225c26f78e24217f9e5c686d2f`.
Lines 49 and 93–94 now retain and compare `/usr/bin/nice` and
`/usr/bin/taskset` identities before and after all decoder commands, and line 65
uses those exact absolute paths. This resolves the sole blocking finding.

**Final status: accepted for decoder execution.**
