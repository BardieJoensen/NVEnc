import importlib.util
from pathlib import Path
import threading
import unittest

spec = importlib.util.spec_from_file_location('parallel_audit', Path(__file__).parents[2]/'tools/fgs/parallel_library_audit.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ResourcePause(RuntimeError):
    pass


def item(key):
    return dict(key=key, version='v1', path=key)


class ParallelAudit(unittest.TestCase):
    def run_audit(self, items, measure, *, workers=2, stop=None, header_for=lambda i: i['key']):
        updates = []
        stop = stop or threading.Event()

        def publish(results, pending, active, paused):
            updates.append(dict(results=list(results), pending=list(pending), active=len(active), paused=paused))

        code = m.run_queue(items, workers, header_for, measure, publish,
                           ResourcePause, lambda: True, stop)
        return code, updates[-1]

    def test_parallel_execution_is_bounded_and_each_file_runs_once(self):
        barrier = threading.Barrier(2)
        lock = threading.Lock()
        seen = []

        def measure(i, _):
            with lock:
                seen.append(i['key'])
            barrier.wait(timeout=3)
            return dict(i, status='measured')

        code, state = self.run_audit([item(str(n)) for n in range(4)], measure)
        self.assertEqual(code, 0)
        self.assertCountEqual(seen, ['0','1','2','3'])
        self.assertEqual(len(state['results']), 4)
        self.assertFalse(state['pending'])
        self.assertEqual(state['active'], 0)

    def test_storage_failure_keeps_unmeasured_files_pending(self):
        def measure(i, _):
            raise ResourcePause('low space')
        code, state = self.run_audit([item('a'), item('b'), item('c')], measure)
        self.assertEqual(code, 75)
        self.assertFalse(state['results'])
        self.assertCountEqual([i['key'] for i in state['pending']], ['a','b','c'])
        self.assertEqual(state['paused'], 'low space')

    def test_worker_error_is_not_a_media_failure(self):
        def measure(i, _):
            raise RuntimeError('scheduler control failure')
        code, state = self.run_audit([item('a')], measure)
        self.assertEqual(code, 75)
        self.assertFalse(state['results'])
        self.assertEqual(len(state['pending']), 1)

    def test_wrong_result_identity_is_rejected(self):
        code, state = self.run_audit([item('a')], lambda *_:dict(item('b'),status='measured'))
        self.assertEqual(code, 75)
        self.assertFalse(state['results'])
        self.assertEqual(state['pending'][0]['key'], 'a')

    def test_stop_finishes_active_file_and_preserves_remaining_work(self):
        stop = threading.Event()
        def measure(i, _):
            stop.set()
            return dict(i, status='measured')
        code, state = self.run_audit([item('a'),item('b')], measure, workers=1, stop=stop)
        self.assertEqual(code, 75)
        self.assertEqual([i['key'] for i in state['results']], ['a'])
        self.assertEqual([i['key'] for i in state['pending']], ['b'])

    def test_finished_headers_leave_explicit_missing_coverage(self):
        code, state = self.run_audit([item('a')], lambda *_:self.fail('no header'), header_for=lambda _:None)
        self.assertEqual(code, 0)
        self.assertEqual(state['results'][0]['status'], 'header_missing')

    def test_deadline_priority_preserves_file_provenance(self):
        rows = [dict(item('a'),installed_at=20), dict(item('b'),installed_at=10),item('c')]
        before = [dict(i) for i in rows]
        ordered = m.ordered_items(rows, {'b':1,'a':2}, {('c','v1')})
        self.assertEqual([i['key'] for i in ordered], ['c','b','a'])
        self.assertEqual(rows, before)

    def test_duplicate_file_versions_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            m.ordered_items([item('a'),item('a')], {}, set())
        with self.assertRaisesRegex(ValueError, 'multiple versions'):
            m.ordered_items([item('a'),dict(item('a'),version='v2')], {}, set())


if __name__ == '__main__':
    unittest.main()
