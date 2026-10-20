#!/usr/bin/env python3
"""Read-only content verification after the standard cold-store relocation."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

REPORT=Path(__file__).resolve().parent
ORIGINAL=Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020')
COLD=Path('/media/merged-storage/logs/cold-storage/docker-apps/pantheon-sourcebudget-20261020')
CACHE={}

def sha(path):
    st=path.stat();key=(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)
    if key not in CACHE:
        with path.open('rb') as f:CACHE[key]=hashlib.file_digest(f,'sha256').hexdigest()
    return CACHE[key]

def identity(path):
    return dict(path=str(path.resolve()),size=path.stat().st_size,sha256=sha(path))

def main():
    out=REPORT/'archive-verification.json';assert not out.exists()
    rec=dict(status='running',started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
             argv=sys.argv,script=identity(Path(__file__)),python=identity(Path(sys.executable)),
             scope='Content hashes and relocation integrity only; historical resolved-path execution provenance requires restoring original scratch root.')
    started=time.monotonic()
    try:
        assert ORIGINAL.is_symlink() and ORIGINAL.resolve()==COLD.resolve()
        log=REPORT/'archive-execution.log';text=log.read_text()
        assert 'VERIFY FAILED' not in text
        match=re.search(r'OK '+re.escape(str(ORIGINAL))+r': (\d+) files verified, removed from SSD',text)
        assert match
        index=Path('/media/merged-storage/logs/cold-storage/INDEX.md')
        rows=[line for line in index.read_text().splitlines() if line.startswith('| `docker-apps/pantheon-sourcebudget-20261020` |')]
        assert len(rows)==1 and str(ORIGINAL) in rows[0]
        rec.update(original_root=str(ORIGINAL),cold_root=str(COLD.resolve()),compatibility_symlink=os.readlink(ORIGINAL),
                   helper_verified_files=int(match.group(1)),archive_log=identity(log),index_row=rows[0])
        checks={}
        for name in ('preflight','controls','observations'):
            path=REPORT/'psyex-cap'/name/'manifest.json';manifest=json.loads(path.read_text())
            rec.setdefault('manifests',[]).append(identity(path))
            for row in [*[x['source'] for x in manifest['files']],*manifest.get('external',[])]:
                source=Path(row['path'])
                if not source.is_relative_to(ORIGINAL):continue
                dest=COLD/source.relative_to(ORIGINAL)
                assert dest.is_file() and dest.stat().st_size==row['size'] and sha(dest)==row['sha256'],str(dest)
                checks[str(dest.relative_to(COLD))]=dict(size=row['size'],sha256=row['sha256'])
        # Both R18 source trees are needed for an exact continuation.
        source_counts={}
        for build in ('build-1','build-observer-2'):
            p=COLD/'parent/psyex-cap-r18'/build/'completed-build-pins.json'
            pins=json.loads(p.read_text())
            source=COLD/Path(pins['source_root']).relative_to(ORIGINAL)
            manifest=COLD/Path(pins['source_manifest']['path']).relative_to(ORIGINAL)
            assert sha(manifest)==pins['source_manifest']['sha256']
            expected=json.loads(manifest.read_text())
            for rel,size,digest in expected:
                f=source/rel
                assert f.is_file() and not f.is_symlink() and f.stat().st_size==size and sha(f)==digest,str(f)
            actual=[str(f.relative_to(source)) for f in source.rglob('*') if f.is_file() and '.git' not in f.relative_to(source).parts]
            assert sorted(actual)==sorted(row[0] for row in expected)
            source_counts[build]=len(expected)
        rec.update(status='verified',artifact_checks=checks,source_files_checked=source_counts,
                   unique_file_contents_hashed=len(CACHE),seconds=time.monotonic()-started)
        assert identity(Path(__file__))==rec['script'] and identity(Path(sys.executable))==rec['python']
    except BaseException as error:
        rec.update(status='failed',error=repr(error),seconds=time.monotonic()-started)
        raise
    finally:
        rec['finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
        out.write_text(json.dumps(rec,indent=2)+'\n')
    print(json.dumps({k:rec[k] for k in ('status','helper_verified_files','source_files_checked','unique_file_contents_hashed','seconds')}))

if __name__=='__main__':
    if not __debug__:raise SystemExit('optimized Python prohibited')
    main()
