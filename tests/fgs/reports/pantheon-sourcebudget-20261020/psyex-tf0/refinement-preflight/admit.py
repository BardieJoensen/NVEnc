#!/usr/bin/env python3
"""R16 joins: syntax lifecycle, decoder, source boundaries, final encoder stages."""
import argparse, hashlib, importlib.util, json, re, sys
from pathlib import Path
import numpy as np

P=Path(__file__).resolve().parent
ROOT=P.parents[1]
REPORT=Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020')
R11=ROOT/'parent/psyex-coeff-r11'
R10=ROOT/'parent/aom-decoder-r10-v2'
WORK=ROOT/'worker/psyex-r16-calibration-refine'
FRAME=1920*1080*3
W,H=1920,1080
PARSER_SHA='45f11c246037e1a58a2762235a62db9a0bcb71e85fe992cfcc35897fa24983e3'
BINDER_SHA='5d30f960504b12d840d9cd916140dac5b24ae2053852c88a5a66b87ae1b347dc'
REPLAY_SHA='8491a376d6376aeb3f0cd2e3903c513b8f7bd0a300eaddd1d882a06917814cc6'
ENCODE_SHA='5804a1a5985d0676975abe28fba2d8c7a8d6af71c2f70d39dab11436bf2941e4'
DECODER_CHECK_SHA='f9bcdfca7e8782dda55e39770148c46a4d2ea7c2070c9c252040f166e4e3938a'
DECODER_REPLAY_SHA='d3fc7d7eb4ddcd295f87bd9083bfd6da01c082dae742924a4d249b0461b18a85'

def ident(p):
    p=Path(p).resolve()
    with p.open('rb') as f: h=hashlib.file_digest(f,'sha256').hexdigest()
    return dict(path=str(p),sha256=h,size=p.stat().st_size)

def exact(d):
    assert ident(d['path'])==d,d
    return Path(d['path'])

