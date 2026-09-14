"""Narrow media-preservation checks for source-based repair exceptions.

These checks do not change the ordinary Tdarr flow or encoder. Expensive
Matroska/SubRip inspection is only needed when the existing fast check differs.
Reviewed cadence is bound to measured, immutable source and library identities.
"""
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def chapter_tree(xml):
    """Compare stored structure, including explicit ends and all display data."""
    def node(element):
        text = element.text or ''
        if len(element) and not text.strip():
            text = ''  # XML indentation, not chapter title whitespace.
        return (element.tag, tuple(sorted(element.attrib.items())), text,
                tuple((node(child), child.tail if (child.tail or '').strip() else '')
                      for child in element))
    root = ET.fromstring(xml)
    if root.tag != 'Chapters':
        raise RuntimeError('chapter extraction did not return a Chapters document')
    return node(root)


def compare_stored_chapters(library, completed, directory):
    documents = []
    for label, path in [('before', library), ('after', completed)]:
        result = subprocess.run(['mkvextract', str(path), 'chapters'], capture_output=True,
                                text=True, check=True, timeout=180)
        xml = result.stdout
        # With no chapters mkvextract returns no XML. Only a matching absence
        # can pass; an extraction error or malformed document still fails.
        tree = chapter_tree(xml) if xml.strip() else None
        output = Path(directory) / (label + '-stored-chapters.xml')
        output.write_text(xml)
        documents.append((tree, file_sha256(output)))
    if documents[0][0] != documents[1][0]:
        raise RuntimeError('stored chapter structure changed')
    return dict(method='stored_matroska_chapters_v1', passed=True,
                before_sha256=documents[0][1], after_sha256=documents[1][1])


def packet_bytes(packet):
    data = bytearray()
    for line in packet['data'].splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r'([0-9a-fA-F]{8}): (.*?)  .*', line)
        if not match or int(match[1], 16) != len(data):
            raise RuntimeError('invalid packet hex dump')
        try:
            data.extend(bytes.fromhex(match[2]))
        except ValueError as error:
            raise RuntimeError('invalid packet payload') from error
    if len(data) != int(packet['size']):
        raise RuntimeError('incomplete packet payload')
    return bytes(data)


def compare_subrip_packets(before, after):
    if not before or len(before) != len(after):
        raise RuntimeError('SubRip cue count differs or is empty')
    changed = 0
    old_hash = hashlib.sha256(); new_hash = hashlib.sha256()
    for old, new in zip(before, after):
        for field in ('pts_time', 'duration_time'):
            a = Decimal(old[field]); b = Decimal(new[field])
            if not a.is_finite() or not b.is_finite() or a != b:
                raise RuntimeError('SubRip cue timing changed')
        a = packet_bytes(old); b = packet_bytes(new)
        old_hash.update(a); new_hash.update(b)
        if a == b:
            continue
        # Do not strip arbitrary whitespace, internal newlines, markup, or
        # repeated terminators. This is the one observed mkvmerge change.
        if not a.endswith(b'\r\n') or b != a[:-2]:
            raise RuntimeError('SubRip cue text or formatting changed')
        changed += 1
    return dict(method='subrip_single_terminal_crlf_v1', passed=True, cues=len(before),
                changed_cues=changed, removed_bytes=2*changed,
                before_payload_sha256=old_hash.hexdigest(), after_payload_sha256=new_hash.hexdigest())


def read_subrip_packets(path, index, evidence):
    result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', str(index),
                             '-show_packets', '-show_data', '-show_entries',
                             'packet=pts_time,duration_time,size,data', '-of', 'json', str(path)],
                            capture_output=True, text=True, check=True, timeout=3600)
    Path(evidence).write_text(result.stdout)
    return json.loads(result.stdout)['packets']


def compare_nonvideo_payloads(library, completed, before, after, old_hashes, new_hashes, directory):
    def mapped(info):
        # Match the worker's -map 0:a? -map 0:s? streamhash order.
        return [s for kind in ('audio', 'subtitle') for s in info['streams'] if s['codec_type'] == kind]
    old_streams = mapped(before); new_streams = mapped(after)
    if not len(old_streams) == len(new_streams) == len(old_hashes) == len(new_hashes):
        raise RuntimeError('nonvideo stream hash coverage differs')
    results = []
    for old, new, a, b in zip(old_streams, new_streams, old_hashes, new_hashes):
        if (old['codec_type'], old['codec_name']) != (new['codec_type'], new['codec_name']):
            raise RuntimeError('nonvideo stream codec changed')
        if a == b:
            continue
        if old['codec_type'] != 'subtitle' or old['codec_name'] != 'subrip':
            raise RuntimeError('audio or non-SubRip subtitle payload changed')
        packets = []
        for label, path, stream in [('before', library, old), ('after', completed, new)]:
            packets.append(read_subrip_packets(path, stream['index'], Path(directory) /
                           f'{label}-subrip-{old["index"]}-packets.json'))
        result = compare_subrip_packets(*packets)
        if (a != 's,SHA256=' + result['before_payload_sha256'] or
                b != 's,SHA256=' + result['after_payload_sha256']):
            raise RuntimeError('SubRip packet evidence does not match stream hashes')
        results.append(dict(stream_index=old['index'], **result))
    return dict(method='exact_hashes_with_subrip_terminal_crlf_v1', passed=True, exceptions=results)


