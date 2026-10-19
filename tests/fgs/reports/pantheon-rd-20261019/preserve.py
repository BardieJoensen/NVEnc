#!/usr/bin/env python3
"""Pack inspectable raw evidence, then retire only this task's reproducible scratch.

Run pack first. Run retire only after the supervisor records idle/mount/job checks.
Archive relocation itself uses the established archive-to-cold-storage.sh.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT=Path('/tmp/downloads/codex-work/pantheon-rd-20261019')
assert ROOT.is_dir() and not ROOT.is_symlink() and ROOT.resolve()==ROOT

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while b:=f.read(4*1024*1024):h.update(b)
    return h.hexdigest()

def record(p):return {'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)}
def dump(p,value):p.write_text(json.dumps(value,indent=2)+'\n')

def validate_measured_source():
    d=ROOT/'parent/measured-svt';receipt=d/'receipt.json';meta=json.loads(receipt.read_text())
    binary=d/'SvtAv1EncApp-retain';archive=d/'source.tar.zst'
    assert meta['source_matches_last_607_file_audit']
    assert sha(binary)==meta['audit']['diagnostic_binary_sha256']
    expected=meta['audit']['source_hashes'];seen=set()
    proc=subprocess.Popen(['zstd','-dc',str(archive)],stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=proc.stdout,mode='r|') as tf:
            for m in tf:
                name=m.name.removeprefix('./')
                if not name.startswith('Source/') or m.isdir():continue
                assert m.isfile() and name in expected and name not in seen,name
                h=hashlib.sha256();f=tf.extractfile(m)
                while b:=f.read(4*1024*1024):h.update(b)
                assert h.hexdigest()==expected[name],name
                seen.add(name)
    finally:proc.stdout.close();code=proc.wait()
    assert code==0 and seen==set(expected) and len(seen)==607
    dump(d/'archive-validation.json',{'all607_source_member_hashes_exact':True,
         'source_archive':record(archive),'binary':record(binary),'audit_receipt':record(receipt)})

def pack():
    dest=ROOT/'raw-evidence.tar.zst';assert not dest.exists()
    paths=[]
    for base in [ROOT/'worker',ROOT/'parent']:
        for p in base.rglob('*'):
            rel=p.relative_to(ROOT)
            if not p.is_file() or p.is_symlink():continue
            if any(z in ('src','build','audit-source') for z in rel.parts):continue
            if 'detail' in rel.parts or 'trace' in rel.parts or ('h264-qp' in rel.parts and p.suffix=='.csv'):
                paths.append(p)
    records=[record(p) for p in sorted(paths)];assert records
    dump(ROOT/'raw-evidence-members.json',records)
    names=ROOT/'raw-evidence-filelist.bin'
    names.write_bytes(b''.join(os.fsencode(r['path'])+b'\0' for r in records))
    subprocess.run(['tar','--hard-dereference','--use-compress-program=zstd -T2 -6','-cf',str(dest),'-C',str(ROOT),
                    '--null','-T',str(names)],check=True)
    expected={r['path']:r for r in records};seen=set()
    proc=subprocess.Popen(['zstd','-dc',str(dest)],stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=proc.stdout,mode='r|') as tf:
            for m in tf:
                assert m.isfile() and m.name in expected and m.name not in seen,m.name
                f=tf.extractfile(m);h=hashlib.sha256();n=0
                while b:=f.read(4*1024*1024):h.update(b);n+=len(b)
                assert (n,h.hexdigest())==(expected[m.name]['bytes'],expected[m.name]['sha256']),m.name
                seen.add(m.name)
    finally:proc.stdout.close();code=proc.wait()
    assert code==0 and seen==set(expected)
    dump(ROOT/'raw-evidence-validation.json',{'all_member_sha256_verified':True,'members':len(seen),
         'archive':record(dest),'member_manifest':record(ROOT/'raw-evidence-members.json')})
    print('Packed and hash-verified',len(seen),'raw evidence files',flush=True)

def retire():
    pre=json.loads((ROOT/'retirement-preflight.json').read_text())
    assert pre['no_task_jobs'] and pre['no_mounts'] and pre['no_scheduled_references'] and pre['no_worktrees']
    val=json.loads((ROOT/'raw-evidence-validation.json').read_text())
    assert record(ROOT/'raw-evidence.tar.zst')==val['archive'] and val['all_member_sha256_verified']
    manifest=ROOT/'raw-evidence-members.json'
    assert record(manifest)==val['member_manifest']
    packed=[]
    for r in json.loads(manifest.read_text()):
        rel=Path(r['path']);assert not rel.is_absolute() and '..' not in rel.parts
        p=(ROOT/rel).resolve();assert p.is_relative_to(ROOT) and p==ROOT/rel and not p.is_symlink()
        assert record(p)==r;packed.append(p)
    validate_measured_source()
    retired=[]
    for p in packed:p.unlink()
    # Full raw reconstructions and score decodes regenerate from retained streams.
    paths=set(ROOT.glob('worker/*/recon.yuv'))|set(ROOT.glob('parent/*/recon.yuv'))|set(ROOT.glob('parent/real/*/*/recon.yuv'))
    paths|=set(ROOT.glob('parent/scores/*/*-decoded.mkv'))
    for base in [ROOT/'fixtures',ROOT/'parent/scores']:
        for name in ('source.yuv','ref.mkv','input.mkv','input10.y4m'):
            paths|=set(base.glob('*/'+name))
    for p in sorted(paths):
        assert p.is_file() and not p.is_symlink();retired.append(record(p));p.unlink()
    # Preserve rejected worker implementation for methodological audit, not reuse.
    src=ROOT/'worker/src';snapshot=ROOT/'worker/rejected-source.tar.zst'
    assert src.is_dir() and not snapshot.exists()
    subprocess.run(['tar','--use-compress-program=zstd -T2 -6','--exclude=Bin','--exclude=.git',
                    '-cf',str(snapshot),'-C',str(src),'.'],check=True)
    subprocess.run(['zstd','-t',str(snapshot)],check=True,stdout=subprocess.DEVNULL)
    # Accepted source archive and binary were independently verified above.
    removed_dirs=[]
    for rel in ['analysis-venv','parent-build','parent-source','parent/audit-source','worker/build','worker/src']:
        p=ROOT/rel;assert p.is_dir() and not p.is_symlink();shutil.rmtree(p);removed_dirs.append(rel)
    # Drop empty payload directories after their contents were independently verified.
    for p in sorted(ROOT.rglob('*'),key=lambda p:len(p.parts),reverse=True):
        if p.is_dir() and not p.is_symlink() and not any(p.iterdir()):p.rmdir()
    dump(ROOT/'retirement.json',{'packed_raw_members_removed':val['members'],
        'reproducible_media_removed':retired,'reproducible_directories_removed':removed_dirs,
        'rejected_source_snapshot':record(snapshot),'prior_archives_untouched':True})
    print('Retired reproducible files; retained streams, packed raw evidence, provenance and visuals',flush=True)

def manifest():
    dest=ROOT/'SHA256SUMS';rows=[]
    for p in sorted(ROOT.rglob('*')):
        if p.is_file() and not p.is_symlink() and p!=dest:rows.append(sha(p)+'  '+str(p.relative_to(ROOT)))
    dest.write_text('\n'.join(rows)+'\n');print('Manifest files:',len(rows),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['pack','retire','manifest'])
    globals()[parser.parse_args().action]()
