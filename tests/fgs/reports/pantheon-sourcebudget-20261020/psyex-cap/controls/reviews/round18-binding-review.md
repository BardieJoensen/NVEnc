# R18 dynamic header-binding review

Reviewed read-only before execution:

- `parent/psyex-cap-r18/bind_headers.py` SHA-256 `20d998ab1f432001ecd839ab5abe1c5bf2cc3701da688f93a4d8764504a5df34`
- pinned pure-parser source `reviewer/round16-refine-binding/bind_refine_headers.py` SHA-256 `5d30f960504b12d840d9cd916140dac5b24ae2053852c88a5a66b87ae1b347dc`
- R18 provenance helper SHA-256 `b6c923ec919c27e55c3be1a432bce225f582064212ad68ac1590388c00e95d8f`
- R18 trace reader SHA-256 `08fe4c552b576e30b91f000246f3a6f39235383f0cb6aa1c19991af3323561d8`

## Disposition

The dynamic mapping and R18 ancestry adaptation are sound, with **one execution blocker**: the optimized-Python guard is written as an `assert` and therefore disappears under `python -O`. Replace it with an explicit exception before argument parsing. No parser, encode or bitstream change is needed.

## Findings

1. **Blocking: fail-open optimized execution.** Lines 144-146 use:

   ```python
   if __name__ == "__main__":
       assert __debug__
       main()
   ```

   Under `python -O`, the assertion is removed and all other assertions in this binding layer are also disabled. Use `if not __debug__: raise RuntimeError(...)` before `main()`, matching the accepted validators. This must be fixed before release.

2. **R18 provenance is correctly bound.** Lines 51-63 pin and load the accepted provenance helper and runner, recursively validate the cap receipt, require the literal completed-build pins path/SHA, bind the supplied outer receipt SHA, and invoke `provenance.outer()` with the exact cap/control/pass1 arguments. That helper establishes the reviewed outer producer, full argv, live stable inputs/log and released build/source domain. The IVF identity is then matched to the admitted cap output.

3. **The accepted parser is reused without stale policy constants.** The new script pins the complete prior helper but calls only `ivf_packets`, `obus`, `parse_headers` and `lifecycle`. It does not invoke its old main, calibration, ordinal, rate or target constants. The R18 layer independently pins ffmpeg, the R18 helper/provenance/runner, cap/outer receipts, IVF and completed pins before and after execution.

4. **Dynamic lifecycle and target binding are valid.** The accepted lifecycle already requires exactly one display action per each of 336 canonical IVF packets and 336 ordered displays. The new checks require 336 non-show-existing coded events and set equality between displayed coded ordinals and the coded population; with equal cardinalities this is a bijection. Display 216 is therefore derived from packet/display lifecycle, with no inherited ordinal.

   For show-existing, the code resolves the live slot, requires the target hidden frame to have refreshed it, and rejects any intervening refresh of that slot. For directly shown coded frames it requires identical coded/display event identity. The selected target must be a complete type-6 frame OBU; split header/tile-group framing fails closed. Extracted bytes are checked against the parser-derived OBU hash and size.

5. **Evidence and scope are appropriate.** Continuous input identities, ffmpeg, command/log, complete events/displays, extracted target OBU and the derived target/display link are retained. The limits correctly reserve encoder-trace identity, source ownership, decoder samples, native q/DQ/EOB and quality for downstream admissions. A private observer may be reused only if its hard target guards equal this computed result; this script does not force an old ordinal.

## Nonblocking receipt hardening

- Add started/finished UTC and elapsed time to the result. If ffmpeg or parsing fails, attach identities for `command.json` and `trace_headers.log` when they exist; the files are already preserved, but the failure receipt currently stores only the argv/preflight inputs and exception.
- Run the fixed script under the pinned outer wrapper and bind that outer receipt in the eventual aggregate. This records CPU/nice controls and preserves failures that happen before the output directory/initial result can be created.
- The summary's `all_packets_exactly_one_display_action=True` is justified by the accepted lifecycle assertion. It could be derived as a count for readability, but it is not an untested claim.

After the explicit `-O` guard is fixed, this binding is released for one fresh R18 cap-stream execution. The computed event/ordinal/order-hint/refresh values remain outcomes and must not be hard-coded in advance.
