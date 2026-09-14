"""Bounded, explicit reconstruction graphs for the isolated FEL trial."""
from pathlib import Path
import os
import re
import vapoursynth as vs

core = vs.core
core.num_threads = 4
core.max_cache_size = 256
ROOT=Path(os.environ.get('FEL_TRIAL_ROOT','/trial'))
core.std.LoadPlugin(str(ROOT/'prefix/lib/libffms2.so'))
core.std.LoadPlugin(str(ROOT/'build/felbaker/libfelbaker.so'))
core.std.LoadPlugin(str(ROOT/'build/felbaker-noresidual/libfelbaker_noresidual.so'))
core.std.LoadPlugin(str(ROOT/'build/felbaker-compat/libfelbaker_compat.so'))


def bounded(clip):
    core.std.SetVideoCache(clip, mode=1, fixedsize=1, maxsize=2)
    return clip


def inputs(directory):
    directory = Path(directory)
    bl = core.ffms2.Source(str(directory / 'BL.hevc'), threads=2)
    el = core.ffms2.Source(str(directory / 'EL.hevc'), threads=2)
    expected = int(re.search(r'Frames:\s*(\d+)', (directory / 'command-3.log').read_text())[1])
    if bl.num_frames != el.num_frames or bl.num_frames != expected:
        raise ValueError(f'BL/EL/RPU count mismatch: {bl.num_frames}/{el.num_frames}/{expected}')
    if (bl.fps_num, bl.fps_den) != (el.fps_num, el.fps_den):
        raise ValueError('BL/EL frame-rate mismatch')
    if (bl.width, bl.height) != (3840, 2160) or bl.format.id != vs.YUV420P10:
        raise ValueError('trial is qualified only for the selected 4K 10-bit sources')
    return bounded(bl), bounded(el)


def reconstructed(bl, el, mode='default', external=True):
    plugin = {'default': core.fel, 'noresidual': core.fel_noresidual, 'compat': core.fel_compat}[mode]
    if external:
        if mode == 'compat':
            raise ValueError('compatibility control requires its original internal resampling')
        el_up = bounded(core.resize.Spline16(el, width=bl.width, height=bl.height))
        yuv = bounded(plugin.Bake(bl, el_up, no_resample=1, dovi_metadata=1))
        rgb = bounded(plugin.ToRGB(bounded(core.resize.Spline16(yuv, format=vs.YUV444P12))))
    else:
        rgb = bounded(plugin.Bake(bl, el, no_resample=0, dovi_metadata=1))
    # The reconstruction yields untrimmed PQ RGB; these are explicit output
    # semantics, never an instruction to replay the source RPU a second time.
    return bounded(core.std.SetFrameProps(rgb, _Matrix=0, _Transfer=16, _Primaries=9, _ColorRange=0, _FieldBased=0))


def rgb_to_pq10(rgb):
    return bounded(core.resize.Spline36(rgb, format=vs.YUV420P10, matrix_s='2020ncl',
        transfer_in_s='st2084', transfer_s='st2084', primaries_in_s='2020', primaries_s='2020',
        range_in_s='full', range_s='limited', dither_type='error_diffusion', chromaloc_s='left'))


def base_rgb(bl):
    return bounded(core.resize.Spline36(bl, format=vs.RGB48, matrix_in_s='2020ncl',
        transfer_in_s='st2084', transfer_s='st2084', primaries_in_s='2020', primaries_s='2020',
        range_in_s='limited', range_s='full'))
