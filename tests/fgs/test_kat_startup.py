"""The startup check accepts retained/synthetic grain and rejects gaps/flashes."""
from pathlib import Path
import tempfile
import unittest

import numpy as np
import fgs_kat as kat


class StartupMeasurementTests(unittest.TestCase):
    def test_retention_synthesis_gap_and_excess_at_both_depths(self):
        for bits in (8, 10):
            spec = dict(width=768, height=64, bits=bits)
            kat.apply_spec(spec)
            rng = np.random.default_rng(20260916)
            base = kat.base_luma()
            scale = 1 << (bits - 8)
            dtype = np.uint8 if bits == 8 else np.dtype('<u2')
            source = [np.rint(base + rng.normal(0, 6 * scale, base.shape)).astype(dtype)
                      for _ in range(3)]
            independent = [np.rint(base + rng.normal(0, 6 * scale, base.shape)).astype(dtype)
                           for _ in range(3)]
            chroma = np.full((32, 384), 128 * scale, dtype=dtype).tobytes()
            with tempfile.TemporaryDirectory() as directory:
                src, output = Path(directory) / 'source.y4m', Path(directory) / 'on.yuv'
                with src.open('wb') as stream:
                    stream.write(b'YUV4MPEG2 W768 H64 F24:1 Ip A1:1\n')
                    for y in source:
                        stream.write(b'FRAME\n' + y.tobytes() + chroma * 2)
                for kind, pictures, expected in [
                    ('retained', source, True), ('synthesized', independent, True),
                    ('single gap', [source[0], base.astype(dtype), source[2]], False),
                    ('single flash', [source[0], np.rint(base + 2 * (source[1].astype(float) - base)).astype(dtype), source[2]], False),
                ]:
                    output.write_bytes(b''.join(y.tobytes() + chroma * 2 for y in pictures))
                    ratios = kat.startup_grain_ratios(src, output, spec, count=3)
                    passed = bool((ratios > .60).all() and (ratios < 1.35).all())
                    self.assertEqual(passed, expected, (bits, kind, ratios.min(), ratios.max()))


if __name__ == '__main__':
    unittest.main()