def load(p,name,sha):
    assert ident(p)['sha256']==sha,p
    spec=importlib.util.spec_from_file_location(name,p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def dump(p,d):p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('run',type=Path);ap.add_argument('run_sha')
    ap.add_argument('binding',type=Path);ap.add_argument('binding_sha')
    ap.add_argument('off',type=Path);ap.add_argument('on',type=Path)
    ap.add_argument('decoder_off',type=Path);ap.add_argument('decoder_on',type=Path)
    ap.add_argument('decoder_replay_sha');ap.add_argument('out',type=Path)
    a=ap.parse_args();a.out.mkdir(exist_ok=False)
    assert a.decoder_replay_sha==DECODER_REPLAY_SHA
    artifacts={}
    def bind(name,p,sha=None):
        d=ident(p)
        if sha is not None:assert d['sha256']==sha,(name,d)
        artifacts[name]=d;return d
    originalp=a.run/'command.json';bind('original_receipt',originalp,a.run_sha)
    original=json.loads(originalp.read_text())
    assert original['status']=='encoded' and original['returncode']==0 and original['case']=='e05-1440'
    assert original['executed_script']['sha256']==ENCODE_SHA and original['identity_before']==original['identity_after']
    for path,sha in original['identity_after'].items():assert ident(path)['sha256']==sha
    for k in ('input','ivf_output','recon','stats','stats_snapshot','contract'):exact(original[k])
    assert original['stats']['sha256']==original['stats_snapshot']['sha256']
    assert original['contract']['sha256']=='9ea9b3bd9dcf4c5a7f994e0eb12508448a93142ad9d7b7baec27f5ea21597d82'
    for flag,value in {'--enable-tf':'0','--preset':'4','--input-depth':'10'}.items():
        assert original['settings'][flag]==value
    encoder=load(WORK/'encode_refine.py','r16_encoder',ENCODE_SHA)
    validated, dependencies=encoder.validate_chain(originalp,a.run_sha)
    assert validated==original
    assert original['within_source_ceiling'] and original['matched_rate_comparable']
    bind('syntax_binding',a.binding,a.binding_sha);binding=json.loads(a.binding.read_text())
    assert binding['status']=='bound' and binding['encode_receipt']==artifacts['original_receipt']
    assert binding['script']['sha256']==BINDER_SHA and binding['input_ivf']==original['ivf_output']
    for k in ('script','events','command','trace_log','target_frame_obu','input_ivf'):exact(binding[k])
    outer_path=exact(binding['outer_execution'])
    outer=json.loads(outer_path.read_text())
    assert outer['status']=='complete' and outer['returncode']==0
    bind('outer_execution',outer_path)
    expected=json.loads(exact(binding['events']).read_text())
    target=binding['target_coded_event'];event=target['event_index'];coded=target['coded_ordinal']
    events=expected['events'];nc=sum(not e['show_existing_frame'] for e in events)
    assert all(type(v)==int for v in (event,coded,nc)) and 0<=event<len(events) and 0<=coded<nc
    assert binding['summary']['frame_headers']==len(events) and binding['summary']['coded_non_show_existing']==nc
    assert len(expected['displays'])==336 and expected['displays'][216]['coded_ordinal']==coded
    assert expected['displays'][216]['coded_event_index']==event and events[event]['coded_ordinal']==coded
    assert events[event]['obu']==target['obu'] and target['obu']['type']==6
    parser=load(ROOT/'parent/psyex-real-r15/parsers.py','r16_parsers',PARSER_SHA)
    controlp=ROOT/'parent/psyex-real-r15/parser-control.json';bind('parser_control',controlp,'afb324e1c891990816383bdfc0ecc281268692c96003adc9729e55163cf947e4')
    control=json.loads(controlp.read_text())
    assert control['status']=='exact_prior_control' and control['all_fields_arrays_bytes_exact']
    assert control['new_parser']==ident(ROOT/'parent/psyex-real-r15/parsers.py')
    assert control['script']==bind('parser_generator',ROOT/'parent/psyex-real-r15/prepare_parsers.py','8a1f29866cfdecbebfbbac1b9b0df2c5cf6102e65c840634e4d77d4529b00b9d')
    for d in control['source_parsers']+control['inputs_before']:exact(d)
    assert control['inputs_before']==control['inputs_after']
    bind('parser',ROOT/'parent/psyex-real-r15/parsers.py',PARSER_SHA)
    # All independent full-frame decoders agree before any coefficient interpretation.
    cp=a.run/'decoder-validation/decoder-validation.json';bind('all336_decoder_check',cp)
    dc=json.loads(cp.read_text())
    assert dc['status']=='admitted' and dc['all336_allplanes_app_dav1d_libaom_NVDEC_exact']
    assert dc['source_script']['sha256']==DECODER_CHECK_SHA and dc['inputs']['command.json']==artifacts['original_receipt']
    assert dc['inputs']['out.ivf']==original['ivf_output'] and dc['recon']==original['recon']
    for k in ('script','source_script','shared_helper','probe'):exact(dc[k])
    assert dc['identity_before']==dc['identity_after'] and dc['launch_tools_before']==dc['launch_tools_after']
    for row in dc['commands']:
        assert row['returncode']==0
        exact(row['log']);exact(row['output'])
    assert len(dc['hashes'])==336
    pins_path=R11/'completed-build-pins.json';bind('encoder_build',pins_path,'f32ace44e5e449ce0898b6566cc9bb3195a8daa2fcb0b9d7f20b0e0d8b3c54d8')
    pins=json.loads(pins_path.read_text())
    for d in pins.values():
        if isinstance(d,dict) and {'path','sha256','size'}<=d.keys():exact(d)
    commands={}
    for name,run in [('off',a.off),('on',a.on)]:
        commands[name]=bind('encoder_'+name,run/'command.json')
        r=json.loads((run/'command.json').read_text())
        assert r['status']=='neutral' and r['returncode']==0 and r['mode']==name
        assert r['original_receipt']==artifacts['original_receipt'] and r['pins']==ident(pins_path)
        assert r['app']==pins['app'] and r['library']==pins['library']
        assert r['identity_before']==r['identity_after']
        for path,sha in r['identity_after'].items():assert ident(path)['sha256']==sha
        assert r['script']['sha256']==r['source_script']['sha256']==REPLAY_SHA
        for k in ('script','source_script','log','stats','out.ivf','recon.yuv'):exact(r[k])
        assert r['out.ivf']['sha256']==original['ivf_output']['sha256'] and r['recon.yuv']['sha256']==original['recon']['sha256']
        assert r['recon.yuv']['size']==336*FRAME and r['stats']['sha256']==original['stats']['sha256']
        cmd=list(original['commands']['pass2']);assert cmd[6]==original['binary']['path'];cmd[6]=pins['app']['path']
        for flag,value in {'--stats':str(run/'pass.stats'),'-b':str(run/'out.ivf'),'-o':str(run/'recon.yuv')}.items():
            assert cmd.count(flag)==1;cmd[cmd.index(flag)+1]=value
        assert cmd==r['argv']
        keys={'LD_LIBRARY_PATH'}|({'SVT_PANTHEON_BOUNDARY_FD','SVT_PANTHEON_COEFF_FD'} if name=='on' else set())
        assert set(r['environment'])==keys and r['environment']['LD_LIBRARY_PATH']==str(R11/'build/bin')
        if name=='on':
            assert r['environment']['SVT_PANTHEON_BOUNDARY_FD']!=r['environment']['SVT_PANTHEON_COEFF_FD']
            for key in keys-{'LD_LIBRARY_PATH'}:assert re.fullmatch('[0-9]+',r['environment'][key]) and int(r['environment'][key])>=3
            assert exact(r['observation'])==run/'boundary.bin' and exact(r['coefficient_observation'])==run/'coeff.bin'
        else: assert not (run/'boundary.bin').exists() and not (run/'coeff.bin').exists()
    # Reuse the admitted complete-source/boundary parser; it already binds picture216.
    boundary_path=REPORT/'validate_psyex_boundary.py'
    boundary_sha='763eeebf43017e79aba6c8ffdce531462f262000290ba9846ad7ae8065e70f8d'
    # Its exact file identity is independently tied to the prior admitted R9 checker.
    old_boundary_path=ROOT/'parent/psyex-boundary-r9/admitted-1/admission.json'
    bind('prior_boundary_admission',old_boundary_path,'f6a7a6d3221f15fb789419a43cd3f1b61372ffb99e325cd1ee131962ed5be7fc')
    old_boundary=json.loads(old_boundary_path.read_text())
    assert ident(boundary_path)==old_boundary['script']
    boundary=load(boundary_path,'r16_boundary',boundary_sha);bind('boundary_parser',boundary_path,boundary_sha)
    attempts,post,records,terminal=boundary.parse_trace(a.on/'boundary.bin')
    accepted=attempts[-1];m=accepted['metadata']
    assert m['decode_order']==coded and (m['order_hint'],m['frame_type'],m['show_frame'])==(target['order_hint'],target['frame_type'],target['show_frame'])
    if target['showable_frame'] is not None:assert m['showable_frame']==target['showable_frame']
    with exact(original['recon']).open('rb') as f:f.seek(216*FRAME);assert f.read(FRAME)==post
    assert hashlib.md5(post).hexdigest()==dc['hashes'][216]
    src=boundary.read_frame(ROOT/'fixtures/e05-1440/source.yuv',120,240)
    assert hashlib.sha256(src).hexdigest()=='c2798d9c00f53bdbe7041575249b353a478a8f5557bc4dd5b61d9ae03f13ea12'
    stages={}
    for name,raw in [('original',src),('coding_input',accepted['coding_input']),('preloop',accepted['preloop']),('postloop',post)]:
        path=a.out/(name+'.yuv');path.write_bytes(raw);stages[name]=ident(path)
    # Native decoder producer identity and all-output neutrality.
    native_commands={}
    for name,run in [('off',a.decoder_off),('on',a.decoder_on)]:
        native_commands[name]=bind('decoder_'+name,run/'command.json')
        r=json.loads((run/'command.json').read_text())
        assert r['status']=='decoded' and r['returncode']==0 and r['trace']==(name=='on') and r['all336_allplanes_exact']
        assert r['encode_receipt']==artifacts['original_receipt'] and r['binding']==artifacts['syntax_binding']
        assert r['input']==original['ivf_output'] and r['expected_recon']==original['recon']
        assert r['script']['sha256']==a.decoder_replay_sha;exact(r['script'])
        assert r['inputs_before']==r['inputs_after']
        for d in r['inputs_after']:exact(d)
        for key in ('app','library','recon','build_pins','log','ldd'):exact(r[key])
        assert r['recon']['sha256']==original['recon']['sha256'] and r['recon']['size']==336*FRAME
        if name=='on':
            for key in ('trace.jsonl','payload.bin'):exact(r[key])
        else:assert not (run/'trace.jsonl').exists() and not (run/'payload.bin').exists()
    native=parser.parse_decoder(a.decoder_on,event,coded,len(events),nc)
    assert native['preloop'].tobytes()==accepted['preloop'][:W*H*2] and native['postloop']==post
    frame_helper=load(REPORT/'aom_tu_binding.py','r16_framing','7d8be210357c70706ca17c8ecad81463b22b809455cc3c36944714c66cfd7935')
    packets=frame_helper.ivf_packets(exact(original['ivf_output']).read_bytes());consumed=[0]*336;coded_seen=-1
    for (got,raw),want in zip(native['events'],events):
        pi=want['packet_index'];start=consumed[pi];assert raw==packets[pi]['data'][start:start+len(raw)]
        frame_obus=[o for o in frame_helper.obus(raw) if o['type'] in (3,6)];assert len(frame_obus)==1
        obu=frame_obus[0];key=want['obu']
        assert (obu['type'],len(obu['data']),hashlib.sha256(obu['data']).hexdigest())==(key['type'],key['size'],key['sha256'])
        assert start+obu['start']==key['packet_start'] and start+obu['end']==key['packet_end']
        assert packets[pi]['file_offset']+start+obu['start']==key['file_offset'];consumed[pi]+=len(raw)
        assert got['event']==want['event_index'] and got['show_existing']==want['show_existing_frame']
        if not got['show_existing']:
            coded_seen+=1;assert got['coded_ordinal']==coded_seen==want['coded_ordinal']
            for key in ('frame_type','show_frame','order_hint'):assert got[key]==want[key]
            assert got['refresh']==want['refresh_frame_flags_normalized']
            if 'showable_frame' in want:assert got['showable']==want['showable_frame']
        else:
            assert got['coded_ordinal']==coded_seen and got['frame_type']==got['showable']==-1 and got['show_frame']==1
            assert got['order_hint']==events[want['resolved_event_index']]['order_hint']
    assert coded_seen==nc-1 and consumed==[len(p['data']) for p in packets]
    # Committed encoder owner and final coefficient join, including all target/control support.
    tokens,coeff_terminal=parser.parse_coeff(a.on/'coeff.bin',coded)
    assert coeff_terminal['footer']['accepted_generation']==terminal['accepted_generation']
    payload=(a.decoder_on/'payload.bin').read_bytes()
    coding=np.frombuffer(accepted['coding_input'],dtype='<u2',count=W*H).reshape(H,W)
    cover=np.zeros((H,W),bool);positive=set();joined=[]
    for key,t in tokens.items():
        z=t['begin'];x,y,w,h=(z[k] for k in ('x','y','w','h'));vh=min(h,H-y);sl=np.s_[y:y+vh,x:x+w]
        assert not cover[sl].any();cover[sl]=True
        assert np.array_equal(t['source'][:vh],coding[sl])
        assert np.array_equal(t['predictor'][:vh],native['predictor'][sl]) and np.array_equal(t['reconstruction'][:vh],native['preloop'][sl])
        ids=np.unique(native['unit'][sl]);assert len(ids)==1
        u=native['units'][int(ids[0])];leaf=native['leaves'][u['leaf']]
        assert (z['block_x'],z['block_y'],z['block_w'],z['block_h'])==(leaf['x'],leaf['y'],leaf['w'],leaf['h'])
        if t['stages']:assert t['info']['actual_qindex']==u['coded_qindex']==t['commit']['qindex']
        if u['eob']:
            assert u['category']==4 and u['id'] not in positive;positive.add(u['id'])
            assert (u['x'],u['y'],u['w'],u['h'],u['tx_w'],u['tx_h'])==(x,y,w,vh,w,h)
            assert not z['md_skip'] and not z['skip_mode'] and t['end']['eob']==u['eob']
            assert (z['tx'],z['type'],z['n'])==(u['tx_size'],u['tx_type'],u['coeff_count'])
            dq=np.frombuffer(payload,dtype='<i4',count=z['n'],offset=u['coeff_offset'])
            assert np.array_equal(parser.decoder_layout(t['stages'][-1]['dq'],w,h),dq)
            assert t['tables'][6,:2].tolist()==leaf['decoder_dequant']
            qm=leaf['qm_level_y'] if z['type']<9 and leaf['using_qmatrix'] else 15
            assert t['info']['qm_level']==qm
            iq=payload[u['iqm_offset']:u['iqm_offset']+u['iqm_count']]
            native_iq=np.frombuffer(t['iqm'],dtype='u1')
            assert (parser.decoder_layout(native_iq,w,h).tobytes() if len(native_iq) else b'')==iq
        else:assert t['end']['eob']==0 and np.array_equal(t['reconstruction'],t['predictor'])
        joined.append(dict(token=key,unit=u['id'],category=u['category'],begin=z,info=t.get('info'),end=t['end'],commit=t['commit'],payload_offsets=t['payload_offsets'],stages=[{k:v for k,v in s.items() if k not in ('q','dq','inverse')} for s in t['stages']]))
    expected_positive={u['id'] for u in native['units'] if u['eob'] and parser.inter(u['x'],u['y'],u['w'],u['h'])}
    assert positive==expected_positive
    qsummary={}
    for name,(rx,ry,rw,rh) in zip(('shirt','background','face'),parser.ROIS):
        assert cover[ry:ry+rh,rx:rx+rw].all()
        qpixels={};skipped=0;invoked=0;geometry={}
        for t in tokens.values():
            z=t['begin'];x,y,w,h=(z[k] for k in ('x','y','w','h'))
            n=max(0,min(x+w,rx+rw)-max(x,rx))*max(0,min(y+h,ry+rh)-max(y,ry))
            if not n:continue
            state='invoked' if t['stages'] else 'uninvoked'
            g=f"{state}:{w}x{h}:type{z['type']}";geometry[g]=geometry.get(g,0)+n
            if t['stages']:
                q=str(t['info']['actual_qindex']);qpixels[q]=qpixels.get(q,0)+n;invoked+=n
            else:skipped+=n
        assert invoked+skipped==rw*rh
        qsummary[name]=dict(xywh=[rx,ry,rw,rh],invoked_pixels=invoked,uninvoked_pixels=skipped,qindex_invoked_pixels=qpixels,pixels_above_qindex1=sum(n for q,n in qpixels.items() if int(q)>1),pixels_above_qindex4=sum(n for q,n in qpixels.items() if int(q)>4),geometry_pixels=geometry)
    native_artifacts={}
    for key in ('leaves','units'):
        path=a.out/(key+'.json');dump(path,native[key]);native_artifacts[key]=ident(path)
    for key in ('owner','unit','category'):
        path=a.out/(key+'.npy');np.save(path,native[key]);native_artifacts[key]=ident(path)
    for key in ('predictor','preloop'):
        path=a.out/(key+'.y');native[key].tofile(path);native_artifacts[key]=ident(path)
    decoder_ad=dict(status='admitted',input_frame=216,scored_frame=120,all336_allplanes_exact=True,complete_visible_luma_ownership=True,all_events_independently_bound=True,artifacts=native_artifacts,r9_stages=stages,commands=native_commands,payload=ident(a.decoder_on/'payload.bin'),trace=ident(a.decoder_on/'trace.jsonl'),independent_binding=ident(a.binding),terminal=native['terminal'])
    dp=a.out/'decoder-admission.json';dump(dp,decoder_ad)
    tp=a.out/'tokens.json';dump(tp,joined)
    result=dict(status='admitted',case='e05-1440',tag=original['tag'],scope='R16 actual final encoder/native-decoder join on three traced ROIs; full-frame source/preloop/postloop boundaries and all336 output identity, no quality or playback acceptance',original_receipt=artifacts['original_receipt'],unmodified_ivf=original['ivf_output'],commands=commands,artifacts=artifacts,script=ident(__file__),trace=ident(a.on/'coeff.bin'),boundary=ident(a.on/'boundary.bin'),decoder_admission=ident(dp),token_manifest=ident(tp),actual_committed_owner=True,all336_exact=True,all_traced_roi_owners_source_predictor_preloop_exact=True,all_traced_positive_units_dq_iqm_exact_with_all_traced_eob_q_exact=True,tokens=len(tokens),positive_units=len(positive),quantization=qsummary,terminal=coeff_terminal,source_boundaries=stages,source_change_count=int(np.count_nonzero(np.frombuffer(src,dtype='<u2')!=np.frombuffer(accepted['coding_input'],dtype='<u2'))))
    for d in artifacts.values():exact(d)
    dump(a.out/'admission.json',result)
    print(json.dumps({k:result[k] for k in ('status','tokens','positive_units','quantization','source_change_count')}))

if __name__=='__main__':
    if not __debug__:raise SystemExit('optimized Python prohibited')
    main()
