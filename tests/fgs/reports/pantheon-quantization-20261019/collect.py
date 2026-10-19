#!/usr/bin/env python3
"""Reconcile source rates, full-reference tails and texture evidence into report tables."""
import json,sys,pathlib
import numpy as np
from study import ROOT,OLD,HERE,x
CASES={'e04':['qp4','qp8','budget5'],'e05-1440':['qp4','qp4-tx32','budget1']}
def load(p):return json.loads(p.read_text())
allrows=[];doc={'arms':allrows,'fixtures':{},'stage_comparisons':{},'whole_window_controls':{},'representability':[]}
for case,tags in CASES.items():
 d=ROOT/case;valid=load(d/'validity.json');doc['fixtures'][case]={k:valid[k] for k in ['source','source_stat','source_mbps','fps','first_pts','last_pts']};roi='purple' if case=='e04' else 'shirt'
 for tag in ['baseline']+tags:
  old=tag=='baseline';root=OLD/case if old else d;t='b-base' if old else tag
  r=load(root/(t+'-result.json'));tex=load(root/(t+'-texture.json'))['midpoint_summary'][roi]
  cuda=load(root/('metrics-cuda-'+t+'.json'));sm=np.asarray(load(root/('ssimu2-'+t+'.json'))).flatten()
  row={'case':case,'tag':tag,'mbps':r['actual_mbps'],'vs_source_percent':100*(r['actual_mbps']/valid['source_mbps']-1),'vmaf':r['vmaf'],'neg':r['vmaf_neg'],'vmaf_p1_excluding_frame0':r['vmaf_p1_excluding_frame0'],'neg_p1_excluding_frame0':float(np.percentile([f['metrics']['vmaf_neg'] for f in cuda['frames'][1:]],1)),'ssimu2':r['ssimu2'],'ssimu2_p1':float(np.percentile(sm,1)),'ssimu2_p5':r['ssimu2_p5'],'butter_2norm':r['butter_2norm'],'butter_max_p95':r['butter_max_p95'],'psnr_y':r['psnr_y'],'ssim':r['ssim'],'ciede2000':r['ciede2000'],'cambi_full_reference_mean':r['pooled']['cambi_full_reference']['mean'],'source_hf':tex['source']['hf_sigma'],'target_hf':tex['target']['hf_sigma'],'source_acf1':tex['source']['acf1'],'target_acf1':tex['target']['acf1'],'hf_source_correlation':tex['paired_hf_correlation'],'source_temporal_hf_correlation':tex['source']['temporal_hf_corr'],'target_temporal_hf_correlation':tex['target']['temporal_hf_corr'],'reused_after_byte_identity':old}
  row['amplitude_relative_error']=row['target_hf']/row['source_hf']-1;row['acf1_absolute_error']=abs(row['target_acf1']-row['source_acf1']);row['provisional_roi_screens_pass']=abs(row['amplitude_relative_error'])<=.1 and row['acf1_absolute_error']<=.05
  if not old:
   row['encode_wall_seconds_instrumented']=load(d/(tag+'-command.json'))['seconds'];row['fps_instrumented']=336/row['encode_wall_seconds_instrumented'];row['independent_decoder_all240_exact']=load(d/(tag+'-decoder-validation.json'))['all240_allplanes_exact']
  allrows.append(row)
 base='detail' if case=='e04' else 'detail2';stage=load(d/(base+'-stages.json'));doc['stage_comparisons'][case]={'checks':stage['checks'],'diagnostic_frame':stage['frame'],'roi':stage['roi'][roi]}
 controls=load(d/'whole-window-controls.json');doc['whole_window_controls'][case]={k:controls[k] for k in ['summary','face','face_frame120_xywh','evaluation_frames']}
 doc['fixtures'][case]['budget_calibration']=load(d/'budget-calibration.json')
for p in load(ROOT/'representability-native.json'):
 q=p['controls']['quiet']['source_conditional_hf'];t=p['controls']['texture']['source_conditional_hf'];entry={'case':p['case'],'frame':p['frame'],'base_10bit_code':p['base_10bit_code'],'controls':p['controls'],'screen_derived_ranges':{'quiet_at_most':q*1.1,'texture_min':t*.9,'texture_max':t*1.1},'native_ensembles':[]}
 for a in p['probes']:
  row={k:a[k] for k in ['shape','scale','seed_count']}
  for key in ['quiet','texture']:
   vals=a['stats'][key];amps=[v['conditional_hf'] for v in vals]
   row[key]={'conditional_hf_mean':float(np.mean(amps)),'conditional_hf_min':float(min(amps)),'conditional_hf_max':float(max(amps)),'endpoint_occupancy_mean':float(np.mean([v['clip_fraction'] for v in vals])),'conditional_endpoint_occupancy_mean':float(np.mean([v['conditional_endpoint_occupancy'] for v in vals])),'isolated_grain_acf1_mean':float(np.mean([v['isolated_grain']['acf1'] for v in vals]))}
  entry['native_ensembles'].append(row)
 doc['representability'].append(entry)
(HERE/'results.json').write_text(json.dumps(doc,indent=2)+'\n')
lines=['# Measured results','','All rates are actual video packet bytes over the 240 scored frames. Texture values are the established five-frame midpoint summaries, not whole-window means. Screens are provisional, not perceptual acceptance. Baseline scores are reused only after byte-identical output verification.','', '| Case / arm | Mbps | vs source | VMAF / NEG | VMAF / NEG p1* | SSIMU2 / p5 | Butter2 / max p95 | PSNR Y / SSIM | CAMBI FR |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for r in allrows:lines.append(f"| {r['case']} / {r['tag']} | {r['mbps']:.5f} | {r['vs_source_percent']:+.2f}% | {r['vmaf']:.2f} / {r['neg']:.2f} | {r['vmaf_p1_excluding_frame0']:.2f} / {r['neg_p1_excluding_frame0']:.2f} | {r['ssimu2']:.2f} / {r['ssimu2_p5']:.2f} | {r['butter_2norm']:.3f} / {r['butter_max_p95']:.2f} | {r['psnr_y']:.2f} / {r['ssim']:.4f} | {r['cambi_full_reference_mean']:.4f} |")
lines+=['','*VMAF/NEG p1 excludes frame 0 only. Other measures include all 240 frames. Lower Butteraugli/CAMBI is better. SSIMULACRA2 can be negative. See results.json for SSIMU2 p1, CIEDE2000, timing, controls and full precision.','','| Case / arm | HF source → output | ACF1 source → output | HF correlation | Provisional ROI screen |','|---|---:|---:|---:|---|']
for r in allrows:lines.append(f"| {r['case']} / {r['tag']} | {r['source_hf']:.4f} → {r['target_hf']:.4f} | {r['source_acf1']:.4f} → {r['target_acf1']:.4f} | {r['hf_source_correlation']:.4f} | {'pass' if r['provisional_roi_screens_pass'] else 'fail'} |")
lines+=['','QP4 uses realized qindex 16 at the diagnostic ROI; QP8 uses 32. E05 qp4-tx32 and budget1 include a global 32-pixel transform cap. Budget maps hold the SB-aligned diagnostic rectangle at 16 for all 336 input frames. E04 budget5 is 5.68% above source and is **not a matched-rate result**. E05 budget1 is +0.18%. Both budget attempts fail whole-window quality. These are ten-second windows, not episode equal-size benchmarks.']
(HERE/'RESULTS.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
