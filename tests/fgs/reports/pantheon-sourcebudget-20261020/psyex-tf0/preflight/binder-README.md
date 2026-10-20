# R16 independent dynamic header binder

`bind_r16_headers.py` SHA256 `cc50a6c5ddda9e5d38742ff52886edc7b8722589d6f6980546641e3c9e66c23e` is the admitted R15 lifecycle parser adapted to R16. No syntax/event lifecycle logic changed.

Before invoking FFmpeg it requires explicit hashes for the selected inner command receipt, final encoder source, and successful outer execution receipt. The encoder SHA is also hard-pinned to reviewed R16 runner `2c14604755be12ae1f8fe996cc93ea9486963f629e44bc3a1a7d21d40076469b`. It imports that exact module's `validate_chain`, verifies the exact TF-off/no-public-Q-bound policy, live receipt and identity population, packet-window 96:336 rate, source cap, 99–100% source interval, and the independently implied ±1% R8 rate interval. The outer receipt must be complete, bind the reviewed wrapper SHA `93c0740995afa0b6c1bf91c5c5bacbe620558e9a327493edf71406e8a68f4858`, selected encoder/Python identities, tag/request, and exact calibration predecessor arguments.

The output uses key `outer_execution` for the exact outer receipt identity and records identities for the entire recursive calibration chain. It derives display216's coded event, reference-slot lifecycle, order hint, refresh map, coded ordinal, and exact complete frame OBU dynamically. It carries no R15 event index, coded ordinal, order hint, slot, or population assumptions.

Intended bounded invocation after a completed selected arm:

```text
/usr/bin/nice -n 10 /usr/bin/taskset -c 8-11 python3 bind_r16_headers.py \
  <selected-command.json> <fresh-output-dir> \
  --receipt-sha <selected-command-sha> \
  --encoder-script <live-encode_r16.py> --encoder-sha 2c14604755be12ae1f8fe996cc93ea9486963f629e44bc3a1a7d21d40076469b \
  --outer-receipt <outer-execution.json> --outer-receipt-sha <outer-sha>
```

This binds bitstream syntax to decoded display position. Decoder/sample admission must separately prove display216 equals fixture frame216 and join the derived event/OBU to neutral observation output.
