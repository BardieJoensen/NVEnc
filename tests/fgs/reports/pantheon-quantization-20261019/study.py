#!/usr/bin/env python3
"""Fresh-scratch adapter reusing validated Pantheon procedures and original references."""
import os,sys,json,pathlib,shutil
HERE=pathlib.Path(__file__).resolve().parent
ROOT=pathlib.Path(os.environ.get('PANTHEON_QUANT_DIR','/tmp/downloads/codex-work/pantheon-quantization-20261019'))
assert str(ROOT).startswith('/tmp/downloads/codex-work/') and not ROOT.is_symlink()
os.environ['PANTHEON_INDEPENDENT_DIR']=str(ROOT)
sys.path.insert(0,str(HERE.parent/'pantheon-independent-20261019'))
import investigate as x
OLD=pathlib.Path('/media/merged-storage/cold-storage/docker-apps/pantheon-causal-20261019')
def prepare(case):
    d=ROOT/case;d.mkdir(exist_ok=True);v=json.loads((OLD/case/'validity.json').read_text());src=pathlib.Path(v['source']);s=src.stat()
    assert {'size':s.st_size,'mtime_ns':s.st_mtime_ns}==v['source_stat']
    x.dump(d/'validity.json',v)
    def replay(tag):
        a=json.loads((OLD/case/(tag+'-command.json')).read_text())['argv']
        a=[p.replace('/tmp/downloads/codex-work/pantheon-causal-20261019',str(ROOT)) for p in a]
        x.run(a,d,tag)
    if not (d/'ref.mkv').exists():replay('extract-ref')
    # Verify only new extraction against retained all-frame hashes; do not repeat
    # the established independent original seek, codec/color/player controls.
    hr=x.hashes(['ffmpeg','-v','error','-threads','4','-i',str(d/'ref.mkv'),'-frames:v','240','-pix_fmt','yuv420p10le'])
    assert hr==v['hashes_ref']
    x.dump(d/'fresh-extraction-validation.json',{'all240_match_prior_reference':True,'source_stat_unchanged':True})
    if case in ('e04','e05-1440'):
        if not (d/'input.mkv').exists():replay('extract-input')
        if not (d/'input10.y4m').exists():x.run(['ffmpeg','-v','error','-threads','4','-i',d/'input.mkv','-pix_fmt','yuv420p10le','-strict','-1','-f','yuv4mpegpipe',d/'input10.y4m'],d,'make-y4m')
        shutil.copy2(OLD/case/'b-trace.ivf',d/'baseline.ivf');shutil.copy2(OLD/case/'b-trace.mkv',d/'baseline.mkv')
    for name in ('fixed-picture.mkv','fixed-picture.ivf'):
        if not (d/name).exists():shutil.copy2(OLD/case/name,d/name)
    if not (d/'source.yuv').exists():x.run(['ffmpeg','-v','error','-threads','4','-i',d/'ref.mkv','-pix_fmt','yuv420p10le','-f','rawvideo',d/'source.yuv'],d,'source-raw')
    if not (d/'base.yuv').exists():x.run([ROOT/'apply_grain',d/'fixed-picture.ivf',d/'base.yuv',0,96,240],d,'base-native')
    print('prepared',case,flush=True)
if __name__=='__main__':prepare(sys.argv[1])
