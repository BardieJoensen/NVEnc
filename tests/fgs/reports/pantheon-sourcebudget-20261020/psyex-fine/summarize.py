#!/usr/bin/env python3
"""Select already-admitted R13 fields; computes no new descriptors."""
import argparse,datetime as dt,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
R13_RESULT_SHA='4511e7223f5c9b8b721e5d2f8c5d01d062ffb5d981bd106ae85ff59e0e1dbb93'
R13_ARRAYS_SHA='11927240f6279d39f491885ab5b50ccd1b89da57ff59830b7265c8372719af09'
def ident(p):
 p=Path(p).resolve()
 with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
 return {'path':str(p),'sha256':h,'size':p.stat().st_size}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('out',type=Path);args=ap.parse_args();out=args.out
 assert not out.exists();out.mkdir(parents=True)
 result_path=HERE/'run-1/result.json';arrays_path=HERE/'run-1/q1-arrays.npz';receipt_path=HERE/'run-1/receipt.json';manifest=HERE/'visuals-1/manifest.json'
 assert ident(result_path)['sha256']==R13_RESULT_SHA and ident(arrays_path)['sha256']==R13_ARRAYS_SHA
 r=json.loads(result_path.read_text());assert r['status']=='admitted_diagnostic';assert r['q1_arrays']==ident(arrays_path)
 v=json.loads(manifest.read_text());assert v['status']=='prepared'
 compact={'status':'admitted_diagnostic','scope':r['scope'],'result':ident(result_path),'q1_arrays':ident(arrays_path),'run_receipt':ident(receipt_path),'visual_manifest':ident(manifest),'counts':r['counts'],'realized_qindex':r.get('realized_qindex'),'q1_tables':r['q1_tables'],'distance_metrics':r['distance_metrics'],'fixed_roi':r['fixed_roi'],'script':r['script'],'r12_result':r['r12_result'],'r12_arrays':r['r12_arrays'],'library':r['library'],'contract':r['contract'],'visuals':v['rois'],'generated_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
 (out/'compact-result.json').write_text(json.dumps(compact,indent=2,allow_nan=False)+'\n');print(json.dumps({'status':'complete','compact':ident(out/'compact-result.json')}))
if __name__=='__main__':main()
