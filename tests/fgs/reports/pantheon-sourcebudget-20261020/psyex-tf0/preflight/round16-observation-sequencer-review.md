# R16 observation-sequencer review

Reviewed `parent/psyex-tf0-r16/observe_selected.py` SHA256 `eb6f8a812e66c226a1e9cd5b4189bc61fc1b306191e1a78d4bdd37d525b259ed`.

No blocking argv/path or partial-failure defect found. The selected run path, receipt SHA, completed inner status, source-cap/matched flags, encoder hash, and completed outer execution are checked before creating a fresh observation directory. Every child is run serially through exact outer wrapper `93c074…`, with the reviewed script SHA supplied to that wrapper. A child failure leaves its outer `*-execution.json` and log, returns nonzero, and stops downstream steps. Script-hash or freshness failure happens before child launch.

Argument order and paths match the reviewed CLIs:

- decoder validator receives tag and selected receipt SHA;
- binder receives selected receipt/output plus explicit receipt, encoder, and outer receipt hashes;
- encoder neutral replays receive mode/tag and selected original receipt;
- native decoder replays receive selected receipt, dynamic binding, fresh output, and `--trace` only for on;
- admission receives selected run, dynamic binding, both encoder/decoder replay roots, decoder wrapper hash, and fresh output;
- stage diagnostic receives exact admission SHA and fresh output.

The script reads the binder's actual `result.json`, then refuses reuse of the fixed R10 observer unless the independently derived event/coded/order/refresh and total populations match its compiled guards. All subsequent admission remains dynamic and hash-bound.

One efficiency advisory: all-336 decoder validation currently precedes the syntax binder. A bad outer/run lineage or changed target mapping would be rejected by the binder after GPU work has already run. Moving `bind-syntax` before `validate-decoders` would fail earlier without changing evidence. This is not a scientific validity blocker because admission requires both and the sequence stops on either failure.

The sequencer itself has no aggregate persistent receipt, but every scientifically relevant child does. A mid-sequence failure therefore leaves the completed prefix and failing child receipt; no final admission is produced. Accepted as orchestration only.
