import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

spec = importlib.util.spec_from_file_location('guard', Path(__file__).parents[2] /
                                               'tools/fgs/repair_media_guard.py')
guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)


def packet(payload, pts='1.000000', duration='2.000000'):
    lines = []
    for offset in range(0, len(payload), 16):
        part = payload[offset:offset+16]
        groups = ' '.join(part[i:i+2].hex() for i in range(0, len(part), 2))
        lines.append(f'{offset:08x}: {groups:39}  ignored ASCII')
    return dict(pts_time=pts, duration_time=duration, size=str(len(payload)), data='\n'.join(lines))


class SubtitleChecks(unittest.TestCase):
    def test_identical_payloads_and_one_removed_terminal_crlf(self):
        text = b'  <i>Hello</i>\r\n    next line  \r\n'
        result = guard.compare_subrip_packets([packet(text), packet(b'same')],
                                             [packet(text[:-2]), packet(b'same')])
        self.assertEqual(result['changed_cues'], 1)
        self.assertEqual(result['removed_bytes'], 2)

    def test_text_formatting_and_internal_newlines_are_required(self):
        text = b'  <i>Hello</i>\r\n    next line  \r\n'
        for changed in (text.lstrip(), text.replace(b'\r\n', b'\n'), text[:-4],
                        text.replace(b'<i>', b''), text + b'\r\n'):
            with self.subTest(changed=changed), self.assertRaisesRegex(RuntimeError, 'formatting'):
                guard.compare_subrip_packets([packet(text)], [packet(changed)])
        with self.assertRaisesRegex(RuntimeError, 'formatting'):
            guard.compare_subrip_packets([packet(b'hi\r\n\r\n')], [packet(b'hi')])

    def test_timing_count_and_order_cannot_change(self):
        old = [packet(b'hello\r\n'), packet(b'next\r\n', pts='5')]
        for new in (old[:1], old[::-1], [packet(b'hello', pts='1.001'), old[1]],
                    [packet(b'hello', duration='1.999'), old[1]],
                    [packet(b'hello', pts='NaN'), old[1]]):
            with self.subTest(new=new), self.assertRaises(RuntimeError):
                guard.compare_subrip_packets(old, new)

    def test_incomplete_packet_evidence_is_rejected(self):
        p = packet(b'abcdefghijk\r\n'); p['size'] = '99'
        with self.assertRaisesRegex(RuntimeError, 'incomplete'):
            guard.packet_bytes(p)
        p = packet(b'hello'); p['data'] = p['data'].replace('00000000', '00000001')
        with self.assertRaisesRegex(RuntimeError, 'hex dump'):
            guard.packet_bytes(p)

    def test_audio_and_other_subtitle_changes_cannot_use_exception(self):
        for kind, codec in [('audio', 'opus'), ('subtitle', 'ass'), ('subtitle', 'hdmv_pgs_subtitle')]:
            info = {'streams': [{'index': 0, 'codec_type': kind, 'codec_name': codec}]}
            with self.subTest(codec=codec), self.assertRaisesRegex(RuntimeError, 'payload changed'):
                guard.compare_nonvideo_payloads('a', 'b', info, info, ['old'], ['new'], '.')

    def test_packet_evidence_must_match_independent_stream_hashes(self):
        info = {'streams': [{'index': 0, 'codec_type': 'subtitle', 'codec_name': 'subrip'}]}
        with mock.patch.object(guard, 'read_subrip_packets', side_effect=[
                [packet(b'hi\r\n')], [packet(b'hi')]]), self.assertRaisesRegex(RuntimeError, 'stream hashes'):
            guard.compare_nonvideo_payloads('a', 'b', info, info, ['s,SHA256=wrong'], ['s,SHA256=other'], '.')


