#!/usr/bin/env python3
"""Exercise gate selection and pushed-ref handling without needing a GPU."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='fgs-gate-test-')
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.env = os.environ.copy()
        for name in list(self.env):
            if name.startswith(('FGS_', 'GIT_')):
                del self.env[name]
        self.env.update(FGS_GATE_CACHE=str(self.root / 'cache'),
                        FGS_GATE_REPORTS=str(self.root / 'reports'))
        self.fake_bin = self.root / 'bin'
        self.fake_bin.mkdir()
        self.env['PATH'] = str(self.fake_bin) + os.pathsep + self.env['PATH']
        for name, body in [('docker', 'exit 0'), ('ffprobe', 'exit 0'),
                           ('ffmpeg', 'echo libdav1d'), ('nvidia-smi', 'echo test-gpu')]:
            self.executable(self.fake_bin / name, '#!/bin/sh\n' + body + '\n')

    def tearDown(self):
        self.tmp.cleanup()

    def executable(self, path, body):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        path.chmod(0o755)
        return path

    def run_command(self, args, **kwargs):
        return subprocess.run(args, cwd=self.repo, env=self.env, text=True,
                              capture_output=True, timeout=30, **kwargs)

    def git(self, *args):
        result = self.run_command(['git', *args])
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_missing_and_ambiguous_candidates_fail_before_preflight(self):
        for args in [[], ['--candidate-commit', 'HEAD', '--reference-control', 'r4050']]:
            result = self.run_command(['bash', str(HERE / 'local_gate.sh'), *args])
            self.assertEqual(result.returncode, 2)
            self.assertIn('select exactly one candidate', result.stderr)
            self.assertNotIn('preflight', result.stdout)

    def test_stage_cannot_ignore_candidate_commit(self):
        result = self.run_command(['bash', str(HERE / 'local_gate.sh'), '--stage', 'kat',
                                   '--candidate-commit', 'this-commit-does-not-exist'])
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('preflight', result.stdout)

    def test_kat_receives_candidate_and_explicit_production_denoiser(self):
        target = self.repo / 'tests/fgs'
        target.mkdir(parents=True)
        shutil.copy2(HERE / 'local_gate.sh', target / 'local_gate.sh')
        (target / 'fgs_kat.py').write_text(
            'import json, os, pathlib\n'
            'pathlib.Path(os.environ["FGS_GATE_REPORTS"], "invocation.json").write_text('
            'json.dumps({k: os.environ[k] for k in ["NVENCC", "FGS_KAT_DENOISER"]}))\n')
        candidate = self.executable(self.root / 'candidate', '#!/bin/sh\necho candidate-version\n')
        result = self.run_command(['bash', str(target / 'local_gate.sh'), '--stage', 'kat',
                                   '--candidate-nvencc', str(candidate)])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = self.root / 'reports'
        call = json.loads((report / 'invocation.json').read_text())
        identity = json.loads((report / 'candidate.json').read_text())
        self.assertEqual(call['NVENCC'], str(candidate))
        self.assertEqual(call['FGS_KAT_DENOISER'], 'bilateral')
        self.assertEqual(identity['denoiser'], 'bilateral')
        self.assertEqual(identity['candidate_sha256'], hashlib.sha256(candidate.read_bytes()).hexdigest())
        self.assertIsNone(identity['reference_control'])

    def prepare_history(self):
        self.git('init', '-q')
        self.git('config', 'user.name', 'FGS gate test')
        self.git('config', 'user.email', 'fgs-test@example.invalid')
        for directory in ['NVEncCore', 'NVEncSDK']:
            (self.repo / directory).mkdir()
            (self.repo / directory / 'fixture').write_text('fixture\n')
        self.executable(self.repo / 'tests/fgs/local_gate.sh',
                        '#!/bin/sh\nprintf "%s\\n" "$*" >> "$FGS_TEST_GPU_CALLS"\n')
        self.executable(self.repo / 'tests/fgs/run_cpu_tests.sh',
                        '#!/bin/sh\necho old >> "$FGS_TEST_CPU_CALLS"\nexit 1\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'failing old candidate')
        old = self.git('rev-parse', 'HEAD')
        self.executable(self.repo / 'tests/fgs/run_cpu_tests.sh',
                        '#!/bin/sh\necho new >> "$FGS_TEST_CPU_CALLS"\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'passing new candidate')
        new = self.git('rev-parse', 'HEAD')
        self.env.update(FGS_TEST_CPU_CALLS=str(self.root / 'cpu-calls'),
                        FGS_TEST_GPU_CALLS=str(self.root / 'gpu-calls'))
        return old, new

    def hook(self, lines):
        return self.run_command(['bash', str(HERE / 'hooks/pre-push')], input=lines)

    def test_non_head_push_tests_the_pushed_source(self):
        old, _ = self.prepare_history()
        self.env['FGS_PREPUSH'] = 'off'
        result = self.hook(f'refs/heads/old {old} refs/heads/old {"0"*40}\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.root / 'cpu-calls').read_text(), 'old\n')

    def test_tag_and_branch_deduplicate_and_pass_pushed_commit_to_gpu(self):
        _, new = self.prepare_history()
        self.git('tag', '-am', 'release', 'release')
        tag = self.git('rev-parse', 'release')
        self.env['FGS_PREPUSH'] = 'full'
        result = self.hook(f'refs/heads/new {new} refs/heads/new {"0"*40}\n'
                           f'refs/tags/release {tag} refs/tags/release {"0"*40}\n')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / 'cpu-calls').read_text(), 'new\n')
        self.assertEqual((self.root / 'gpu-calls').read_text(),
                         f'--full --candidate-commit {new} --denoiser bilateral\n')

    def test_deletion_does_not_test_head(self):
        _, new = self.prepare_history()
        result = self.hook(f'(delete) {"0"*40} refs/heads/old {new}\n')
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.root / 'cpu-calls').exists())


if __name__ == '__main__':
    unittest.main()
