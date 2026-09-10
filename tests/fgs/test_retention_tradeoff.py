import copy
import unittest

from retention_tradeoff import compare, prepare


class TradeoffTests(unittest.TestCase):
    def manifest(self):
        return dict(binaries={name: dict(path='/encoder/' + name, sha256=letter * 64)
                              for name, letter in [('production', 'a'), ('qualified_auto', 'b')]},
                    cases=[dict(name='sdr', source='/fixtures/source.mkv', sha256='c' * 64,
                                identity={}, frames=1440, source_kind='original',
                                content_class='1080p_sdr', video_properties={'r_frame_rate': '24/1'},
                                prefix=['--avhw', '--seek', '00:02:00'],
                                arguments=['--codec', 'av1', '--output-depth', '10', '--qvbr', '30',
                                           '--max-bitrate', '50000', '--av1-film-grain',
                                           'denoiser=bilateral,retain=auto,retain-max=0.5',
                                           '--master-display', 'copy'])])

    def test_pinned_matrix_preserves_properties_and_isolates_modes(self):
        source = self.manifest()
        before = copy.deepcopy(source)
        plan = prepare(source, '/scratch/encodes')
        self.assertEqual(source, before)
        self.assertEqual(len(plan['jobs']), 10)
        for job in plan['jobs']:
            command = job['command']
            self.assertEqual(command[command.index('--master-display') + 1], 'copy')
            self.assertEqual(command[command.index('--seek') + 1], '00:02:00')
            self.assertEqual(command[command.index('--frames') + 1], '1440')
            if job['mode'] == 'plain':
                self.assertNotIn('--av1-film-grain', command)
            else:
                grain = command[command.index('--av1-film-grain') + 1]
                self.assertEqual(grain.count('retain='), 1)
                self.assertNotIn('retain-max=0.5', grain)
                self.assertIn('retain=auto' if job['mode'] == 'auto' else 'retain=0', grain)
        self.assertEqual(plan['status'], 'prepared_not_executed')

    def test_reference_identity_changes_with_window_or_source(self):
        manifest = self.manifest()
        original = prepare(manifest, '/scratch')['cases'][0]['reference_id']
        manifest['cases'][0]['prefix'][-1] = '00:03:00'
        self.assertNotEqual(original, prepare(manifest, '/scratch')['cases'][0]['reference_id'])

    def test_ambiguous_or_transcoded_references_rejected(self):
        for key, value in [('source_kind', 'library_transcode'), ('frames', 0), ('sha256', '')]:
            manifest = self.manifest()
            manifest['cases'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                prepare(manifest, '/scratch')
        manifest = self.manifest()
        manifest['cases'] *= 2
        with self.assertRaises(ValueError):
            prepare(manifest, '/scratch')

    def row(self, mode, size, score=95.0, **extra):
        return dict(case='sdr', arm=mode + str(size), mode=mode, anchor=mode == 'auto',
                    video_bytes=size, reference_id='a' * 64, quality_checks_passed=True,
                    metrics={'vmaf': dict(value=score, definition='sdr-grain-on-model-A')}, **extra)

    def test_actual_bytes_select_match_and_scores_do_not_imply_visible_gain(self):
        result = compare([self.row('auto', 1300, 96), self.row('current_fgs', 1000),
                          self.row('current_fgs', 1290, 95.5)])['comparisons'][0]
        self.assertEqual(result['comparison_arm'], 'current_fgs1290')
        self.assertEqual(result['status'], 'matched')
        self.assertEqual(result['auto_minus_comparison_metrics']['vmaf'], .5)
        self.assertEqual(result['visible_quality_gain'], 'not_established_by_numeric_scores')

    def test_equal_nominal_settings_do_not_make_a_size_match(self):
        result = compare([self.row('auto', 1300), self.row('current_fgs', 1000)])['comparisons'][0]
        self.assertEqual(result['status'], 'needs_more_size_points')
        self.assertNotIn('auto_minus_comparison_metrics', result)

    def test_metric_definitions_and_reference_provenance_must_match(self):
        auto, other = self.row('auto', 1300), self.row('current_fgs', 1300)
        other['metrics']['vmaf']['definition'] = 'hdr-tonemapped-model-B'
        result = compare([auto, other])['comparisons'][0]
        self.assertEqual(result['missing_or_incompatible_metrics'], ['vmaf'])
        self.assertEqual(result['auto_minus_comparison_metrics'], {})
        other['reference_id'] = 'b' * 64
        self.assertEqual(compare([auto, other])['comparisons'][0]['status'], 'missing_valid_comparison')
        other['reference_id'] = auto['reference_id']
        other['quality_checks_passed'] = False
        self.assertEqual(compare([auto, other])['comparisons'][0]['status'], 'missing_valid_comparison')

    def test_duplicate_or_nonfinite_measurements_rejected(self):
        row = self.row('auto', 1300)
        with self.assertRaises(ValueError):
            compare([row, row])
        row['metrics']['vmaf']['value'] = float('nan')
        with self.assertRaises(ValueError):
            compare([row])


if __name__ == '__main__':
    unittest.main()
