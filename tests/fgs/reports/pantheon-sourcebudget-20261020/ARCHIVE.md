# Source-budget evidence storage and restoration

The standard archive workflow started on2026-10-20 after the two child agents
hit their usage limit. Final completion and verification are recorded below when
available. Earlier evidence archives are unchanged.

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
