#!/usr/bin/env python3
"""Install or restore a prepared plugin update with both Tdarr containers stopped."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

from prepare_tdarr_plugin_update import digest


def archives_equivalent(actual, expected):
    """Recognize a Tdarr repack without accepting changed members or permissions.

    ZIP timestamps, compression and UTF-8/data-descriptor flags can change on
    regeneration. Require the exact decoded names, bytes, types and Unix modes.
    Duplicate names and encrypted or otherwise changed flags remain errors.
    """
    try:
        with zipfile.ZipFile(actual) as a, zipfile.ZipFile(expected) as b:
            left = {i.filename: i for i in a.infolist()}
            right = {i.filename: i for i in b.infolist()}
            if (len(left) != len(a.infolist()) or len(right) != len(b.infolist())
                    or left.keys() != right.keys()):
                return False
            for name, one in left.items():
                two = right[name]
                if (one.file_size != two.file_size or one.is_dir() != two.is_dir()
                        or one.external_attr != two.external_attr
                        or one.create_system != two.create_system
                        or one.flag_bits & 1 or two.flag_bits & 1
                        or (one.flag_bits ^ two.flag_bits) & ~0x808):
                    return False
                with a.open(one) as x, b.open(two) as y:
                    while True:
                        block = x.read(1024 * 1024)
                        if block != y.read(1024 * 1024):
                            return False
                        if not block:
                            break
            return True
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, NotImplementedError):
        return False


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
    observed_archive = digest(archive)
    repacked = observed_archive not in (archive_before, archive_after)
    if repacked:
        known = [(prepared / 'rollback-nodePlugins.Zip', archive_before),
                 (prepared / 'candidate-nodePlugins.Zip', archive_after)]
        if not any(digest(path) == expected and archives_equivalent(archive, path)
                   for path, expected in known):
            raise ValueError('Installed plugin archive changed outside this update')
    source_archive = prepared / ('rollback-nodePlugins.Zip' if rollback else 'candidate-nodePlugins.Zip')
    expected_archive = archive_before if rollback else archive_after
    if digest(source_archive) != expected_archive:
        raise ValueError('Prepared plugin archive changed')
    if digest(archive) != observed_archive:
        raise ValueError('Installed plugin archive changed during verification')
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
    return dict(complete=True, rollback=rollback, plugins=len(operations), archive_sha256=expected_archive,
                equivalent_repack_verified=repacked, previous_archive_sha256=observed_archive)


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