def reviewed_policy(item, config):
    path = config.get('reviewed_media_policy')
    if not path:
        return None
    if file_sha256(path) != config.get('reviewed_media_policy_sha256'):
        raise RuntimeError('reviewed media policy changed')
    data = json.loads(Path(path).read_text())
    if data.get('version') != 1:
        raise RuntimeError('unsupported reviewed media policy')
    entry = data['files'].get(item['path'])
    if entry is None:
        return None
    for field in ('source', 'source_signature', 'library_signature'):
        if entry[field] != item[field]:
            raise RuntimeError('reviewed media identity changed: ' + field)
    for field in ('clock_evidence', 'clock_error_log', 'field_evidence'):
        if field in entry and file_sha256(entry[field]) != entry[field + '_sha256']:
            raise RuntimeError('reviewed source evidence changed')
    if entry.get('clock_error_log') and Path(entry['clock_error_log']).read_text().strip():
        raise RuntimeError('reviewed source clock decode reported errors')
    clock = json.loads(Path(entry['clock_evidence']).read_text())
    n = clock.get('count', 0)
    if (entry.get('fps') != 25 or entry.get('policy') != 'decoded_25fps_progressive_v1'
            or clock.get('source_signature') != item['source_signature']
            or clock.get('path') != item['source'] or not clock.get('complete')
            or not clock.get('regular_25fps') or n < 1000 or clock.get('anomalies')
            or clock.get('intervals_us') != {'40000': n-1}
            or clock.get('repeat_pict') != {'0': n}
            or clock.get('last_us') != clock.get('first_us') + (n-1)*40000):
        raise RuntimeError('reviewed source clock is not a complete 25 fps sequence')
    if entry.get('reviewed_field_passages'):
        evidence = json.loads(Path(entry['field_evidence']).read_text())
        samples = evidence['samples']
        fractions = {s['fraction'] for s in samples}
        if (evidence.get('source_signature') != item['source_signature']
                or evidence.get('path') != item['source'] or len(samples) < 8
                or len(fractions) < 8 or not all(0 < f < 1 for f in fractions)
                or max(fractions)-min(fractions) < .75
                or any(s['total'] != sum(s[k] for k in ('tff', 'bff', 'progressive', 'undetermined'))
                       or any(s[k] < 0 for k in ('tff', 'bff', 'progressive', 'undetermined')) for s in samples)
                or any(s['total'] < 300 or s['tff']+s['bff'] > .02*s['total'] for s in samples)
                or sum(s['progressive'] >= .6*s['total'] for s in samples) < 6):
            raise RuntimeError('expanded source field review is insufficient')
    return dict(entry, clock=clock)


def compare_reviewed_clock(timestamps, clock):
    """Require every encoded picture at the measured source's original clock."""
    count = 0
    for value in timestamps:
        timestamp = Decimal(value)
        if not timestamp.is_finite():
            raise RuntimeError('encoded picture has a nonfinite timestamp')
        expected = clock['first_us'] + count * 40000
        if abs(timestamp * 1000000 - expected) > 1000:
            raise RuntimeError('encoded picture timestamp differs from reviewed source clock')
        count += 1
    if count != clock['count']:
        raise RuntimeError('encoded picture count differs from reviewed source')
    return dict(method='complete_reviewed_source_clock_v1', passed=True, frames=count, fps=25)


def validate_reviewed_output(encoded, policy, directory, phase='encoded'):
    command = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_packets',
               '-show_entries', 'packet=pts_time', '-of', 'csv=p=0', str(encoded)]
    # AV1 packet order is display order in these native-cadence NVEncC MKVs.
    # Missing or non-picture packets must not be silently filtered out.
    result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=3600)
    path = Path(directory) / (phase + '-reviewed-timestamps.csv')
    path.write_text(result.stdout)
    verdict = compare_reviewed_clock(result.stdout.splitlines(), policy['clock'])
    return dict(verdict, timestamps_sha256=file_sha256(path), source_evidence=policy['clock_evidence'],
                source_evidence_sha256=policy['clock_evidence_sha256'])