class Chapters(unittest.TestCase):
    XML = ('<Chapters><EditionEntry><EditionUID>1</EditionUID><ChapterAtom>'
           '<ChapterUID>2</ChapterUID><ChapterTimeStart>00:00:01.000000000</ChapterTimeStart>'
           '<ChapterDisplay><ChapterString> Title </ChapterString><ChapterLanguage>eng</ChapterLanguage>'
           '</ChapterDisplay></ChapterAtom></EditionEntry></Chapters>')

    def test_formatting_does_not_change_stored_chapter_structure(self):
        self.assertEqual(guard.chapter_tree(self.XML), guard.chapter_tree(self.XML.replace('><', '>\n  <')))

    def test_explicit_ends_titles_language_and_order_are_not_discarded(self):
        old = guard.chapter_tree(self.XML)
        for changed in (self.XML.replace(' Title ', 'Title'), self.XML.replace('eng', 'dan'),
                        self.XML.replace('</ChapterAtom>', '<ChapterTimeEnd>00:00:05</ChapterTimeEnd></ChapterAtom>'),
                        self.XML.replace('00:00:01.000000000', '00:00:01.001000000'),
                        self.XML.replace('<ChapterUID>2</ChapterUID>', '<ChapterUID>3</ChapterUID>')):
            with self.subTest(changed=changed):
                self.assertNotEqual(old, guard.chapter_tree(changed))

    def test_unrelated_xml_is_not_a_chapter_document(self):
        with self.assertRaisesRegex(RuntimeError, 'Chapters document'):
            guard.chapter_tree('<other/>')

    def test_empty_extraction_cannot_clear_a_chapter_mismatch(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(guard.subprocess, 'run') as run:
            run.return_value.stdout = ''
            with self.assertRaisesRegex(RuntimeError, 'missing stored chapter evidence'):
                guard.compare_stored_chapters('before', 'after', folder)


class Cadence(unittest.TestCase):
    def test_requires_every_picture_on_the_original_clock(self):
        clock = dict(count=4, first_us=46000)
        times = ['.046', '.086', '.126', '.166']
        self.assertTrue(guard.compare_reviewed_clock(times, clock)['passed'])
        for wrong in (times[:-1], times+[times[-1]], ['.046', '.086', '.086', '.166'],
                      ['.046', '.086', '.166', '.206'], ['.046', '.0871', '.126', '.166'],
                      ['NaN']+times[1:]):
            with self.subTest(wrong=wrong), self.assertRaises(RuntimeError):
                guard.compare_reviewed_clock(wrong, clock)

    def test_review_is_pinned_to_the_measured_files_and_evidence(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); clockpath = root/'clock.json'; policypath = root/'policy.json'
            signature = dict(device=1, inode=2, size=100, mtime_ns=3)
            item = dict(path='library', source='original', source_signature=signature,
                        library_signature=dict(signature, inode=4))
            clock = dict(path='original', source_signature=signature, complete=True, regular_25fps=True,
                         count=1001, first_us=0, last_us=40000000, intervals_us={'40000':1000},
                         repeat_pict={'0':1001}, anomalies=[])
            clockpath.write_text(json.dumps(clock))
            errorpath = root/'errors.log'; errorpath.write_text('')
            entry = dict(item, fps=25, policy='decoded_25fps_progressive_v1',
                         clock_evidence=str(clockpath), clock_evidence_sha256=guard.file_sha256(clockpath),
                         clock_error_log=str(errorpath), clock_error_log_sha256=guard.file_sha256(errorpath))
            policypath.write_text(json.dumps(dict(version=1, files={'library':entry})))
            config = dict(reviewed_media_policy=str(policypath),
                          reviewed_media_policy_sha256=guard.file_sha256(policypath))
            self.assertEqual(guard.reviewed_policy(item, config)['clock']['count'], 1001)
            self.assertIsNone(guard.reviewed_policy(dict(item, path='unreviewed'), config))
            for key in ('source', 'source_signature', 'library_signature'):
                changed = copy.deepcopy(item); changed[key] = 'changed'
                with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'identity changed'):
                    guard.reviewed_policy(changed, config)
            clockpath.write_text(json.dumps(dict(clock, count=1000)))
            with self.assertRaisesRegex(RuntimeError, 'evidence changed'):
                guard.reviewed_policy(item, config)
            policypath.write_text('{}')
            with self.assertRaisesRegex(RuntimeError, 'policy changed'):
                guard.reviewed_policy(item, config)

    def test_expanded_fields_need_separate_progressive_passages_without_woven_motion(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); clockpath = root/'clock.json'; fieldpath = root/'fields.json'; policypath = root/'policy.json'
            errorpath = root/'errors.log'; errorpath.write_text('')
            item = dict(path='library', source='original', source_signature={'inode':1}, library_signature={'inode':2})
            clockpath.write_text(json.dumps(dict(path='original', source_signature=item['source_signature'],
                complete=True, regular_25fps=True, count=1001, first_us=0, last_us=40000000,
                intervals_us={'40000':1000}, repeat_pict={'0':1001}, anomalies=[])))
            samples = [dict(fraction=f, tff=0, bff=0, progressive=300, undetermined=0, total=300)
                       for f in (.05,.11,.17,.29,.41,.53,.61,.73,.83,.91)]
            samples[2].update(progressive=100, undetermined=200)  # Inconclusive, not woven.
            def check(rows):
                fieldpath.write_text(json.dumps(dict(path='original', source_signature=item['source_signature'], samples=rows)))
                entry = dict(item, fps=25, policy='decoded_25fps_progressive_v1', reviewed_field_passages=True,
                             clock_evidence=str(clockpath), clock_evidence_sha256=guard.file_sha256(clockpath),
                             clock_error_log=str(errorpath), clock_error_log_sha256=guard.file_sha256(errorpath),
                             field_evidence=str(fieldpath), field_evidence_sha256=guard.file_sha256(fieldpath))
                policypath.write_text(json.dumps(dict(version=1, files={'library':entry})))
                return guard.reviewed_policy(item, dict(reviewed_media_policy=str(policypath),
                                             reviewed_media_policy_sha256=guard.file_sha256(policypath)))
            self.assertIsNotNone(check(samples))
            woven = copy.deepcopy(samples); woven[2].update(tff=20, undetermined=180)
            ambiguous = copy.deepcopy(samples)
            for s in ambiguous[:6]: s.update(progressive=100, undetermined=200)
            for rows in (woven, ambiguous, samples[:5], [samples[0]]*10):
                with self.subTest(rows=rows), self.assertRaisesRegex(RuntimeError, 'field review'):
                    check(rows)


if __name__ == '__main__':
    unittest.main()
