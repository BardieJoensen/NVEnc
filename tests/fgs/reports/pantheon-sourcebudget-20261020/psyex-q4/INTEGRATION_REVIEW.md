# R17 integrated report review

Disposition: **released without correction**. The report and frozen outcome package accurately represent the admitted R17 diagnostic and its limits.

Reviewed identities:

- `PSYEX_Q4.md` SHA256 `fc319bb2313f224d0ce253314f10faa2b778a0e5d2e8d9894cd458496837d4c9`
- `HYPOTHESES.md` SHA256 `aa7823050bd6ded93973b53bc33e1919d8afa064e552ca961bfebddcd002dcea`
- `LEDGER.md` SHA256 `f3912dbb55442dcfe8f80d444cfcb381c2689502a802d721b82359dec151ad2f`
- `README.md` SHA256 `6a82a596e28c78603f8607c6d4d6cc1e3f6fea7f0585b59ae74bf207250f7fd6`
- `psyex-q4/outcome/manifest.json` SHA256 `a3ef75e01b9516b644cf7b08423e31c91f20d4f1549d7c96ce5ea8f231ec5ea3`

I independently walked every manifest entry. All 60 source/frozen pairs exist and match their recorded path, size and SHA256; each pair is byte-identical. Their total frozen size is the stated 2,442,230 bytes. Both external artifacts—`native-arrays.npz` and `mosaics.npz`—remain present at the recorded scratch paths and match their recorded hashes and sizes. All local Markdown links in the four reviewed reports resolve.

The principal values match the accepted result and independent derivation: shirt q4 HF/source 86.080%, ACF error 0.05612, correlation 0.83228 and MSE 0.21869; background 99.605%, 0.00492, 0.98810 and 0.19733; face 93.543%, 0.02525, 0.92133 and 4.25032. Counts also agree: 2,870 tokens, 2,169 invoked, 701 uninvoked, 2,130 baseline positive-EOB, 39 invoked baseline-zero-EOB, 20,974→203,490 nonzero coefficients and 2,154 EOB changes.

The spatial attribution is accurate. The 4,624 shirt pixels on native 64×64 transforms are 23.12% of the ROI and account for 86.026% of q4 source-SSE and 96.561% of raw source-SSE. Background's 1,040 uninvoked pixels account for 66.905% of q4 source-SSE; face's 81,472 account for 99.193%. The report correctly labels these as additive SSE partitions and does not convert them into additive HF or a proven rejected search decision.

Scientific scope is appropriately narrow. The text states that raw HF is not a strict bound on quantized HF, treats another fixed-q point as low value rather than impossible, and preserves the distinction between this local reconstruction and a legal encode, packet-rate result, full-window campaign, practical candidate or playback observation. The parent still inspection is explicitly grayscale diagnostic inspection. R18 is presented as a new real-policy cost/delivery question, not as a favorable expected result.

Provenance is complete for the accepted outcome. The reviewer `ADDENDUM.md` is linked and frozen at SHA256 `57d650006879017c523897ea3b9bd60ab2a2c010be822c97dd6f1cb52edc49ec`. The exact failed derivation source is frozen at SHA256 `48de104a91a2a707277bbd1333269690f02cf2db5cb93c1a812946e348f204c7`, matching its failed outer receipt. The report and manifest explicitly disclose that rejected worker-v3 source SHA `1a0903beb82688631fbf2459b7b4b3dedf2cf139b0e8a6eff847efa11613bda3` is unavailable and that retained audits are not a source substitute.

The reproduction command correctly uses the pinned outer execution wrapper, accepted runner SHA and fresh receipt/output paths. It does not overwrite admitted evidence. No native or metric rerun was needed for this review.
