# Source-budget evidence storage and restoration

The standard archive workflow completed on2026-10-20 at21:26:22UTC after the
two child agents hit their usage limit. It verified54,430files, removed the77GiB
task tree from SSD, left the compatibility symlink and added one index row.
Earlier evidence archives are unchanged.

- Source: `/tmp/downloads/codex-work/pantheon-sourcebudget-20261020`
- Destination: `/media/merged-storage/cold-storage/docker-apps/pantheon-sourcebudget-20261020`
- Physical root: `/media/merged-storage/logs/cold-storage/`
- Helper: `/opt/docker-apps/scripts/archive-to-cold-storage.sh --link`
- Execution log: [archive-execution.log](archive-execution.log)

The tree contains pinned source/build/runtime dependencies, unique native traces,
coefficient arrays, media, metrics, reviews and earlier-round evidence. Those
files remain useful for exact resumption. Six verified duplicate R18 payloads
were replaced with hardlinks to byte-identical canonical files, retaining every
path and hash while reclaiming8,402,815,291bytes. The helper preserves hardlinks.
See [deduplication receipt](psyex-cap/archival/archive-deduplication.json).

Before relocation, the parent checked current processes, registered jobs, Git
worktrees, Docker mounts, user cron and user/system timers. No experiment was
running or queued. Some services mount the ancestor `/tmp/downloads`; none
mounted this task tree specifically. No scheduled task referenced this root.
The archive helper also checks open handles and container mounts and refuses
in-use trees. Unrelated media, torrent and service jobs were left running.

A compatibility symlink permits reading, but historical validators bind
`Path.resolve()` identities. **Do not execute those validators through the
symlink and claim unchanged provenance.** On resume, restore a writable exact
copy from the immutable archive to the original scratch prefix, after checking
jobs, space and mounts. Copy with hardlinks preserved to a fresh sibling,
verify file counts and checksum dry-run, then replace only the compatibility
symlink with the restored directory. Never rewrite archived receipts or alter
the archive in place. A different prefix needs explicit new provenance.

[Current state and dependency instructions](psyex-cap/archival/CURRENT_STATE.md)
and [resource blocker](R18_RESOURCE_BLOCKER.md) give the next checks. The archive
is a checkpoint at a resource limit, not a completed repair or playback finding.

Additional read-only verification passed:3,759unique file contents hashed against
the frozen evidence, including all1,790files in each R18 source tree, decisive
traces, media and private build artifacts. The check took43.974403s and does not
claim unchanged resolved-path execution provenance. See
[verification receipt](archive-verification.json) and
[verification script](archive_verify.py).

Post-archive free space: staging SSD approximately670GiB; home75GiB; cold-storage
pool20TiB. The archive helper and temporary copy container exited successfully.
No experimental job remains active. Useful pinned dependencies stay in cold
storage; duplicate payloads occupy a single hardlinked copy.
