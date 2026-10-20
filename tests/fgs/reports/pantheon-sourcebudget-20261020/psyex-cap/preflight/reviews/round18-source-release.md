# R18 source release for private build and controls

## Disposition

**Released for the bounded private build and control sequence only.** This is not admission of a runtime trace, encoder output, rate, quality, or causal result.

The final source differs from the reviewed worker v5 domain in exactly one file, `Source/Lib/Codec/pc_impl.h`, and that difference is the requested skip dispatch correction. All other 1,789 file identities are unchanged. The complete 1,790-row manifest exactly equals the accepted `sorted(Path.rglob("*"))` non-Git, symlink-free harness walk.

## Frozen identities

Source and method:

- contract `ROUND18_ABSOLUTE_CAP_CONTRACT.md`: `97d68ee39c6ad1922c1025143583fffc02d480b3370f4aaa1c58817029f7b4bf`
- final patch `parent/psyex-cap-r18/source-freeze-1/r18-cap.patch`: `5f03edf1ba320c84006e65484e88742ffb60b2de422b73b10346ea90ca9ed5d0`
- final complete manifest `source-freeze-1/source-manifest.json`: `f405193d6b35d74919d452457e9b8c93e52938ebbf184dda07c7622180af75ca` (1,790 files)
- freeze receipt `source-freeze-1/receipt.json`: `15f90baddfc51d783fe79a7107cb983f7731fd17cdefe27a2883d0c8c3475d52`
- outer freeze execution `source-freeze-1-execution.json`: `14e69ea9ccc4c6cc824e9c685cb0b07bd7d924cdc9ec74518f5dea5ec77a8583`
- freeze producer `freeze_source.py`: `99549bdc048a98cd4f14b3c6593cacab1b4602a4f62e8ce6b9e5c1596bb8b0e2`
- base R11 manifest: `c4a264dfa50cf24e5411c27719cf9e7ac118357ee8f0ee133e5a371854065b55`
- outer wrapper: `93c0740995afa0b6c1bf91c5c5bacbe620558e9a327493edf71406e8a68f4858`

Independent reviews:

- full native review `round18-implementation-review.md`: `780c83f4be5e2f39ef090f04976551de79312b2e6952eb9d3afa34f8255988d6`
- focused worker v5 review `round18-implementation-review-v5.md`: `9840b690d2193fad3ec35b5bdc10139df943f45557a89edb8fd63a58d9f32173`
- accepted harness revision review `round18-harness-review-revision3.md`: `d4f8b9ae3074d951bb0164acbc6d779e8f168062e821693055840db5cefca8e5`

Build/control harness:

- harness inventory `harness-revision3.json`: `bf7fce139b7e6dbd23282805f281f576f2de2e3f0c356ea011a2af0fd2c7dea9`
- `prepare_build.py`: `f0c29f5be5bd910f7bf7ea04b021005fbdeb7dbfeb4730937386f4d6510b58e8`
- `pin_build.py`: `dd5093a3cddd6e309e36e51f329dea2937c2591c8524c5659b55896655f84d9a`
- `execute_build.py`: `7f366b22bcd3d38bd87e32c7af58753925a4efd99920280fc7b47248531b6a32`
- `run.py`: `ebfce2b97bd8002db2e866086ed44ac8dece936d64bfeaa01062f29dc5bf6bb3`
- harness README: `49aa03f310684ab5ccdec1137f82d8625f257686f6be963cdec861fa873604bd`

## Focused correction verification

The preserved worker bundle `rejected-v6/r18-cap.patch` is the previously reviewed `ad24de1b...` patch. Comparing its 1,790-row manifest to the final freeze shows exactly one content change: `pc_impl.h` from SHA `07b23f...` to `be3c843...`.

In final `pc_skip()` (`pc_impl.h:121-131`):

- non-target pictures, or target216 without the R11 coefficient observer, take `pb_r18_skip()` once and return;
- target216 with the coefficient observer calls `pc_begin()` once; its common `pb_r18_begin()` already sets `skipped` from `blk_ptr->skip_mode`.

Thus no path invokes `pb_r18_begin()` twice, while all-picture R18 skip coverage and target216 source/predictor capture remain present. The previously accepted explicit accepted-generation envelope, cap-off commit guard, application/accept decode identity, and TPL grid metadata are unchanged.

The freeze receipt identifies exactly the same six changed codec files previously reviewed. Applying the normalized `-p1` patch to the pinned R11 source and checking the final manifest is an exact reproduction path.

## Release boundary

The build must use a fresh preparation directory, this exact patch/manifest, and the accepted harness under the pinned outer wrapper. Completed pins must bind this review and all outer receipts. Runtime admission still must prove complete all-picture cap application, accepted-generation, committed geometry, actual quantizer calls, lambda delivery, independent syntax/native-decoder joins, and observer neutrality before any result interpretation.
