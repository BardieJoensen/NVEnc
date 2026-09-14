"""Build explicitly diagnostic FelBaker controls from the pinned source."""
from pathlib import Path
import difflib
import hashlib
import json
import shutil
import subprocess

ROOT = Path('/trial')
SOURCE = ROOT / 'src/felbaker'


def replace(text, before, after):
    if text.count(before) != 1:
        raise RuntimeError('unexpected upstream source: ' + before)
    return text.replace(before, after, 1)


def build(mode):
    output = ROOT / 'build' / ('felbaker-' + mode)
    output.mkdir(exist_ok=True)
    src = output / 'src'
    shutil.copytree(SOURCE / 'src', src, dirs_exist_ok=True)
    p = src / 'VapourSynthEntry.cpp'
    text = replace(p.read_text(), '"com.vapoursynth.felbaker", "fel"',
                   f'"com.vapoursynth.felbaker.trial.{mode}", "fel_{mode}"')
    p.write_text(text)
    if mode == 'noresidual':
        p = src / 'RpuProcessor.h'
        p.write_text(replace(p.read_text(), 'return !skipEl;', 'return false; /* Trial: omit residual only. */'))
    elif mode == 'compat':
        p = src / 'RpuProcessor.h'; text = p.read_text()
        for sample, channel in [('y', 'Y'), ('u', 'U'), ('v', 'V')]:
            text = replace(text, f'const int {sample}f = ({sample} << YCC_TO_RGB_INPUT_SHIFT)',
                           f'const int {sample}f = {sample}')
        text = replace(text, 'static constexpr int MAP_OUT_BIT_DEPTH       = 12;',
                       'static constexpr int MAP_OUT_BIT_DEPTH       = 16;')
        p.write_text(text)
        p = src / 'Utils.h'
        p.write_text(replace(p.read_text(), 'inline constexpr int MAX_12_BIT = 0xFFF;',
                            'inline constexpr int MAX_12_BIT = 0xFFFF;'))
        p = src / 'FelBaker.cpp'; text = p.read_text()
        text = replace(text, '// vsapi->mapSetInt(props, "_ColorRange", !metadata.fullRange, maReplace); // COMPAT:',
                       'vsapi->mapSetInt(props, "_ColorRange", !metadata.fullRange, maReplace); // COMPAT:')
        text = replace(text,
                       'const int mmrYt = 2 + 2 * y  + yR  + blYp[xyl];\n'
                       '                    const int mmrYb = 2 + 2 * yB + yBR + blYp[xyl + blStrideY];',
                       'const int xyr = x == blWidthUV - 1 ? xy : xy + 1;\n'
                       '                    const int mmrYt = 2 + 2 * y  + blYp[xyl] + blYp[xyr];\n'
                       '                    const int mmrYb = 2 + 2 * yB + blYp[xyl + blStrideY] + blYp[xyr + blStrideY];')
        p.write_text(text)
    else:
        raise ValueError(mode)
    diffs = []
    for p in sorted(src.iterdir()):
        original = SOURCE / 'src' / p.name
        diffs.extend(difflib.unified_diff(original.read_text().splitlines(True), p.read_text().splitlines(True),
                                        fromfile='upstream/src/' + p.name, tofile=mode + '/src/' + p.name))
    (output / 'diagnostic.patch').write_text(''.join(diffs))
    flags = ['g++', '-fPIC', '-O3', '-DNDEBUG', '-std=c++20', '-ffast-math', '-fno-plt',
             '-fno-semantic-interposition', '-fno-rtti', '-march=x86-64-v3', '-fvisibility=hidden', '-flto',
             '-I' + str(src), '-I' + str(SOURCE / 'external/vapoursynth'),
             '-I/trial/build/felbaker/libdovi']
    objects = []
    commands = []
    for name in ['FelBaker', 'RpuProcessor', 'Spline16Resampler', 'VapourSynthEntry']:
        obj = output / (name + '.o'); objects.append(str(obj))
        command = flags + ['-c', str(src / (name + '.cpp')), '-o', str(obj)]
        subprocess.run(command, check=True); commands.append(command)
    binary = output / ('libfelbaker_' + mode + '.so')
    command = ['g++', '-shared', '-flto', '-o', str(binary), *objects,
               '/trial/build/felbaker/libdovi/libdovi.a', '-ldl', '-lpthread', '-lm']
    subprocess.run(command, check=True); commands.append(command)
    (output / 'build.json').write_text(json.dumps(dict(mode=mode, commands=commands,
        binary=str(binary), sha256=hashlib.sha256(binary.read_bytes()).hexdigest()), indent=2)+'\n')
    print(mode, 'built', flush=True)


if __name__ == '__main__':
    for variant in ['noresidual', 'compat']:
        build(variant)
