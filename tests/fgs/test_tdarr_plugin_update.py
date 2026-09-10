#!/usr/bin/env python3
import hashlib
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
import warnings

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/fgs'))
from prepare_tdarr_plugin_update import prepare
from install_tdarr_plugin_update import apply, archives_equivalent


class Utf8ZipInfo(zipfile.ZipInfo):
    def _encodeFilenameFlags(self):
        # Reproduce Tdarr's UTF-8 flag even for ASCII member names.
        return self.filename.encode('utf-8'), self.flag_bits | 0x800


def repack(source, target, change=None):
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(target, 'w') as new:
        new.comment = b'regenerated archive'
        for original in old.infolist():
            info = Utf8ZipInfo(original.filename, (2020, 1, 1, 0, 0, 0))
            for key in ['external_attr', 'create_system', 'compress_type']:
                setattr(info, key, getattr(original, key))
            raw = old.read(original)
            if change == 'content':
                raw = bytes([raw[0] ^ 1]) + raw[1:]
            elif change == 'permission':
                info.external_attr ^= 0o100 << 16
            elif change == 'name':
                info.filename += '.changed'
            new.writestr(info, raw)
            if change == 'duplicate':
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', UserWarning)
                    new.writestr(copy.copy(info), raw)


class PluginUpdateTests(unittest.TestCase):
    def test_verified_tdarr_repack_can_roll_back_to_the_exact_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            name = 'FlowPlugins/local/existing.js'
            bundle, plugins, archive = root / 'bundle', root / 'installed', root / 'plugins.zip'
            for base, raw in [(bundle, b'new plugin'), (plugins, b'old plugin')]:
                (base / name).parent.mkdir(parents=True)
                (base / name).write_bytes(raw)
            (bundle / 'bundle.json').write_text(json.dumps({'files': {name: hashlib.sha256(b'new plugin').hexdigest()}}))
            with zipfile.ZipFile(archive, 'w') as z:
                z.write(plugins / name, name)
            before = archive.read_bytes()
            prepare(bundle, plugins, archive, root / 'staged')
            apply(root / 'staged')
            replacement = root / 'repacked.zip'
            repack(archive, replacement)
            self.assertNotEqual(archive.read_bytes(), replacement.read_bytes())
            self.assertTrue(archives_equivalent(replacement, archive))
            replacement.replace(archive)
            result = apply(root / 'staged', rollback=True)
            self.assertTrue(result['equivalent_repack_verified'])
            self.assertEqual(archive.read_bytes(), before)
            self.assertEqual((plugins / name).read_bytes(), b'old plugin')

    def test_repack_check_rejects_changed_members_modes_and_duplicates(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / 'original.zip'
            with zipfile.ZipFile(original, 'w') as z:
                info = zipfile.ZipInfo('FlowPlugins/local/example.js')
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                z.writestr(info, b'original plugin')
            for change in ['content', 'permission', 'name', 'duplicate']:
                with self.subTest(change=change):
                    candidate = root / (change + '.zip')
                    repack(original, candidate, change)
                    self.assertFalse(archives_equivalent(candidate, original))
            bad = root / 'bad.zip'
            bad.write_bytes(b'not a ZIP')
            self.assertFalse(archives_equivalent(bad, original))

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
