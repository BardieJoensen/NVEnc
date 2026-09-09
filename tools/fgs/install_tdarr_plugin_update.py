#!/usr/bin/env python3
"""Install or restore a prepared plugin update with both Tdarr containers stopped."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from prepare_tdarr_plugin_update import digest


def atomic_copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.fgs-plugin-', dir=destination.parent)
    os.close(fd)
    try:
        shutil.copy2(source, temporary)
        with open(temporary, 'rb') as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply(prepared, rollback=False):
    record = json.loads((prepared / 'plugin-update.json').read_text())
    if record['schema'] != 'fgs_tdarr_plugin_update_v1':
        raise ValueError('Unknown prepared plugin update')
    bundle, plugins, archive = (Path(record[k]) for k in ('bundle', 'plugins', 'archive'))
    operations = []
    for name, hashes in record['files'].items():
        destination = plugins / name
        current = digest(destination) if destination.exists() else None
        if current not in (hashes['before_sha256'], hashes['after_sha256']):
            raise ValueError('Installed plugin changed outside this update: ' + name)
        source = prepared / 'rollback-plugins' / name if rollback else bundle / name
        expected = hashes['before_sha256'] if rollback else hashes['after_sha256']
        if expected is not None and digest(source) != expected:
            raise ValueError('Prepared plugin artifact changed: ' + name)
        operations.append((source, destination, expected))
    archive_before, archive_after = record['rollback_archive_sha256'], record['candidate_archive_sha256']
    if digest(archive) not in (archive_before, archive_after):
        raise ValueError('Installed plugin archive changed outside this update')
    source_archive = prepared / ('rollback-nodePlugins.Zip' if rollback else 'candidate-nodePlugins.Zip')
    expected_archive = archive_before if rollback else archive_after
    if digest(source_archive) != expected_archive:
        raise ValueError('Prepared plugin archive changed')
    # Check all inputs before modifying any file. A retry accepts either this
    # update's old or new bytes, allowing recovery after an interrupted copy.
    for source, destination, expected in operations:
        if expected is None:
            destination.unlink(missing_ok=True)
        else:
            atomic_copy(source, destination)
            if digest(destination) != expected:
                raise ValueError('Installed plugin does not match its artifact')
    atomic_copy(source_archive, archive)
    if digest(archive) != expected_archive:
        raise ValueError('Installed plugin archive does not match its artifact')
    return dict(complete=True, rollback=rollback, plugins=len(operations), archive_sha256=expected_archive)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--server-container', required=True)
    parser.add_argument('--node-container', required=True)
    parser.add_argument('--rollback', action='store_true')
    args = parser.parse_args()
    for container in (args.server_container, args.node_container):
        running = subprocess.check_output(['docker', 'inspect', '--format', '{{.State.Running}}', container], text=True).strip()
        if running != 'false':
            raise RuntimeError('Container must be stopped before plugin installation: ' + container)
    print(json.dumps(apply(args.prepared, args.rollback), indent=2))
