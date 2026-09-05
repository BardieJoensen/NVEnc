#!/usr/bin/env python3
"""Verify private FGS fixtures against the committed hash manifest."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

DEFAULT_ROOT = '/media/merged-storage/validation-fixtures/nvenc-fgs/v1'
MANIFEST = Path(__file__).with_name('fixtures.json')


def verify(root, manifest, names):
    artifacts = manifest['artifacts']
    result = {}
    for name in dict.fromkeys(names or artifacts):
        if name not in artifacts:
            raise ValueError(f'unknown fixture: {name}')
        artifact = artifacts[name]
        path = root / artifact['file']
        if not path.is_file():
            raise ValueError(f'missing pinned fixture: {path}; see tests/fgs/FIXTURES.md')
        with path.open('rb') as source:
            digest = hashlib.sha256()
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                digest.update(chunk)
            actual = digest.hexdigest()
        if actual != artifact['sha256']:
            raise ValueError(f'fixture hash mismatch: {path}; expected {artifact["sha256"]}, got {actual}')
        result[name] = {'path': str(path), 'sha256': actual}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=os.environ.get('FGS_GATE_FIXTURES', DEFAULT_ROOT))
    parser.add_argument('--manifest', type=Path, default=MANIFEST)
    parser.add_argument('--check', nargs='+')
    args = parser.parse_args()
    try:
        checked = verify(args.root, json.loads(args.manifest.read_text()), args.check)
    except (OSError, ValueError) as error:
        print(f'FGS fixtures: {error}', file=sys.stderr)
        return 2
    print(json.dumps({'root': str(args.root), 'verified': checked}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
