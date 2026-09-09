#!/usr/bin/env python3
"""Prepare additive server/node plugin archives and exact rollback copies.

Reads the installed files, writes a fresh staging directory, and does not modify
the server. The caller installs these artifacts while its Tdarr server and node
are stopped, after jobs have drained. The old archive's unrelated entries remain
byte-for-byte identical when decompressed.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import zipfile


def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def prepare(bundle, plugins, archive, output):
    manifest = json.loads((bundle / 'bundle.json').read_text())
    selected = {name: value for name, value in manifest['files'].items() if name.startswith('FlowPlugins/')}
    if not selected:
        raise ValueError('Bundle has no plugin files')
    for name, expected in selected.items():
        if digest(bundle / name) != expected:
            raise ValueError('Bundle plugin changed: ' + name)
    output.mkdir()
    archive_hash = digest(archive)
    shutil.copy2(archive, output / 'rollback-nodePlugins.Zip')
    replacements = {}
    for name, expected in selected.items():
        installed = plugins / name
        old_hash = digest(installed) if installed.exists() else None
        if old_hash:
            target = output / 'rollback-plugins' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(installed, target)
            if digest(target) != old_hash:
                raise ValueError('Installed plugin changed while preparing rollback')
        replacements[name] = dict(before_sha256=old_hash, after_sha256=expected)
    with zipfile.ZipFile(archive) as old:
        normalized = {n.removeprefix('./'): n for n in old.namelist() if not n.endswith('/')}
        if len(normalized) != sum(not n.endswith('/') for n in old.namelist()):
            raise ValueError('Ambiguous old plugin archive')
        with zipfile.ZipFile(output / 'candidate-nodePlugins.Zip', 'w', compression=zipfile.ZIP_DEFLATED) as new:
            for info in old.infolist():
                name = info.filename.removeprefix('./')
                if name not in selected:
                    new.writestr(copy.copy(info), old.read(info))
            for name in selected:
                info = zipfile.ZipInfo.from_file(bundle / name)
                info.filename = normalized.get(name, name)
                info.compress_type = zipfile.ZIP_DEFLATED
                new.writestr(info, (bundle / name).read_bytes())
        with zipfile.ZipFile(output / 'candidate-nodePlugins.Zip') as new:
            if new.testzip() is not None:
                raise ValueError('Candidate archive failed integrity check')
            for info in old.infolist():
                if info.filename.removeprefix('./') not in selected and new.read(info.filename) != old.read(info):
                    raise ValueError('Unrelated archived plugin changed')
            for name, expected in selected.items():
                if hashlib.sha256(new.read(normalized.get(name, name))).hexdigest() != expected:
                    raise ValueError('Candidate archived plugin changed')
    if digest(archive) != archive_hash or digest(output / 'rollback-nodePlugins.Zip') != archive_hash:
        raise ValueError('Installed archive changed during preparation')
    result = dict(schema='fgs_tdarr_plugin_update_v1', bundle=str(bundle.resolve()),
        plugins=str(plugins.resolve()), archive=str(archive.resolve()), files=replacements,
        rollback_archive_sha256=archive_hash,
        candidate_archive_sha256=digest(output / 'candidate-nodePlugins.Zip'),
        installation='not performed; install only with the target server and node stopped')
    (output / 'plugin-update.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle', 'plugins', 'archive', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.bundle, args.plugins, args.archive, args.output), indent=2))
