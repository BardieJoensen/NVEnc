import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/fgs'))
from fel_process import supervise


class ProcessTests(unittest.TestCase):
    def run_case(self, producer, consumer, timeout=2):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            fifo = directory / 'input.y4m.fifo'; os.mkfifo(fifo)
            commands = [[sys.executable, '-c', body, str(fifo)] for body in [producer, consumer]]
            stopped = []
            try:
                result = supervise(commands, directory, timeout,
                    stop_external=lambda: stopped.append(True), interval=.01)
                return result
            finally:
                self.assertEqual(stopped, [True])
                record = json.loads((directory / 'pipeline.json').read_text())
                self.assertTrue(all(c is not None for c in record['final_returncodes']))

    def test_both_sides_and_payload_must_complete(self):
        result = self.run_case("import sys; open(sys.argv[1],'wb').write(b'complete picture')",
            "import sys; assert open(sys.argv[1],'rb').read()==b'complete picture'")
        self.assertTrue(result['passed'])

    def test_producer_failure_survives_successful_consumer(self):
        with self.assertRaisesRegex(RuntimeError, 'process failed'):
            self.run_case("import sys; open(sys.argv[1],'wb').write(b'partial'); sys.exit(7)",
                          "import sys; open(sys.argv[1],'rb').read()")

    def test_consumer_failure_reaps_blocked_producer(self):
        with self.assertRaisesRegex(RuntimeError, 'process failed'):
            self.run_case("import sys; open(sys.argv[1],'wb').write(b'never read')",
                          "import sys; sys.exit(8)")

    def test_timeout_reaps_both_sides(self):
        with self.assertRaises(TimeoutError):
            self.run_case("import time; time.sleep(60)", "import time; time.sleep(60)", .05)

    def test_resource_failure_never_starts_a_job(self):
        with tempfile.TemporaryDirectory() as temp:
            def no_space(): raise RuntimeError('scratch reserve')
            with self.assertRaisesRegex(RuntimeError, 'scratch reserve'):
                supervise([[sys.executable, '-c', 'raise Exception()']] * 2, temp,
                          1, check_resources=no_space)
            record = json.loads((Path(temp) / 'pipeline.json').read_text())
            self.assertFalse(record['passed'])
            self.assertEqual(record['final_returncodes'], [])


if __name__ == '__main__': unittest.main()
