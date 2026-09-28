import unittest
import numpy as np
from recovery_audit_reference import measure_plane


class RecoveryAuditReferenceTests(unittest.TestCase):
    def test_known_energy_loss_and_depth_units(self):
        rng = np.random.default_rng(20260928)
        source = (128+2*rng.integers(-3, 4, (128, 128))).astype(np.uint16)
        previous = (128+2*rng.integers(-3, 4, source.shape)).astype(np.uint16)
        base = (128+(source.astype(np.int32)-128)//2).astype(np.uint16)
        a = measure_plane(source, previous, base, source, 8, 0)
        b = measure_plane(source*4, previous*4, base*4, source*4, 10, 0)
        self.assertTrue(np.all(a['reasons'] == 0))
        np.testing.assert_allclose(a['base_variance'], a['source_variance']*.25)
        np.testing.assert_allclose(a['output_variance'], a['source_variance'])
        for key in a:
            if isinstance(a[key], np.ndarray):
                np.testing.assert_array_equal(a[key], b[key])
        self.assertFalse(a['source_admission'])

    def test_output_cannot_change_source_screen(self):
        rng = np.random.default_rng(719)
        source = rng.integers(100, 107, (64, 96), dtype=np.uint16)
        previous = rng.integers(100, 107, source.shape, dtype=np.uint16)
        a = measure_plane(source, previous, source, source, 8, 1)
        b = measure_plane(source, previous, np.zeros_like(source), np.full_like(source, 255), 8, 1)
        for key in ['coordinates', 'reasons', 'stable_constant', 'temporal_correlation',
                    'gradient_coherence', 'source_variance']:
            np.testing.assert_array_equal(a[key], b[key])

    def test_persistent_texture_is_unsupported(self):
        rng = np.random.default_rng(93)
        source = rng.integers(120, 137, (64, 64), dtype=np.uint16)
        result = measure_plane(source, source, source, source, 8, 0)
        self.assertTrue(np.all(result['reasons'] & 4))
        self.assertFalse(result['stable_constant'][0])

    def test_quiet_and_mean_error_do_not_cancel(self):
        source = np.full((64, 64), 128, dtype=np.uint16)
        output = source.copy(); output[:, :32] -= 1; output[:, 32:] += 1
        result = measure_plane(source, source, source, output, 8, 1)
        self.assertTrue(np.all(result['stable_constant']))
        self.assertTrue(np.all(result['reasons'] != 0))
        np.testing.assert_array_equal(result['output_mean_error'], [-1, 1, -1, 1])
        np.testing.assert_array_equal(result['added_grain_rms'], [1]*4)

    def test_partial_borders_are_explicit(self):
        source = np.full((66, 70), 128, dtype=np.uint16)
        result = measure_plane(source, source, source, source, 8, 0)
        self.assertEqual(result['unmeasured_border_samples'], 66*70-64*64)
        self.assertEqual(len(result['coordinates']), 1)

    def test_direct_least_squares_across_batch_boundary(self):
        rng = np.random.default_rng(116)
        source = rng.integers(80, 121, (32, 32*129), dtype=np.uint16)
        previous = rng.integers(80, 121, source.shape, dtype=np.uint16)
        base = rng.integers(90, 111, source.shape, dtype=np.uint16)
        output = rng.integers(75, 126, source.shape, dtype=np.uint16)
        result = measure_plane(source, previous, base, output, 8, 2)
        y, x = np.mgrid[:32, :32]
        design = np.stack([np.ones(32*32), x.ravel(), y.ravel()], axis=1)
        for i in (0, 127, 128):
            for name, values in [('source', source), ('base', base), ('output', output)]:
                tile = values[:, i*32:(i+1)*32].astype(float).ravel()
                residual = tile-design@np.linalg.lstsq(design, tile, rcond=None)[0]
                self.assertAlmostEqual(result[name+'_variance'][i], np.mean(residual**2), places=11)

    def test_moving_texture_does_not_become_source_admission(self):
        rng = np.random.default_rng(912)
        texture = rng.integers(120, 137, (128, 128), dtype=np.uint16)
        moved = np.roll(texture, 11, axis=1)
        result = measure_plane(moved, texture, moved, moved, 8, 0)
        self.assertTrue(np.any(result['reasons'] == 0))
        self.assertFalse(result['source_admission'])

    def test_invalid_inputs(self):
        source = np.full((64, 64), 128, dtype=np.uint16)
        for bad in [source[:-1], source.astype(float), np.full_like(source, 256)]:
            with self.assertRaises(ValueError):
                measure_plane(source, source, source, bad, 8, 0)
        with self.assertRaises(ValueError):
            measure_plane(source, source, source, source, 9, 0)


if __name__ == '__main__':
    unittest.main()
