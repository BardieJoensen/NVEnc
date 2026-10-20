# Round 18 observer-2 replay and provenance review

## Reviewed identities

- `parent/psyex-cap-r18/policy_provenance.py`:
  `a7fa1a5f102444d2a1aa87cd21afbae8b09b13ed748036368e37c06d533b4792`
- `parent/psyex-cap-r18/replay_observer2.py`:
  `8276cad4df501913b9e05604f91ceb91020fc56d7157cde0dd7146b63ef3626d`
- Observer build pins:
  `b8f5e1353621974462b9d8840faaa53282c77312e470816932c80c6aae8cce82`
- Observer build index:
  `067f1ef1d7af99f67c7829e13bd135d3b6e840678e034f3a64ca6e17a81b2361`
- Immutable policy index:
  `10cf5a2006cdaf5660627e79def9da43a947ebe0d7ba967b5a288b20e440d067`
- Observer correction addendum:
  `3a4848fb219c874117ec43e80931356c96c5cc8c89d03b796ed79e3dd2531957`
- Preview outer receipt:
  `8d5e1efe40f5c366cac745577da760ce82cac991084dc1f2e5c0b30475f058e1`

I ran only static/Python import validation of the provenance functions. I did
not run an encode or replay.

## Findings

### The two provenance domains remain distinct and complete

`policy_provenance.policy` pins the immutable build-1 index, requires exactly
baseline/pass1/cap, calls the frozen runner's recursive `read_receipt` for
each inner receipt, reconstructs each outer command, and validates the build
prepare/build/pin chain. It also rehashes the full non-Git source domain. The
live validation succeeded against the frozen cap IVF
`e141c7ac67476320b76f96c505a809a15cde126721b9a5b45d6f8ecfab6cbd96`.

The observer build is independently pinned to the corrected 1,790-file
manifest
`305f06b51bf94988bd9d6c1002cfa880736071799f52d38f3bc7c25f5248a22b`,
observer-only patch
`a53d222914c87e20cbedd12497774a93a375448c53a3fe78c60a93e616505024`,
and source review
`566197111539997ad89180f6db36c969dc87fdf1aa9fcb4ff9e67adf058393ff`.
Its prepare/build/pin outer commands, bash launch, artifacts, source
before/after manifests, and current source tree are revalidated independently.
The policy and observer app/library identities are therefore not conflated.

### The replay holds the policy and statistics fixed

`replay_observer2.py:58-64` begins with the already validated cap-1 pass-2
argv. It asserts the old executable position, substitutes only the corrected
observer executable, and changes only the stats/IVF/reconstruction paths to a
fresh run directory. It copies cap-1's exact `pass.stats` before execution.
All policy settings, source input, request, pass number, CPU binding, and
command ordering remain those of cap-1.

The environment starts only after rejecting inherited loader and Pantheon
controls. It selects the exact observer library, retains
`SVT_PANTHEON_R18_CAP=1`, and supplies three distinct inherited FDs for the
R18, boundary, and coefficient traces (`replay_observer2.py:65-67,104-110`).
The loader check before and after requires the observer app to resolve the
exact pinned library.

### Neutrality and state controls are decisive

After success, the replay requires SHA and size equality with cap-1 for:

- the complete IVF;
- the 336-frame reconstruction YUV (therefore every plane of every frame);
- the pass statistics.

It also requires each of the three trace artifacts to be nonempty and bounded,
rehashes the observer build chain again, verifies every collected input/tool
identity before and after, and enforces the 120 GiB post-run floor after the
160 GiB pre-run gate. The identity closure includes the old run chain and
outputs, both build indices and their nested artifacts, the source input,
copied statistics, scripts, addendum, executable/library, Python, and
`nice`/`taskset`/`ldd`.

The successful replay's outer execution receipt does not yet exist and cannot
be embedded in its own inner receipt. It must be retained and bound by the
subsequent provenance/admission index, just as the preview and all prior
launches are. This is an expected post-run join, not a pre-run defect.

## Disposition

**Released for one fresh observer-2 replay under the pinned outer wrapper.**

Interpretation remains conditional on a complete inner receipt, a successful
exact outer receipt, all three structurally admitted traces, and the enforced
IVF/reconstruction/statistics equality. Quality, packet rate, and normal
two-pass runtime remain facts of immutable cap-1; observer-2 runtime is
diagnostic overhead. A byte mismatch invokes the addendum's new-build
observer-disabled cap control and blocks trace interpretation.
