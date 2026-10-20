#!/usr/bin/env python3
"""Parameterize only event bindings in admitted R10/R11 structural parsers."""
import ast, hashlib, importlib.util, json
from pathlib import Path
import numpy as np

P=Path(__file__).resolve().parent
ROOT=P.parents[1]
R11=ROOT/'parent/psyex-coeff-r11'
R10=ROOT/'parent/aom-decoder-r10-v2'

def ident(p):
    p=Path(p).resolve()
    with p.open('rb') as f: h=hashlib.file_digest(f,'sha256').hexdigest()
    return dict(path=str(p),sha256=h,size=p.stat().st_size)

def load(p,name):
    s=importlib.util.spec_from_file_location(name,p)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def functions(p,names):
    text=p.read_text();nodes={n.name:n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
    return '\n\n'.join(ast.get_source_segment(text,nodes[n]) for n in names)+'\n'

def replace_once(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b)

def equal(a,b):
    if isinstance(a,np.ndarray):
        assert isinstance(b,np.ndarray) and a.dtype==b.dtype and a.shape==b.shape and np.array_equal(a,b)
    elif isinstance(a,dict):
        assert a.keys()==b.keys()
        for k in a:equal(a[k],b[k])
    elif isinstance(a,(tuple,list)):
        assert type(a)==type(b) and len(a)==len(b)
        for x,y in zip(a,b):equal(x,y)
    else: assert a==b

def main():
    old11=R11/'validate.py';old10=R10/'validate.py'
    assert ident(old11)['sha256']=='258db37595666efa153d6fc526d42de371fe0a7f0b21bff7c3334e84238378f3'
    d_ad=R10/'admitted-1/admission.json'
    assert ident(d_ad)['sha256']=='4848fa5164df8ffbca7a2204de8f2df03982aed251fc7d2737709d5019e8de79'
    assert ident(old10)==json.loads(d_ad.read_text())['script']
    pins=[ident(old11),ident(old10)]
    a=functions(old11,['strict_json','decoder_layout','records','inter','stage_contract','parse'])
    a=replace_once(a,'def parse(path):','def parse_coeff(path, expected_decode_order):')
    a=replace_once(a,"m['decode_order']==210","m['decode_order']==expected_decode_order")
    b=functions(old10,['parse'])
    b=replace_once(b,'def parse(run):','def parse_decoder(run, expected_event, expected_coded, expected_events, expected_coded_count):')
    b=replace_once(b,'target_event=314,target_coded=210','target_event=expected_event,target_coded=expected_coded')
    assert b.count('len(events)==314')==3
    b=b.replace('len(events)==314','len(events)==expected_event')
    b=replace_once(b,'len(events)==315','len(events)==expected_event+1')
    b=replace_once(b,"len(events)==rows[-1]['events']==502 and rows[-1]['coded']==336","len(events)==rows[-1]['events']==expected_events and rows[-1]['coded']==expected_coded_count")
    target=P/'parsers.py';assert not target.exists()
    target.write_text('''#!/usr/bin/env python3
"""R15 structural parsers; only independently supplied event identities vary."""
import json,struct,math,hashlib
import numpy as np
W,H=1920,1080
FRAME=W*H*3
ROIS=((1200,650,200,100),(950,50,250,180),(160,600,500,480))
'''+a+'\n'+b)
    trace=R11/'runs/on-1/coeff.bin'
    # Locate the exact admitted trace rather than assuming a replay directory name.
    ad=json.loads((R11/'admitted-1/admission.json').read_text());trace=Path(ad['trace']['path'])
    assert ident(trace)==ad['trace']
    d_run=R10/'runs/on-1'
    inputs=[trace,d_run/'trace.jsonl',d_run/'payload.bin']
    before=[ident(p) for p in inputs]
    native=load(target,'r15_parametric_parsers')
    prior11=load(old11,'r15_prior_coeff_parser')
    prior10=load(old10,'r15_prior_decoder_parser')
    t1,m1=prior11.parse(trace);t2,m2=native.parse_coeff(trace,210);equal(t1,t2);equal(m1,m2)
    d1=prior10.parse(d_run);d2=native.parse_decoder(d_run,314,210,502,336);equal(d1,d2)
    assert before==[ident(p) for p in inputs]
    rec=dict(status='exact_prior_control',source_parsers=pins,script=ident(__file__),new_parser=ident(target),inputs_before=before,inputs_after=[ident(p) for p in inputs],coefficient_tokens=len(t1),decoder_units=len(d1['units']),decoder_events=len(d1['events']),all_fields_arrays_bytes_exact=True,scope='Parameterization control on old admitted evidence; no R15 event/value assumption.')
    (P/'parser-control.json').write_text(json.dumps(rec,indent=2)+'\n')
    print(json.dumps(rec))

if __name__=='__main__': main()
