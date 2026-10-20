#!/usr/bin/env python3
"""Read-only extraction of the bound target AV1 frame-header DC syntax."""
from __future__ import annotations
import hashlib, json, pathlib, re, sys
from datetime import datetime, timezone

if not __debug__:
    raise SystemExit('optimized Python is refused')

ROOT = pathlib.Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020')
BIND = ROOT/'parent/psyex-tf0-r16-refine/r16-refine-tbr10042-observations/syntax-binding'
BRES = BIND/'result.json'
EVENTS = BIND/'events.json'
LOG = BIND/'trace_headers.log'
R12 = ROOT/'parent/psyex-scalar-r12/build-2/receipt.json'
OUT = pathlib.Path(__file__).resolve().parent/'result.json'


def sha(p):
    h=hashlib.sha256(); n=0
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):
            n += len(b); h.update(b)
    return {'path':str(pathlib.Path(p).resolve()),'sha256':h.hexdigest(),'size':n}

def assert_ident(obj, label):
    if not isinstance(obj,dict) or set(('path','sha256','size'))-set(obj):
        raise AssertionError(f'{label}: malformed identity')
    got=sha(obj['path'])
    if got != {k:obj[k] for k in ('path','sha256','size')}:
        raise AssertionError(f'{label}: identity mismatch {got} != {obj}')
    return got

def load_json(p):
    with open(p) as f: return json.load(f)

# Input evidence identities are checked before any extraction.
for p in (BRES, EVENTS, LOG, R12):
    if not p.is_file(): raise AssertionError(f'missing input {p}')
b = load_json(BRES)
e = load_json(EVENTS)
r12 = load_json(R12)
assert_ident(b['trace_log'], 'binding.trace_log')
assert_ident(b['events'], 'binding.events')
assert_ident(b['target_frame_obu'], 'binding.target_frame_obu')
# The container files have no self-identity field; hash them directly.
sha(BRES); sha(EVENTS); sha(LOG)
sha(R12)

# Validate R12 receipt schema and every recorded file identity.  In particular,
# inputs_before/after are lists; they are not receipt identity dictionaries.
if r12.get('status') != 'complete': raise AssertionError('R12 receipt is not complete')
# The receipt stores identity dictionaries for the two manifest JSON files;
# each referenced JSON contains the actual list of tracked identities.
for k in ('inputs_before','inputs_after'):
    assert_ident(r12[k], 'r12.'+k+' receipt identity')
    if not isinstance(load_json(r12[k]['path']), list):
        raise AssertionError(f'R12 {k} referenced payload must be a list')
before = load_json(r12['inputs_before']['path']); after = load_json(r12['inputs_after']['path'])
if before != after: raise AssertionError('R12 input identity lists changed')
for k in ('source_manifest','library','object'):
    assert_ident(r12[k], 'r12.'+k)
if not isinstance(r12['commands'], list): raise AssertionError('R12 commands must be a list')
for i,c in enumerate(r12['commands']):
    if not isinstance(c,dict) or c.get('returncode') != 0: raise AssertionError(f'R12 command {i} failed/schema')
    if 'log' in c: assert_ident(c['log'], f'r12.commands[{i}].log')
for i,x in enumerate(before): assert_ident(x, f'r12.inputs_before payload[{i}]')
for i,x in enumerate(after): assert_ident(x, f'r12.inputs_after payload[{i}]')

