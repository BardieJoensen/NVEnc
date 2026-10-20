#!/usr/bin/env python3
"""Structural fault checks; explicit distinction from full provenance admission."""
import importlib.util,json,pathlib,copy,sys,hashlib
P=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r10_validator',P/'validate.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
base=P/'runs/on-1';out=P/'faultchecks-1';out.mkdir(exist_ok=False)
rows=[json.loads(l) for l in (base/'trace.jsonl').read_text().splitlines()]; results=[]
def case(name,change):
 d=out/name;d.mkdir();x=copy.deepcopy(rows);change(x)
 (d/'trace.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in x));(d/'payload.bin').symlink_to(base/'payload.bin')
 try:v.parse(d)
 except (AssertionError,KeyError,ValueError) as e:results.append(dict(name=name,rejected=True,error=str(e)[:500],trace=v.ident(d/'trace.jsonl')))
 else:raise AssertionError('failed to reject '+name)
def first(x,k):return next(r for r in x if r['kind']==k)
case('missing_footer',lambda x:x.pop())
case('bad_event_order',lambda x:first(x,'event').update(event=8))
case('bad_payload_offset',lambda x:first(x,'event').update(bytes_offset=1))
case('missing_owner',lambda x:x.remove(first(x,'leaf')))
case('bad_tu_geometry',lambda x:first(x,'tu').update(w=1000))
case('bad_tu_identity',lambda x:first(x,'after').update(tu=999999))
case('extra_terminal_bytes',lambda x:x[-1].update(payload_bytes=x[-1]['payload_bytes']+1))
case('bad_qindex',lambda x:first(x,'leaf').update(coded_qindex=256))
case('bad_eob_extent',lambda x:next(r for r in x if r['kind']=='tu' and r['eob']>0).update(eob=99999))
# Hash/source binding is tested by the full validator; structural parser alone
# intentionally cannot detect a plausible pixel that violates R9 identity.
r={'status':'passed','scope':'Structural parse rejection only, not a replacement for full command/build/OBU/R9 admission','cases':results,'script':v.ident(__file__),'validator':v.ident(P/'validate.py'),'nominal_trace':v.ident(base/'trace.jsonl'),'nominal_payload':v.ident(base/'payload.bin'),'python':v.ident(sys.executable)}
(out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
