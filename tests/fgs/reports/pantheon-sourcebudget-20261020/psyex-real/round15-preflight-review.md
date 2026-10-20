# R15 encoder runner preflight

Reviewed frozen `worker/psyex-r15-real/encode_r15.py` SHA256 `6588a0e6d0718a725ddaba7e776d445df80e4e9c3d10aa5c79a1b10adaa1f211`, `source-audit.md` SHA256 `93414f93bf5aef366e25834bb1f2f9bbee89efce698a3b9b04d3cae46433275c`, and no-encode preview receipt SHA256 `e75e7c0235a1de90a73448eb4e0bd5401ae9ed40a7736bc8a455d0a0625da68f`. No encoder was run.

## Blocking before the sole encode

1. **The completion status reinstates the obsolete 99% lower rate gate.** Lines 242–253 define `decisive_rate_gate` as 99–100% of source and mark any completed encode outside it `rate_gate_failed`. The current user constraint is only the upper practical ceiling; an otherwise valid arm below 99% must remain eligible for the unchanged quality screen, while an over-cap encode remains a completed diagnostic. Split the facts:
   - `within_source_ceiling = actual <= 9.6765224`;
   - optional `within_one_percent_of_source` for descriptive comparability;
   - a successful completion status independent of either, e.g. `encoded_under_cap` / `encoded_over_cap` (or `encoded` plus booleans).

   This matters in both directions: the planned overshoot must not look like an invalid encode, and a sub-99% passing result must not be incorrectly disqualified.

2. **The supposedly fixed request is still a free CLI parameter.** Line 91 accepts any 1–30,000 kb/s although the preregistered sole arm is 10,313 kb/s. Require `a.request_kbps == 10313` for this initial arm. A later calibration, if scientifically authorized, should be an explicit new tagged contract rather than silently admitted by this runner.

These are receipt/admission fixes only; neither changes encoder bits for the intended `10313` invocation.

## Literal command and provenance findings

I independently compared both preview pass argvs with admitted R8 `psyex-1x1`. After excluding output/stats paths, the only option differences are exactly:

- `--enable-tf 1` → `0`;
- addition of `--min-qp 1 --max-qp 1`.

TBR remains 10313, no `--qp` is added, and all other policy flags are byte-for-byte equivalent. Both passes use the changes and one fresh stats path; pass 2 verifies the stats hash against the pass-1 snapshot (lines 177–197). The preview contains the intended commands and matching canonical/snapshot script hashes.

The runner correctly pins the R8 app/library, reviewed build receipt/manifests, nested cpuinfo population, exact input and historical input validation; resolves the private library; rejects loader/observer overrides; checks identities around each pass; retains logs/timings; verifies a 336-frame 10-bit BT.709-limited stream and recon size; and separately records IVF/MKV packet populations and the established 96:336 Matroska rate. The temporal-delimiter size delta is recorded rather than incorrectly requiring identical container packet sizes.

## Small corrections / admission notes

- Line 145 says “no isolated psy-rd causality”; the changed bundle concerns TF and public QP bounds. Replace with “no isolated TF, quantizer, or rate-control causality.”
- `target_mbps = source * .995` at line 135 is an inherited comparison target, not this fixed-QP arm's achieved/requested rate. Rename it `comparison_target_mbps` or omit it to avoid implying RC can meet it.
- The README's “never a practical candidate” is too broad. Only an **over-cap** result is disqualified; any under-cap result still needs the unchanged quality/control and playback qualification.
- The absence of TF-strength log lines and exact argv are adequate preflight evidence, but not independent delivery proof. The planned neutral observer must dynamically bind the changed coded/display lifecycle and report actual encoder-final and decoder-normative q distributions. Public QP1 means frame qindex 4 before active AQ/variance modifications, never R13 internal qindex1 or a TU cap.
- Preflight failures before `run.mkdir()` leave no receipt. This is a workflow limitation, not a scientific blocker for a successful run whose full command/identity chain is retained; document it rather than claiming every failure persists.

With the two blocking receipt/parameter corrections, this runner is suitable for the one bounded diagnostic encode. CPU affinity and the 130-GiB free-space floor provide reasonable bounds for 336 fixed frames; no separate wall timeout is scientifically required.

## Final correction review — cleared

Final runner SHA256 `8616fe44a383c8aaf1722d55891cdc040b7af6886a288fcf8817903794e42ce2`; README SHA256 `19f1095186ae2bf0cb74fffab6bbe275e708c9d317c1126dc3a4c8542fc57796`.

The final delta resolves both blockers and the two stale labels without changing the planned encoder argv. It requires request 10313, records every successful encode as completed, separately records `within_source_ceiling` and `matched_rate_comparable`, and uses the same names in the packet-window receipt. It puts public bounds 1/1 in the policy record, binds the contract and current README/source audit through the before/after map, and accurately separates API default QP35, predicted effective VBR static QP30, public QP1, frame-bound qindex4, and still-unverified realized TU q. The README now says only an over-cap outcome is ineligible. **The encoder runner is cleared for the single R15 arm.**

The final preview's literal argv remains identical to the reviewed preview apart from output paths: relative to admitted R8, only TF 1→0 and the addition of public min/max QP1 change.
