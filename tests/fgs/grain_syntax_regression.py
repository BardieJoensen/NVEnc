#!/usr/bin/env python3
"""Check an independently diagnosed malformed grain header and a valid control."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import fixtures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=fixtures.DEFAULT_ROOT)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    pinned = fixtures.verify(args.root, json.loads(fixtures.MANIFEST.read_text()),
                             ['invalid_chroma_negative', 'gentlemen_guard_positive'])
    repo = Path(__file__).resolve().parents[2]; scanner = args.output / 'fgs-scan'
    flags = shlex.split(subprocess.check_output(
        ['pkg-config', '--cflags', '--libs', '--static', 'libavformat', 'libavcodec', 'libavutil'], text=True))
    subprocess.run(['g++', '-std=c++17', '-O2', '-I', str(repo / 'NVEncCore'),
                    str(repo / 'tests/fgs/scan_bitstream.cpp'), '-o', str(scanner), *flags], check=True)
    reports = {}
    for name in pinned:
        result = subprocess.run([str(scanner), '--syntax-only', pinned[name]['path']], capture_output=True, text=True)
        report = json.loads(result.stdout); reports[name] = dict(report, exit_code=result.returncode)
        if name == 'invalid_chroma_negative':
            if result.returncode != 2 or report['verdict'] != 'invalid_grain' or report['complete']:
                raise RuntimeError('malformed chroma header was not rejected')
            if report.get('rejection_reason') != '4:2:0 grain must enable both chroma components or neither':
                raise RuntimeError('negative failed for the wrong reason')
        elif result.returncode != 0 or report['verdict'] != 'valid_syntax' or not report['complete'] or report['packets'] != 3600:
            raise RuntimeError('valid complete positive was not accepted')
    (args.output / 'report.json').write_text(json.dumps(dict(fixtures=pinned, results=reports), indent=2) + '\n')


if __name__ == '__main__':
    main()
