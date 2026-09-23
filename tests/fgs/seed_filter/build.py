#!/usr/bin/env python3
"""Explicit, isolated Linux build. Does not install packages or replace FFmpeg."""
import argparse,hashlib,json,os,pathlib,shutil,subprocess,sys,tarfile,tempfile,time

COMMIT='140fd653aed8cad774f991ba083e2d01e86420c7'
ARCHIVE_SHA256='5c4a9e51e706b8deba835f02ea70e1e1101187f601adae72b36ec2b17b6f15be'
URL=f'https://codeload.github.com/FFmpeg/FFmpeg/tar.gz/{COMMIT}'
def sha(path):
    with path.open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',type=pathlib.Path,required=True,help='Verified FFmpeg n8.0 archive: '+URL)
    p.add_argument('--work-dir',type=pathlib.Path,required=True,help='New build directory, preferably off root')
    p.add_argument('--output',type=pathlib.Path,required=True,help='New libfgsseed.so path')
    a=p.parse_args();a.archive=a.archive.resolve();a.work_dir=a.work_dir.resolve();a.output=a.output.absolute()
    if sys.platform!='linux':p.error('This builder qualifies Linux only')
    if not a.archive.is_file() or sha(a.archive)!=ARCHIVE_SHA256:p.error('FFmpeg archive checksum mismatch')
    if a.work_dir.exists() or a.output.exists() or a.output.is_symlink():p.error('Work directory and output must be new')
    if not a.output.parent.is_dir():p.error('Output parent directory is missing')
    a.work_dir.mkdir(parents=True)
    own=pathlib.Path(__file__).resolve().parent
    record=dict(complete=False,started=time.time(),ffmpeg_commit=COMMIT,url=URL,archive_sha256=ARCHIVE_SHA256,
                sources={x.name:sha(x) for x in own.iterdir() if x.is_file()},commands=[],installed=False)
    try:
        with tarfile.open(a.archive) as archive:archive.extractall(a.work_dir,filter='data')
        source=a.work_dir/('FFmpeg-'+COMMIT)
        shutil.copy2(own/'av1_grain_seed.c',source/'libavcodec/bsf/av1_grain_seed.c')
        for name,anchor,line in [
            ('configure','av1_metadata_bsf_select="cbs_av1"','av1_grain_seed_bsf_select="cbs_av1"\n'),
            ('libavcodec/bsf/Makefile','OBJS-$(CONFIG_AV1_METADATA_BSF)','OBJS-$(CONFIG_AV1_GRAIN_SEED_BSF)         += bsf/av1_grain_seed.o\n'),
            ('libavcodec/bitstream_filters.c','extern const FFBitStreamFilter ff_av1_metadata_bsf;','extern const FFBitStreamFilter ff_av1_grain_seed_bsf;\n')]:
            file=source/name;text=file.read_text()
            if text.count(anchor)!=1:raise ValueError('Unexpected FFmpeg source: '+name)
            file.write_text(text.replace(anchor,line+anchor))
        temporary=a.work_dir/'libfgsseed.so'
        commands=[
            ['./configure','--disable-everything','--disable-autodetect','--disable-programs','--disable-doc',
             '--disable-network','--disable-x86asm','--disable-avformat','--disable-avdevice','--disable-avfilter',
             '--disable-swresample','--disable-swscale','--disable-shared','--enable-static','--enable-avcodec',
             '--enable-avutil','--enable-bsf=av1_grain_seed','--enable-small','--enable-pic'],
            ['nice','-n','15','make','-j','2'],
            ['g++','-std=c++17','-O2','-fPIC','-shared','-I',str(source),str(own/'seed-library.cpp'),
             str(source/'libavcodec/libavcodec.a'),str(source/'libavutil/libavutil.a'),
             '-Wl,--exclude-libs,ALL','-Wl,-Bsymbolic','-Wl,--version-script='+str(own/'seed-library.map'),
             '-lpthread','-lm','-lz','-latomic','-o',str(temporary)]]
        with (a.work_dir/'build.log').open('w') as log:
            for command in commands:
                record['commands'].append(command)
                subprocess.run(command,cwd=source,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
        exports=subprocess.check_output(['nm','-D','--defined-only',str(temporary)],text=True)
        expected={'FGS_SEED_1','fgs_av1_seed_abi_version','fgs_av1_seed_open','fgs_av1_seed_process',
                  'fgs_av1_seed_error','fgs_av1_seed_close'}
        if {x.split()[-1].split('@')[0] for x in exports.splitlines()}!=expected:
            raise RuntimeError('Unexpected exported symbols')
        dynamic=subprocess.check_output(['readelf','-d',str(temporary)],text=True)
        if 'libavcodec' in dynamic or 'libavutil' in dynamic:raise RuntimeError('Parser is not isolated')
        # Publish a complete library without overwriting a destination created
        # during the build, including across separate build/output filesystems.
        staged=None
        try:
            with tempfile.NamedTemporaryFile(dir=a.output.parent,prefix='.fgs-seed-',delete=False) as output:
                staged=pathlib.Path(output.name)
                with temporary.open('rb') as compiled:shutil.copyfileobj(compiled,output)
                output.flush();os.fsync(output.fileno())
            staged.chmod(0o644)
            os.link(staged,a.output)
        finally:
            if staged is not None:staged.unlink(missing_ok=True)
        record.update(complete=True,output=str(a.output),sha256=sha(a.output),exports=exports,
                      dependencies=[x.strip() for x in dynamic.splitlines() if 'NEEDED' in x],seconds=time.time()-record['started'])
    finally:(a.work_dir/'build.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))
if __name__=='__main__':main()
