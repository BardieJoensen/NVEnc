import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('guard', Path(__file__).resolve().parents[2]/'tools/fgs/repair_dovi_guard.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class RepairDoviTests(unittest.TestCase):
    def test_empty_title_equivalence_does_not_hide_named_track_or_language_changes(self):
        original = {'title': '', 'language': 'eng'}
        self.assertEqual(guard.comparable_tags(original), guard.comparable_tags({'language': 'eng'}))
        for changed in [{'language': 'dan'}, {'language': 'eng', 'title': 'Commentary'},
                        {'language': 'eng', 'title': ' '}]:
            self.assertNotEqual(guard.comparable_tags(original), guard.comparable_tags(changed))
        self.assertNotEqual(guard.comparable_tags({'filename': 'font.ttf'}), guard.comparable_tags({'filename': 'other.ttf'}))

    def test_unknown_or_mixed_layers_cannot_be_treated_as_mel(self):
        self.assertEqual(guard.classify('Profile: 7 (MEL)'), 'MEL')
        self.assertEqual(guard.classify('Profile: 7 (FEL)'), 'FEL')
        for text in ['Profile: 8', 'unknown', 'Profile: 7 (MEL)\nProfile: 7 (FEL)']:
            with self.assertRaises(ValueError):guard.classify(text)

    def test_p7_needs_mel_qualified_encoder_and_portable_metadata_arguments(self):
        args = ['--dolby-vision-rpu', 'copy', '--dolby-vision-profile', '10.1']
        guard.admit_p7('MEL', guard.P7_ENCODER, args)
        for kind, encoder, arguments in [('FEL', guard.P7_ENCODER, args),
                                         ('MEL', 'old-encoder', args),
                                         ('MEL', guard.P7_ENCODER, ['--dolby-vision-rpu', '/tmp/vanished.bin', '--dolby-vision-profile', '10.1']),
                                         ('MEL', guard.P7_ENCODER, args + args),
                                         ('MEL', guard.P7_ENCODER, ['--dolby-vision-rpu'])]:
            with self.assertRaises(ValueError):guard.admit_p7(kind, encoder, arguments)


if __name__ == '__main__':unittest.main()