E = e['events']
summary_expected={'ivf_packets':336,'display_actions':336,'frame_headers':502,'coded_non_show_existing':336,'show_existing':166,'hidden_coded':166,'shown_coded':170,'packets_with_multiple_frame_headers':84,'max_frame_headers_per_packet':5}
if any(b.get('summary',{}).get(k) != v for k,v in summary_expected.items()): raise AssertionError('binding summary counts mismatch')
if len(e.get('packets',[])) != 336 or len(e.get('displays',[])) != 336: raise AssertionError('packet/display populations mismatch')
if sorted(x.get('packet_index') for x in e['displays']) != list(range(336)): raise AssertionError('display actions do not cover one per packet')
if len(E) != 502: raise AssertionError(f'expected 502 events, got {len(E)}')
if [x.get('event_index') for x in E] != list(range(502)): raise AssertionError('event indices not contiguous 0..501')
# Every event has a self-consistent packet/header position and coded/display identity.
by_packet={}
for x in E:
    req=('packet_index','packet_pts','packet_event_index','header_log_line','obu','show_existing_frame')
    if any(k not in x for k in req): raise AssertionError(f'event missing fields {x.get("event_index")}')
    if x['packet_event_index'] < 0: raise AssertionError('negative packet event index')
    by_packet.setdefault(x['packet_index'],[]).append(x)
    o=x['obu']
    if o.get('type') not in (3,6): raise AssertionError('unexpected OBU type')
    if o['packet_end'] <= o['packet_start'] or o['size'] != o['packet_end']-o['packet_start']:
        raise AssertionError(f'bad OBU bounds event {x["event_index"]}')
    if x['show_existing_frame']:
        if 'resolved_coded_ordinal' not in x: raise AssertionError('show-existing lacks resolution')
    else:
        if 'coded_ordinal' not in x: raise AssertionError('coded event lacks ordinal')
for pi, xs in by_packet.items():
    if [x['packet_event_index'] for x in xs] != list(range(len(xs))): raise AssertionError(f'packet {pi} event positions not contiguous')
    starts=[x['obu']['packet_start'] for x in xs]
    ends=[x['obu']['packet_end'] for x in xs]
    if any(a < b for a,b in zip(starts[1:],ends[:-1])): raise AssertionError(f'packet {pi} OBU overlap/order')
coded=[x for x in E if not x['show_existing_frame']]
show=[x for x in E if x['show_existing_frame']]
if [x['coded_ordinal'] for x in coded] != list(range(336)): raise AssertionError('coded ordinals not 0..335')
if len(show)!=166 or len(coded)!=336: raise AssertionError('coded/show counts mismatch')
hidden=sum(x.get('show_frame')==0 for x in coded); shown=sum(x.get('show_frame')==1 for x in coded)
if (hidden,shown)!=(166,170): raise AssertionError('hidden/shown coded counts mismatch')
if sum(len(v)>1 for v in by_packet.values()) != 84 or max(map(len,by_packet.values())) != 5: raise AssertionError('packet header multiplicity mismatch')

T=next(x for x in E if x['event_index']==314)
expected={'coded_ordinal':210,'packet_index':209,'packet_pts':209,'packet_event_index':1,'frame_type':1,'show_frame':0,'showable_frame':1,'order_hint':88,'refresh_frame_flags_normalized':16}
for k,v in expected.items():
    if T.get(k)!=v: raise AssertionError(f'target {k} {T.get(k)} != {v}')
if T['obu'] != b['target_coded_event']['obu']: raise AssertionError('target OBU binder disagreement')
if T['obu']['sha256'] != b['target_frame_obu']['sha256']: raise AssertionError('target OBU hash disagreement')
packet209=by_packet[209]
if [x['event_index'] for x in packet209] != [313,314,315,316,317]: raise AssertionError('packet209 four-header framing mismatch')
if packet209[1]['event_index'] != 314: raise AssertionError('target is not packet209 second header')

lines=LOG.read_text(errors='replace').splitlines()
def line_text(n): return lines[n-1]
# Binder header_log_line is the first syntax field after Frame Header. Find the
# marker immediately before it and the next marker after it; this is the full
# target frame-header block, without the next frame header.
first=T['header_log_line']
start_zero=first-1
if not lines[start_zero].endswith('Frame Header'): raise AssertionError('target header line is not Frame Header marker')
field_zero=start_zero
while field_zero < len(lines) and 'show_existing_frame' not in lines[field_zero]:
    field_zero += 1
if field_zero >= len(lines): raise AssertionError('target show_existing_frame field absent')
end_zero=start_zero+1
while end_zero < len(lines) and not lines[end_zero].endswith('Frame Header'):
    end_zero += 1
