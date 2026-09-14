"""Bounded FEL-to-PQ graph for an explicitly prepared, unchanged source pair.

Import from a .vpy entry point; create_graph accepts a manifest dictionary.
It deliberately provides no library replacement or implicit HDR10 fallback.
"""
from fractions import Fraction
import json
from pathlib import Path

from fel_metadata import sha


def read_rpus(path):
    data = Path(path).read_bytes()
    prefix = b'\x00\x00\x00\x01'
    if not data.startswith(prefix):
        raise ValueError('Expected dovi_tool four-byte-prefixed RPU file')
    rows = data[len(prefix):].split(prefix)
    if not rows or any(not row or row[0] != 0x19 for row in rows):
        raise ValueError('Empty or invalid RPU in prepared source')
    return rows


def create_graph(config):
    import vapoursynth as vs
    core = vs.core
    core.num_threads = 4
    core.max_cache_size = 256
    runtime = Path(config['runtime'])
    directory = Path(config['components'])
    cache = Path(config['cache'])
    cache.mkdir(parents=True, exist_ok=True)
    metadata_dir = Path(config['metadata'])
    report = json.loads((metadata_dir / 'metadata-report.json').read_text())
    if report.get('complete') is not True:
        raise ValueError('Metadata preparation did not pass')
    if report.get('reconstruction_contract') != 'p7-fel-pq-bt2020-v2':
        raise ValueError('Reconstruction input contract has not been verified')
    for name, expected in config['component_sha256'].items():
        if name not in ['BL.hevc', 'EL.hevc', 'RPU.bin'] or sha(directory / name) != expected:
            raise ValueError('Changed or unknown prepared component: ' + name)
    if set(config['component_sha256']) != {'BL.hevc', 'EL.hevc', 'RPU.bin'}:
        raise ValueError('All three prepared component hashes are required')
    if report['source_sha256'] != config['component_sha256']['RPU.bin']:
        raise ValueError('Metadata was prepared from another RPU file')
    if sha(metadata_dir / 'pq-rpu.bin') != report['output_sha256']:
        raise ValueError('Prepared output metadata changed')
    layer_order = json.loads((metadata_dir / 'layer-order.json').read_text())
    if (layer_order.get('complete') is not True or layer_order.get('frames') != report['frames']
        or any(layer_order.get(layer, {}).get('sha256') != config['component_sha256'][name]
               for layer, name in [('bl', 'BL.hevc'), ('el', 'EL.hevc')])):
        raise ValueError('Missing or mismatched independent layer-order check')
    for relative, expected in config['runtime_sha256'].items():
        if sha(runtime / relative) != expected:
            raise ValueError('Changed reconstruction dependency: ' + relative)
    required = {'prefix/lib/libffms2.so', 'build/felbaker/libfelbaker.so'}
    if not required.issubset(config['runtime_sha256']):
        raise ValueError('Reconstruction plugin hashes are required')
    core.std.LoadPlugin(str(runtime / 'prefix/lib/libffms2.so'))
    core.std.LoadPlugin(str(runtime / 'build/felbaker/libfelbaker.so'))
    def bounded(clip):
        core.std.SetVideoCache(clip, mode=1, fixedsize=1, maxsize=2)
        return clip
    bl = bounded(core.ffms2.Source(str(directory / 'BL.hevc'), threads=2,
                                   cachefile=str(cache / 'bl.ffindex')))
    el = bounded(core.ffms2.Source(str(directory / 'EL.hevc'), threads=2,
                                   cachefile=str(cache / 'el.ffindex')))
    fps = Fraction(config['fps'])
    for layer in [bl, el]:
        if layer.num_frames != report['frames'] or Fraction(layer.fps_num, layer.fps_den) != fps:
            raise ValueError('Decoded BL/EL frame count or clock mismatch')
        if layer.format.id != vs.YUV420P10:
            raise ValueError('Only ten-bit 4:2:0 layers are qualified')
    if (bl.width, bl.height, el.width, el.height) != (3840, 2160, 1920, 1080):
        raise ValueError('Only 4K BL / 1080p EL is currently qualified')
    rpus = read_rpus(directory / 'RPU.bin')
    if len(rpus) != report['frames']:
        raise ValueError('Binary RPU count mismatch')
    scenes = set(report['scenes'])
    def check_bl(n, f):
        frame = f
        expected = dict(_FieldBased=0, _Matrix=9, _Transfer=16, _Primaries=9,
                        _ColorRange=1, _ChromaLocation=2)
        if any(frame.props.get(k) != v for k, v in expected.items()):
            raise ValueError(f'Unsupported base-layer colour or field properties at frame {n}')
        return frame
    bl = bounded(core.std.ModifyFrame(bl, clips=bl, selector=check_bl))
    def check_rpu(n, f):
        frame = f
        # FFMS/libavcodec reorder the EL to display order. Compare the exact
        # attached RPU with dovi_tool's independently extracted display list.
        if bytes(frame.props.get('DolbyVisionRPU', b'')) != rpus[n]:
            raise ValueError(f'EL/RPU display-order mismatch at frame {n}')
        if frame.props.get('_FieldBased') != 0:
            raise ValueError('Interlaced enhancement layer is unqualified')
        return frame
    checked_el = bounded(core.std.ModifyFrame(el, clips=el, selector=check_rpu))
    el_up = bounded(core.resize.Spline16(checked_el, width=bl.width, height=bl.height))
    yuv = bounded(core.fel.Bake(bl, el_up, no_resample=1, dovi_metadata=1))
    rgb = bounded(core.fel.ToRGB(bounded(core.resize.Spline16(yuv, format=vs.YUV444P12))))
    def check_picture(n, f):
        frame = f
        if bool(frame.props.get('_SceneChangePrev', False)) != (n in scenes):
            raise ValueError(f'Reconstructed picture/scene metadata mismatch at frame {n}')
        return frame
    rgb = bounded(core.std.ModifyFrame(rgb, clips=rgb, selector=check_picture))
    rgb = bounded(core.std.SetFrameProps(rgb, _Matrix=0, _Transfer=16, _Primaries=9,
                                         _ColorRange=0, _FieldBased=0))
    return bounded(core.resize.Spline36(rgb, format=vs.YUV420P10, matrix_s='2020ncl',
        transfer_in_s='st2084', transfer_s='st2084', primaries_in_s='2020', primaries_s='2020',
        range_in_s='full', range_s='limited', dither_type='error_diffusion', chromaloc_s='left'))
