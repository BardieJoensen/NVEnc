# The scoring harness caches on filename, not on content — 2026-08-07

> Root cause of the "campaign.score returns garbage" report. It does not. It
> returns *stale* results, which is worse, because they look plausible.

## What happened

Re-running three titles under the deployed flow produced impossible scores:
SSIMULACRA2 `-411`, VMAF-neg `0.15`, Butteraugli max p95 `275`, on encodes that
`ffmpeg psnr` puts at **34.9 dB**. The scores were also byte-identical across
two runs with different encodes (`-411.46` vs `-411.47`).

Timestamps give it away:

```
ssimu2-Sugar_S02E08-new.json   11:49:27   score
Sugar_S02E08-new.mkv           11:51:21   encode, two minutes LATER
```

The score predates the encode it supposedly describes.

## The mechanism

`campaign.py:294`, in `ffvship()`:

```python
out_json = os.path.join(d, out_name)
if not os.path.isfile(out_json):
    run([... FFVship ... "--json", f"/data/{out_name}"])
return json.load(open(out_json))
```

and the same shape at `:347` for the vmaf track's `feat_json`.

**The cache key is the output filename, which is derived from the tag alone.**
Nothing ties it to the identity of the reference or the encode. Re-encode under
the same tag and the old scores come back silently, with no staleness check and
no warning.

The first run of `flow_rerun.py` seeded those files with genuinely broken
numbers: the encoder and the reference were seeked independently
(`--seek` vs `-ss`), which do not land on the same frame, so entirely different
content was compared. Fixing the alignment and deleting the `.mkv` files was
not enough -- the `.json` files survived, and every subsequent run replayed the
misaligned scores.

## Why this is dangerous rather than merely annoying

The failure is silent and the output is well-formed. A stale score is
indistinguishable from a fresh one at the call site, so:

- **iterating on an encoder change in a fixed working directory returns the
  first result forever.** Every subsequent measurement of "did this help?"
  answers with the pre-change number.
- it is invisible in aggregate. Only the impossible magnitudes here made it
  noticeable; a *plausible* stale score would have been believed.
- it interacts badly with the repo's convention of stable, descriptive tags,
  which is exactly what makes tags collide across runs.

The encode functions in this repo cache the same way (`if out.is_file(): return`),
and that is fine -- an encode is deterministic given its inputs, and the file
*is* the artifact. A score is a claim *about* two other files, so caching it on
its own name alone drops the dependency that matters.

## What is not wrong

FFVship and the vmaf binary are fine, and so is the rest of `campaign.score`.
Re-scored directly through the vmaf binary, the same encodes give sensible
numbers (Sugar `92.00`/`92.05` VMAF, Elemental `91.53`/`92.25`). Nothing that
was measured in a **fresh** directory is affected -- which covers
`bucket_calibration.py` and the film results, each of which ran once into a
clean path.

## Fix

Key the cache on the inputs, not the label. Cheapest correct form is to include
the reference and encode `(size, mtime_ns)` in the cached document and re-run
when they differ:

```python
stamp = [(os.path.getsize(p), os.path.getmtime(p)) for p in (ref, enc)]
if os.path.isfile(out_json):
    doc = json.load(open(out_json))
    if doc.get("_inputs") == stamp:
        return doc
```

writing `_inputs` alongside the metric payload. A content hash is stricter but
reads the whole file; size+mtime is enough to catch re-encoding, which is the
case that actually occurs.

Until that lands, the rule for any re-run is: **delete the score JSONs, not just
the media**, or score into a fresh directory.

## Related, from the same file

`campaign.py:330` already documents a trap I then walked into twice today while
killing a background job -- "cleaned up by captured PID, never by pattern
matching, which twice managed to SIGTERM its own shell because the writer
command text appears inside the shell's own command line". `pkill -f
flow_rerun.py` killed the shell running it, twice, for exactly that reason.