if end_zero >= len(lines): raise AssertionError('next Frame Header marker absent')
if lines[end_zero].endswith('Frame Header') is not True: raise AssertionError('next marker roundtrip failed')
if any(lines[i].endswith('Frame Header') for i in range(start_zero+1,end_zero)): raise AssertionError('interior Frame Header marker')
block=lines[start_zero:end_zero]
delta=[(i,s) for i,s in enumerate(block,start_zero) if 'delta_q_y_dc.delta_coded' in s]
if len(delta)!=1: raise AssertionError(f'target block delta line count {len(delta)}')
delta_zero_based, delta_text=delta[0]
delta_line=delta_zero_based+1
if lines[delta_zero_based] != delta_text or delta_line != delta_zero_based+1: raise AssertionError('delta line index roundtrip failed')
if not re.search(r'delta_q_y_dc\.delta_coded\s+0\s*=\s*0\s*$',delta_text): raise AssertionError('target delta syntax is not 0 = 0')
block_text='\n'.join(block)+'\n'
block_hash=hashlib.sha256(block_text.encode()).hexdigest()
delta_line_zero_based=delta_zero_based

out={
 'status':'admitted', 'scope':'read-only target frame-header DC evidence; no native/build/encode/GPU',
 'inputs': {'binding_result':sha(BRES),'events':sha(EVENTS),'trace_log':sha(LOG),'target_obu':sha(BIND/'target-frame.obu'),'syntax_command':sha(BIND/'command.json'),'r12_build_receipt':sha(R12)},
 'r12_receipt_schema': {'status':r12['status'],'inputs_before_receipt_type':'identity_dict','inputs_after_receipt_type':'identity_dict','referenced_input_payload_type':'list','input_entries':len(before),'inputs_equal':True,'commands_type':'list','identity_locations':['source_manifest','inputs_before[]','inputs_after[]','commands[].log','library','object'],'all_recorded_identities_verified':True},
 'framing': {'events':502,'coded_non_show_existing':336,'show_existing':166,'hidden_coded':hidden,'shown_coded':shown,'ivf_packets':336,'packets_with_multiple_frame_headers':84,'max_frame_headers_per_packet':5,'all_packet_event_indices_contiguous':True,'all_obu_bounds_nonoverlapping_per_packet':True,'coded_ordinals_contiguous':True,'display_actions':336,'all_packets_exactly_one_display_action':True},
 'packet_209': [{'event_index':x['event_index'],'packet_event_index':x['packet_event_index'],'obu':x['obu']} for x in packet209],
 'target': {'event_index':314,'coded_ordinal':210,'packet_index':209,'packet_event_index':1,'frame_header_first_field_log_line':field_zero+1,'frame_header_start_line_1based':start_zero+1,'frame_header_end_exclusive_1based':end_zero+1,'frame_header_included_end_line_1based':end_zero,'frame_header_line_count':len(block),'frame_header_interval_kind':'broad interval from Frame Header marker through immediately before next Frame Header marker (may include Tile Group/next OBU fields)', 'frame_header_block_sha256':block_hash,'header_text_lines':block,'delta_q_y_dc':{'log_line_1based':delta_line,'splitlines_index_zero_based':delta_line_zero_based,'text':delta_text,'delta_coded':0,'effective_delta':0,'semantics':'trace_headers names the AV1 frame-header syntax flag delta_q_y_dc.delta_coded; the traced 0 = 0 means no luma DC delta is signaled, hence frame-level delta 0.'},'obu':T['obu'],'show_existing_consumer':{'event_index':325,'packet_index':216,'resolved_coded_ordinal':210,'header_log_line':b['display_216_event']['header']['header_log_line'] if isinstance(b['display_216_event'].get('header'),dict) else b['display_216_event'].get('header_log_line')}},
 'generated_utc':datetime.now(timezone.utc).isoformat(),
}
OUT.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
print(json.dumps({'output':str(OUT),'events':502,'target_broad_interval_1based':[start_zero+1,end_zero], 'target_broad_interval_end_exclusive_1based':end_zero+1,'delta_log_line_1based':delta_line,'delta_splitlines_index_zero_based':delta_line_zero_based,'output_sha256':sha(OUT)['sha256']},sort_keys=True))
