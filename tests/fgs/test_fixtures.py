#!/usr/bin/env python3
"""Missing or changed private media must invalidate the gate."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from fixtures import verify


class FixtureTests(unittest.TestCase):
    def test_only_the_pinned_bytes_are_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / 'fixture.mkv'
            payload = b'original fixture'
            manifest = {'artifacts': {'clip': {
                'file': fixture.name, 'sha256': hashlib.sha256(payload).hexdigest()}}}
            with self.assertRaisesRegex(ValueError, 'missing pinned fixture'):
                verify(root, manifest, ['clip'])
            fixture.write_bytes(payload)
            self.assertEqual(verify(root, manifest, ['clip'])['clip']['path'], str(fixture))
            fixture.write_bytes(b'changed fixture')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                verify(root, manifest, ['clip'])
            with self.assertRaisesRegex(ValueError, 'unknown fixture'):
                verify(root, manifest, ['typo'])


if __name__ == '__main__':
    unittest.main()
