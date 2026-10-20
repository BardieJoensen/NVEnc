#!/usr/bin/env python3
"""Read-only R17 interface/schema preflight; never loads native.so or runs q4."""
import hashlib, importlib.util, inspect, json
from pathlib import Path
ROOT=Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020')
def ident(p):
 p=Path(p).resolve(); return {'path':str(p),'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest(),'size':p.stat().st_size}
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
adp=ROOT/'parent/psyex-tf0-r16-refine/r16-refine-tbr10042-observations/admitted/admission.json'; ad=json.loads(adp.read_text()); binding=json.loads(Path(ad['artifacts']['syntax_binding']['path']).read_text())
p=load(ROOT/'parent/psyex-real-r15/parsers.py','p'); tokens,terminal=p.parse_coeff(Path(ad['trace']['path']),int(binding['target_coded_event']['coded_ordinal']))
r12=load(ROOT/'parent/psyex-scalar-r12/experiment.py','r12'); metric=load(ROOT/'parent/psyex-coeff-r11/analyze.py','metric'); unit=load(metric.U,'unit')
assert len(tokens)==2870 and sum(bool(t['stages']) for t in tokens.values())==2169 and sum(not t['stages'] for t in tokens.values())==701 and sum(len(t['stages'])==2 for t in tokens.values())==39
assert terminal==ad['terminal']; assert list(inspect.signature(r12.Native.paired).parameters)==['self','t','mode','tables']; assert list(inspect.signature(r12.Native.inverse).parameters)==['self','t','dq','eob','dispatch']; assert list(inspect.signature(metric.descriptor).parameters)==['unit_helper','h','ref','z']; assert ident(Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020/parent/psyex-tf0-r16-refine/r16-refine-tbr10042-observations/syntax-binding/trace_headers.log'))['sha256']=='af82740d0c84a2a55c72aa9f1ba794e630431b3b2729618d5cf9ffd8fc2f5ee8'
res={'status':'pass','scope':'read-only schema/parser/interface preflight; no native library load, no q4 call, no output reconstruction','admission':ident(adp),'counts':{'tokens':len(tokens),'invoked':sum(bool(t['stages']) for t in tokens.values()),'uninvoked':sum(not t['stages'] for t in tokens.values()),'two_stage':sum(len(t['stages'])==2 for t in tokens.values())},'target':binding['target_coded_event'],'checks':['parser terminal','token population','Native.paired signature','Native.inverse signature','descriptor signature','target DC trace log identity'],'script':ident(__file__)}
Path(__file__).with_name('preflight-schema-check.json').write_text(json.dumps(res,indent=2)+'\n'); print(json.dumps(res))
