#!/usr/bin/env python3
"""Assemble the pinned, qualified FEL binaries into an isolated runtime image.

This packages existing build artifacts; it is not a from-source dependency
build. The receipt identifies every copied file, the host Python packages and
the immutable base image. Rebuilding dependencies requires requalification.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from fel_metadata import sha


QUALIFIED = {
    'prefix/bin/vspipe': '029c9e93c040bbd11f251aa0c0f504131f62402f445a502431c05ba54fe1c43f',
    'prefix/lib/libffms2.so': '98f750ad61d81197b3a17d0171bfba1c4fe38c8fb67ce49cf4b1e5b2fa2409a5',
    'build/felbaker/libfelbaker.so': 'c02b11fcd7d5378a4d679d5b4f7d13ccbbd0f72ba2c39b213971318ea0e94397',
}


def bundle(runtime, output, base_image):
    runtime, output = Path(runtime).resolve(strict=True), Path(output).resolve()
    if not base_image.startswith('sha256:') or len(base_image) != 71:
        raise ValueError('An immutable, local base image ID is required')
    actual = json.loads(subprocess.check_output(['docker', 'image', 'inspect', base_image]))[0]['Id']
    if actual != base_image:
        raise ValueError('Base image identity changed')
    # Dockerfile FROM resolves names, not local configuration IDs. Create a
    # private tag containing the entire verified ID, and retain both identities.
    base_tag = 'nvenc-fgs/fel-base:' + base_image.removeprefix('sha256:')
    existing = subprocess.run(['docker', 'image', 'inspect', base_tag],
                              capture_output=True, text=True)
    if existing.returncode == 0 and json.loads(existing.stdout)[0]['Id'] != base_image:
        raise ValueError('The private base-image tag already names another image')
    subprocess.run(['docker', 'image', 'tag', base_image, base_tag], check=True)
    for name, expected in QUALIFIED.items():
        if sha(runtime / name) != expected:
            raise ValueError('Unqualified reconstruction artifact: ' + name)
    output.mkdir(parents=True, exist_ok=False)
    root = output / 'fel'
    def copy(source, relative):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination, follow_symlinks=True)
    for name in [*QUALIFIED, 'prefix/lib/libvapoursynth.so',
                 'prefix/lib/libvapoursynth-script.so.0',
                 'prefix/lib/python3.12/site-packages/vapoursynth.so']:
        copy(runtime / name, 'runtime/' + name)
    # Ship a matching executable, embedding library and standard library. This
    # avoids mixing the host's Python patch version with the base image's one.
    copy('/usr/bin/python3.12', 'python/bin/python3.12')
    copy('/lib/x86_64-linux-gnu/libpython3.12.so.1.0', 'python/lib/libpython3.12.so.1.0')
    shutil.copytree('/usr/lib/python3.12', root / 'python/lib/python3.12',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ['fel_input.vpy', 'fel_reconstruct.py', 'fel_metadata.py', 'fel_parameter_bounds.py']:
        copy(Path(__file__).parent / name, 'tools/' + name)
    receipt = dict(base_image=base_image, base_tag=base_tag, qualified_binaries=QUALIFIED,
        python_packages=subprocess.check_output(['dpkg-query', '-W',
            'python3.12-minimal', 'libpython3.12-minimal', 'libpython3.12-stdlib',
            'libpython3.12t64'], text=True).splitlines(),
        files={str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*')) if p.is_file()},
        provenance='Assembly of pinned trial artifacts, not a new source build')
    (root / 'runtime-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    (output / 'Dockerfile').write_text(f'''FROM {base_tag}
COPY fel /opt/fel
ENV PYTHONHOME=/opt/fel/python \\
    PYTHONPATH=/opt/fel/runtime/prefix/lib/python3.12/site-packages:/opt/fel/tools \\
    LD_LIBRARY_PATH=/opt/fel/python/lib:/opt/fel/runtime/prefix/lib \\
    PYTHONDONTWRITEBYTECODE=1 \\
    OPENBLAS_NUM_THREADS=1 \\
    OMP_NUM_THREADS=1
RUN /opt/fel/python/bin/python3.12 -c "import fractions,hashlib,json,vapoursynth; c=vapoursynth.core; c.std.LoadPlugin('/opt/fel/runtime/prefix/lib/libffms2.so'); c.std.LoadPlugin('/opt/fel/runtime/build/felbaker/libfelbaker.so'); print(c)"
USER 1000:1000
ENTRYPOINT ["/opt/fel/runtime/prefix/bin/vspipe"]
''')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--base-image', required=True)
    args = parser.parse_args()
    bundle(args.runtime, args.output_dir, args.base_image)
