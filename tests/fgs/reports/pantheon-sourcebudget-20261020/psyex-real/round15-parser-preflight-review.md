# R15 structural-parser parameterization review

Reviewed:

- `parent/psyex-real-r15/parsers.py` SHA256 `45f11c246037e1a58a2762235a62db9a0bcb71e85fe992cfcc35897fa24983e3`
- generator `prepare_parsers.py` SHA256 `8a1f29866cfdecbebfbbac1b9b0df2c5cf6102e65c840634e4d77d4529b00b9`
- successful control `parser-control.json` SHA256 `afb324e1c891990816383bdfc0ecc281268692c96003adc9729e55163cf947e4`

The generator pins the admitted R11 coefficient validator and admitted R10 decoder validator, extracts their functions through the Python AST, and requires every replacement site to occur exactly once (or exactly three times for target-event leaf checks). The only semantic substitutions are:

- coefficient route `decode_order == 210` → caller-supplied expected coded ordinal;
- decoder start target `(event314,coded210)` → caller-supplied event/coded identities;
- three target-event guards and the target postloop transition → supplied event identity;
- terminal totals `(502 events,336 coded)` → supplied full-stream counts.

The corrected generated module adds only the `hashlib` import required by the unchanged decoder parser. The preserved first control failed before producing an admitted control; its failure receipt accurately identifies that missing import. The corrected control then parsed the old admitted 19.6-MB coefficient trace and 39.3-MB decoder payload through both old and new paths and recursively established exact types, keys, shapes, dtypes, array contents, metadata, bytes, 2,907 coefficient tokens, 9,843 decoder units, and 502 event records. Inputs were unchanged.

All branch-sequence, source/predictor/residual, q/DQ/IQM storage normalization, EOB/scan, native-inverse, owner coverage, skip-category, payload-offset, postloop, and terminal population guards remain literal copies. I found no loosened trace structure or hidden old target identity beyond source picture 216, which is intentionally fixed to the original fixture display target.

**Cleared conditionally for R15 admission.** The admission caller, rather than either trace, must supply `expected_decode_order`, `expected_event`, `expected_coded`, total events, and coded count from the independently pinned R15 syntax binder. It should explicitly check their domains and cross-bind the binder result/IVF/target OBU before calling these functions. It must also reject optimized Python, pin this parser/control/generator, and retain the complete old-control receipt. No R15 value has yet been observed or inferred.
