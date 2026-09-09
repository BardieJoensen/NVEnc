#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/fgs'))
from prepare_tdarr_plugin_update import prepare
from install_tdarr_plugin_update import apply


class PluginUpdateTests(unittest.TestCase):
    def test_update_preserves_unrelated_archive_entries_and_exact_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle, plugins = root / 'bundle', root / 'installed'
            files = {'FlowPlugins/local/existing.js': b'new existing plugin',
                     'FlowPlugins/local/new.js': b'new plugin'}
            for name, raw in files.items():
                p = bundle / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(raw)
            (bundle / 'bundle.json').write_text(json.dumps({'files': {n: hashlib.sha256(b).hexdigest() for n, b in files.items()}}))
            old = plugins / 'FlowPlugins/local/existing.js'
            old.parent.mkdir(parents=True)
            old.write_bytes(b'previous plugin')
            archive = root / 'original.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('./FlowPlugins/local/existing.js', b'previous plugin')
                z.writestr('Community/independent.js', b'unrelated bytes')
            before = archive.read_bytes()
            report = prepare(bundle, plugins, archive, root / 'staged')
            self.assertEqual(archive.read_bytes(), before)
            self.assertEqual((root / 'staged/rollback-nodePlugins.Zip').read_bytes(), before)
            self.assertEqual((root / 'staged/rollback-plugins/FlowPlugins/local/existing.js').read_bytes(), b'previous plugin')
            self.assertIsNone(report['files']['FlowPlugins/local/new.js']['before_sha256'])
            with zipfile.ZipFile(root / 'staged/candidate-nodePlugins.Zip') as z:
                self.assertEqual(z.read('Community/independent.js'), b'unrelated bytes')
                self.assertEqual(z.read('./FlowPlugins/local/existing.js'), files['FlowPlugins/local/existing.js'])
                self.assertEqual(z.read('FlowPlugins/local/new.js'), files['FlowPlugins/local/new.js'])
            self.assertEqual(old.read_bytes(), b'previous plugin')
            self.assertTrue(apply(root / 'staged')['complete'])
            self.assertEqual(old.read_bytes(), files['FlowPlugins/local/existing.js'])
            self.assertEqual((plugins / 'FlowPlugins/local/new.js').read_bytes(), files['FlowPlugins/local/new.js'])
            self.assertTrue(apply(root / 'staged')['complete'])
            (plugins / 'FlowPlugins/local/new.js').write_bytes(b'unrelated later edit')
            with self.assertRaisesRegex(ValueError, 'changed outside'):
                apply(root / 'staged', rollback=True)
            (plugins / 'FlowPlugins/local/new.js').write_bytes(files['FlowPlugins/local/new.js'])
            self.assertTrue(apply(root / 'staged', rollback=True)['complete'])
            self.assertEqual(old.read_bytes(), b'previous plugin')
            self.assertFalse((plugins / 'FlowPlugins/local/new.js').exists())
            self.assertEqual(archive.read_bytes(), before)
            with self.assertRaises(FileExistsError):
                prepare(bundle, plugins, archive, root / 'staged')
            (bundle / 'FlowPlugins/local/new.js').write_bytes(b'changed after qualification')
            with self.assertRaisesRegex(ValueError, 'plugin changed'):
                prepare(bundle, plugins, archive, root / 'changed')


if __name__ == '__main__':
    unittest.main()
