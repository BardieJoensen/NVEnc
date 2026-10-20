# R16 neutral-replay draft preflight

Reviewed `worker/psyex-r16-tf0-budget/replay_r16.py` SHA256 `00032d23d6db7d07761cd3ad58367174ea94a71fb34eac3099e3126290e29822`.

## Disposition

The neutral replay retains the accepted R11 mechanics: it uses the completed private observer pins, copies the selected arm's exact pass1 statistics, changes only app/stats/output paths in pass2, privately resolves the observer library, passes fresh append-only trace FDs only in `on`, requires exact unmodified IVF and app reconstruction in both modes, checks 336 unique sorted IVF timestamps, and rehashes its inputs before/after. The fixed source index 216 in the envelope is appropriate; coded/display event identity must still be derived dynamically later.

It is not ready for calibrated R16 arms because line 76 hardcodes `request_kbps == 10313`. The decisive arm may be request 2 or 3. Replace this with a caller-provided expected selected receipt/request or a hard-pinned calibration-selection receipt, while continuing to require that the replay command is copied from that exact completed arm. Never accept an arbitrary receipt merely because its settings say TF-off.

The placeholders for final encoder-script, contract, and R11-pins hashes must be replaced with reviewed constants. Admission should additionally depend on the final encoder receipt having the exact R8-relative policy/provenance and valid rate status established by the measured runner. The line-79 error text should say R16 rather than R15, although that wording is non-scientific.

With those fixes and the final encoder schema, no further replay-method change is needed. It remains an observational neutrality replay, not a timing comparison or proof that target event/population identities match R15.

## Revision `f06151…`

Reviewed `replay_r16.py` SHA256 `f06151c6b666aa774d4bcda7c2784a04ee4784928e466a54895f555d6cc464eb`.

The hardcoded 10,313 request was removed, so the wrapper can replay a calibrated arm. It correctly requires a positive integer request and copies the exact selected receipt's pass2/stats. However it is not releasable yet:

- `EXPECTED_ENCODER_SCRIPT_SHA` still names the rejected preview SHA `e82359…`, not executable SHA `1e0709…` (or the forthcoming corrected final runner), and `EXPECTED_PINS_SHA` remains a placeholder.
- Merely accepting any SHA supplied on the command line does not establish that this is the selected valid calibration arm. After the runner correction, require the final receipt's asserted R8-relative policy and calibration lineage, internal request=`--tbr` equality, completed stats linkage, and `matched_rate_comparable == true` for the decisive replay. Pin the selected receipt SHA in the parent execution/admission layer.
- Include the selected R8 command identity in replay before/after dependencies via the original receipt, and correct the non-scientific `R15 original identity drift` message to R16.

The neutral FD, loader, statistics, IVF/reconstruction equality, and trace-envelope mechanics remain sound. These binding fixes do not require a method rewrite.

## Corrected revision `e9ec3b…`: exact-diff review

Reviewed `replay_r16.py` SHA256 `e9ec3b877c9299748b925e37c1c96598ce4a390faaefc16f810007053bf49f65`.

The final observer pins are populated, the encoder hash points to the current `f8c326…` runner, arbitrary calibrated TBR is accepted, both command TBRs must equal the selected receipt, the selected rate is independently compared to the source 99–100% interval, and the selected receipt's input/IVF/reconstruction/stats are rehashed. Neutral off/on replay mechanics remain sound.

It is not releasable with the current encoder revision or as a standalone selector:

- It inherits the encoder's incomplete recursive calibration proof. Add the same full chain validator (including formula, attempt progression, out-of-window predecessor, issued runner, and exact stored/live receipt identities), then bind every chain receipt in replay before/after identities.
- Line 83 only compares the two recorded identity dictionaries. Rehash every recorded path and require its live digest to equal the recorded digest; otherwise equal stale maps pass. In particular, verify the live R8 receipt identity rather than only its recorded SHA string.
- Bind the live `packet_window` receipt and require `actual_mbps`, source rate, `within_source_ceiling`, and `matched_rate_comparable` to agree with it. The present eligibility check trusts scalar values copied into the selected command receipt. The parent layer must additionally hard-pin the ultimately selected receipt SHA and the outer execution receipt.

The error wording is now correctly R16. **Disposition:** blocked on the shared calibration/live-identity corrections; no replay should run from `e9ec3b…` until the corresponding final encoder SHA and checks are repinned.

## Final revision `03118968…`: accepted

Reviewed `replay_r16.py` SHA256 `03118968ab27f79146bb2d2d95cdcec709e0d7512c220b2d9a2053d084b3fae0`. It hard-pins encoder `2c146047…`, imports that exact module's corrected recursive validator, and adds the returned lineage, encoder source, and every selected-run identity path to its own live before/after population. The packet-rate and calibration checks are therefore no longer trusted as unverified scalars. Under the parent layer's exact selected inner and outer receipt pins, the replay is accepted for execution after a qualifying arm exists.
