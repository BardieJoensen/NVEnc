# Evidence archive and cleanup

Archive: `/media/merged-storage/cold-storage/docker-apps/pantheon-quantization-20261019/`.
The standard archive utility copied and verified 516 files, removed the original
scratch directory and added the cold-storage INDEX row. A separate SHA-256 pass
verified all 515 manifest entries after the move; see [receipt](archive-receipt.json).
Earlier evidence archives were not modified.

The archive contains selected IVF/Matroska encodes, native comparison clips and
stills, metrics and packet lists, models/probes, validation outputs, isolated
binaries, build logs and a report/script snapshot from `44c14d5f`.

- `CASE/TAG-detail.tar.zst` preserves selected raw final-TU exports.
- `CASE/TAG-trace.tar.zst` preserves all realized quantizer/block/transform maps,
  including calibration attempts. Member SHA-256 manifests accompany each bundle.
- `CASE/TAG-stages.json` and `.npz` retain parsed values, maps and consistency checks.
- `CASE/native-clip-validation.json` verifies four panels × 240 frames exactly.
- `diagnostic-frames.json` identifies retained one-frame application/source/base
  raw pictures: 1920×1080 planar yuv420p10le.
- `cleanup-manifest.json` records only this task's retired files. Full-length raw
  arrays, decoded intermediates, unselected/failed streams, build and virtualenv
  are reproducible from committed commands. Traces were content-compared before
  removing their uncompressed copies.

To inspect a trace, extract its bundle into **fresh scratch**, for example:

```bash
mkdir -p /tmp/downloads/codex-work/pantheon-trace-review
tar --zstd -xf /media/merged-storage/cold-storage/docker-apps/pantheon-quantization-20261019/e05-1440/detail2-detail.tar.zst -C /tmp/downloads/codex-work/pantheon-trace-review
```

Do not point experiment scripts at the archive. Their saved absolute paths describe
execution-time locations. Rebuild through [REPRODUCE.md](REPRODUCE.md), using a
new `PANTHEON_QUANT_DIR`. No scheduled service, container-specific mount or Git
worktree referenced this task directory; the archive tool also checked open files.
No experiment job remains. Production binaries, configuration, library files and
torrents were untouched.
