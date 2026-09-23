"""Manual Meson/Ninja regression: a CUDA header edit must change the executable.

Requires NVCC on PATH but no GPU. Uses a new scratch directory and never edits
the encoder build. Run with the same Python/Meson environment as that build.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def run(directory, report_path, architecture):
    directory.mkdir(parents=True, exist_ok=False)
    source = directory / 'source'; source.mkdir()
    build = directory / 'build'
    (source / 'meson.build').write_text("project('cuda-header-rebuild', 'cuda')\n"
        "executable('probe', 'probe.cu', cuda_args: ['-arch=" + architecture + "'])\n")
    (source / 'probe.cu').write_text('#include "value.cuh"\n#include <cstdio>\n'
                                   'int main() { std::printf("%d\\n", probe_value); }\n')
    header = source / 'value.cuh'; header.write_text('constexpr int probe_value = 7;\n')
    source_hash = hashlib.sha256((source / 'probe.cu').read_bytes()).hexdigest()
    report = dict(complete=False, source_sha256=source_hash, directory=str(directory))
    def command(args):
        p = subprocess.run(args, capture_output=True, text=True, timeout=120)
        with (directory / 'commands.log').open('a') as out:
            out.write(json.dumps(args) + '\n' + p.stdout + p.stderr)
        p.check_returncode(); return p.stdout.strip()
    try:
        report['meson_version'] = command([sys.executable, '-m', 'mesonbuild.mesonmain', '--version'])
        command([sys.executable, '-m', 'mesonbuild.mesonmain', 'setup', str(build), str(source)])
        command(['ninja', '-C', str(build), '-j', '1'])
        report['before'] = command([str(build / 'probe')])
        assert report['before'] == '7'
        # Change only an included header; the .cu file and command stay fixed.
        header.write_text('constexpr int probe_value = 13;\n')
        command(['ninja', '-C', str(build), '-j', '1'])
        report['after_header_edit'] = command([str(build / 'probe')])
        assert hashlib.sha256((source / 'probe.cu').read_bytes()).hexdigest() == source_hash
        assert report['after_header_edit'] == '13', 'CUDA header edit reused stale object code'
        dependencies = command(['ninja', '-C', str(build), '-t', 'deps'])
        assert 'value.cuh' in dependencies
        (directory / 'dependencies.txt').write_text(dependencies + '\n')
        report['complete'] = True
    except BaseException as error:
        report['error'] = repr(error)
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path); parser.add_argument('report', type=Path)
    parser.add_argument('--architecture', default='sm_120', choices=['sm_75', 'sm_80', 'sm_86', 'sm_89', 'sm_90', 'sm_120'])
    args = parser.parse_args(); run(args.directory, args.report, args.architecture)
