#!/usr/bin/env python3
"""Validate neutral R8 replay and aggregate policy delivery, before quality."""
import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT=Path(os.environ.get("PANTHEON_SOURCEBUDGET_ROOT","/tmp/downloads/codex-work/pantheon-sourcebudget-20261020"))
OBS=ROOT/"parent/psyex-observation"
ORIGINAL=ROOT/"worker/psyex-r8/runs/e05-1440/psyex-1x1"
ORIGINAL_SHA="ceea9943cb7b0fd31331a7505089ac72bb06dc78c7e150589f0972d469cfa138"
SCHEMA_SHA="f15b2ef12fb9dca3e85e81651df7ff7d1aa047f348946d73a51973f734445e30"
REPLAY_SHA="fed5d3a539ad72c1e36b86257578995901adc714a191a7d6d8050b7f5ff4f3bf"
DECODER_SHA="a32f685a4040cb10f7028ef8280920c2eb6d85225c26f78e24217f9e5c686d2f"
APP_SHA="fef14903f17127f7ad5c143fd306a2a88e68270c4dcf858a472096154d1f1c02"
LIBRARY_SHA="9e05ca22b16c3fb68c6fb69bf8f4cff6446af84469529b597a0610513c554736"
BUILD_PINS={
    "observation.patch":"740a90af1352368e907a0aa8f1a4a2f5e96d46ff3686d31b1df570f9fe27552a",
    "source-manifest-before.json":"b004b855c0605f7b0f340d7b0bf30a240d46a3f75e7e229aa049cbc10877d490",
    "source-manifest-after.json":"b004b855c0605f7b0f340d7b0bf30a240d46a3f75e7e229aa049cbc10877d490",
    "build-receipt.log":"cdc82e5e658abbe7bd451e80a0bdd0bfbf8d2f60f4d9b77633d9e6d03e93e5a3",
    "build-artifact-hashes.txt":"76ec207dbf7ada77720e081affa6be68317ac4d57ee81c66e5636a57d4bfee1c",
    "measured-runner.sh":"ba90de74c22b6e4767d8825747314c43e2365d1553efa2e7cd2c2c4b507c9dd1",
}

def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()

def ident(p):
    p=Path(p);return {"path":str(p),"sha256":sha(p),"size":p.stat().st_size}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("off_tag");ap.add_argument("on_tag");ap.add_argument("output")
    a=ap.parse_args()
    for tag in (a.off_tag,a.on_tag):assert "/" not in tag and tag not in ("",".","..")
    out=Path(a.output);assert not out.exists()
    assert sha(ORIGINAL/"command.json")==ORIGINAL_SHA
    original=json.loads((ORIGINAL/"command.json").read_text())
    assert original["status"]=="encoded" and original["returncode"]==0
    artifacts={"schema":ident(OBS/"schema.json"),"original_command":ident(ORIGINAL/"command.json")}
    assert artifacts["schema"]["sha256"]==SCHEMA_SHA
    for name,h in BUILD_PINS.items():
        artifacts["build_"+name]=ident(OBS/name)
        assert artifacts["build_"+name]["sha256"]==h,name
    canonical_build={}
    for line in (OBS/"build-artifact-hashes.txt").read_text().splitlines():
        h,p=line.split(maxsplit=1);p=p.lstrip("*")
        assert sha(p)==h,p
        canonical_build[p]=h
    schema=json.loads((OBS/"schema.json").read_text());names=schema["kinds"]
    assert len(names)==len(set(names))==34
    decoder_path=ORIGINAL/"decoder-validation/decoder-validation.json"
    decoder=json.loads(decoder_path.read_text())
    assert decoder["status"]=="admitted" and decoder["all336_allplanes_app_dav1d_libaom_NVDEC_exact"]
    assert decoder["inputs"]["command.json"]["sha256"]==ORIGINAL_SHA
    assert decoder["source_script"]["sha256"]==DECODER_SHA
    assert sha(decoder["source_script"]["path"])==DECODER_SHA
    artifacts["decoder"]=ident(decoder_path)
    runs=[]
    for mode,tag in (("off",a.off_tag),("on",a.on_tag)):
        d=OBS/"runs"/tag;r=json.loads((d/"command.json").read_text())
        assert r["case"]=="e05-1440" and r["tag"]==tag and r["mode"]==mode
        assert r["status"]=="neutral" and r["returncode"]==0
        assert r["exact_unmodified_ivf"] and r["exact_unmodified_reconstruction"]
        assert r["original_receipt"]["sha256"]==ORIGINAL_SHA
        assert r["identity_before"]==r["identity_after"]
        for p,h in r["identity_after"].items():assert sha(p)==h
        assert r["script"]["sha256"]==r["source_script"]["sha256"]==REPLAY_SHA
        assert r["app"]["sha256"]==APP_SHA and r["library"]["sha256"]==LIBRARY_SHA
        assert r["build_artifacts"]==canonical_build
        assert r["patch"]==artifacts["build_observation.patch"]
        assert r["schema"]==artifacts["schema"]
        assert r["build_receipt"]==artifacts["build_build-receipt.log"]
        assert r["stats"]["sha256"]==original["stats"]["sha256"]
        for key in ("script","source_script","app","library","stats","log","patch","schema","build_receipt"):
            assert ident(r[key]["path"])==r[key], key
            artifacts[mode+"_"+key]=r[key]
        for key,parent_key in (("out.ivf","ivf_output"),("recon.yuv","recon")):
            assert ident(d/key)==r[key]
            assert r[key]["sha256"]==original[parent_key]["sha256"]
            artifacts[mode+"_"+key]=r[key]
        expected=list(original["commands"]["pass2"]);expected[6]=r["app"]["path"]
        for flag,value in {"--stats":str(d/"pass.stats"),"-b":str(d/"out.ivf"),"-o":str(d/"recon.yuv")}.items():
            expected[expected.index(flag)+1]=value
        assert expected==r["argv"]
        assert r["environment"]["LD_LIBRARY_PATH"]==str(OBS/"build/bin")
        assert ("SVT_PSYEX_OBS_FD" in r["environment"])==(mode=="on")
        if mode=="on":
            assert ident(d/"observation.json")==r["observation"]
            artifacts["observation"]=r["observation"]
        else:assert not (d/"observation.json").exists()
        artifacts[mode+"_command"]=ident(d/"command.json");runs.append(r)
    assert runs[0]["app"]==runs[1]["app"] and runs[0]["library"]==runs[1]["library"]
    data=json.loads(Path(artifacts["observation"]["path"]).read_text())
    assert data["schema"]==3 and data["status"]=="complete"
    assert data["instances"]==1 and data["shape"]==[336,4,34]
    assert data["invalid"]==data["overflow"]==0
    config={
        "pass":2,"active_channel_count":1,"channel_id":0,"source_width":1920,"source_height":1080,
        "encoder_bit_depth":10,"encoder_color_format":1,"frame_rate_numerator":24,"frame_rate_denominator":1,
        "enc_mode":4,"tune":0,"scene_change_detection":0,"level_of_parallelism":1,
        "color_range":0,"color_primaries":1,"transfer_characteristics":1,"matrix_coefficients":1,
        "sharp_tx":1,"sharpness":1,"spy_rd":0,"hbd_mds":1,"complex_hvs":0,"noise_norm_strength":1,
        "noise_adaptive_filtering":0,"rate_control_mode":1,"pred_structure":2,
        "intra_period_length":239,"intra_refresh_type":2,"hierarchical_levels":4,
        "enable_adaptive_quantization":2,"enable_variance_boost":1,"variance_boost_strength":2,
        "variance_octile":5,"variance_boost_curve":0,"enable_qm":1,"min_qm_level":4,"max_qm_level":15,
        "min_chroma_qm_level":10,"max_chroma_qm_level":15,"enable_tf":1,"tf_strength":1,"kf_tf_strength":1,
        "enable_overlays":0,"enable_dlf_flag":1,"cdef_level":-1,"enable_restoration_filtering":-1,
        "film_grain_denoise_strength":0,"film_grain_denoise_apply":0,
        "target_bit_rate":original["request_kbps"]*1000,"psy_rd":1.0,"qp_scale_compress_strength":1.0,
    }
    assert data["config"]==config, {k:(config.get(k),data["config"].get(k)) for k in set(config)|set(data["config"]) if config.get(k)!=data["config"].get(k)}
    counts=data["counts"];assert len(counts)==336
    totals={k:0 for k in names};per_picture=[];per_stage=[{k:0 for k in names} for _ in range(4)]
    for p,stages in enumerate(counts):
        assert len(stages)==4
        aggregate={k:0 for k in names}
        for stage,values in enumerate(stages):
            assert len(values)==34 and all(type(v) is int and 0<=v<2**64 for v in values)
            c=dict(zip(names,values))
            assert c["PO_OPT_ENTER"]==c["PO_OPT_EARLY_RATE"]+c["PO_OPT_EARLY_EOB"]+c["PO_OPT_COMPLETE"]
            assert c["PO_OPT_ZERO_WEIGHT"]<=c["PO_OPT_GUARD"]<=c["PO_OPT_LUMA"]<=c["PO_OPT_ENTER"]
            for stem in ("FAST","TX_PRED","TX_RECON","FULL_PRED","FULL_RECON"):
                assert c["PO_"+stem+"_NONZERO"]<=c["PO_"+stem+"_CALL"]
            assert c["PO_TX_PRED_CALL"]==c["PO_TX_RECON_CALL"]
            assert c["PO_FULL_PRED_CALL"]==c["PO_FULL_RECON_CALL"]==c["PO_FULL_SPATIAL"]
            for stem in ("ZERO","SKIPMODE"):
                assert c["PO_"+stem+"_CHOICE"]<=c["PO_"+stem+"_COMPARE"]
                assert c["PO_"+stem+"_SPATIAL_COMPARE"]<=c["PO_"+stem+"_COMPARE"]
            assert c["PO_MODE_INTER"]+c["PO_MODE_INTRA"]==c["PO_MODE_CALL"]<=c["PO_MODE_CANDIDATES"]
            for k in ("HBD","SPATIAL","SKIP","COEFF"):assert c["PO_MODE_"+k]<=c["PO_MODE_CALL"]
            for k,v in c.items():aggregate[k]+=v;totals[k]+=v;per_stage[stage][k]+=v
        per_picture.append(aggregate)
    seen=[i for i,c in enumerate(per_picture) if c["PO_MODE_CALL"]]
    assert seen==list(range(336))
    # These are delivery criteria, not texture/quality thresholds. No winning
    # coefficient, pixel or ROI is attributed to a specific psy term.
    target=per_picture[216]
    required=["PO_OPT_ZERO_WEIGHT","PO_FULL_PRED_NONZERO","PO_FULL_RECON_NONZERO",
              "PO_ZERO_SPATIAL_COMPARE","PO_SKIPMODE_SPATIAL_COMPARE","PO_MODE_HBD","PO_MODE_SPATIAL"]
    delivery=all(target[k]>0 for k in required)
    result={"status":"admitted","case":"e05-1440","tag":"psyex-1x1","policy_delivery_pass":delivery,
        "original_receipt":ident(ORIGINAL/"command.json"),"unmodified_ivf":original["ivf_output"],
        "off_receipt":artifacts["off_command"],"on_receipt":artifacts["on_command"],
        "reviewed_replay_sha256":REPLAY_SHA,"script":ident(__file__),"postprocessed_static_config":config,
        "unresolved_auto_config_fields":["cdef_level","enable_restoration_filtering"],
        "counter_names":names,"totals":totals,"per_stage":per_stage,"per_picture":per_picture,
        "mode_selection_pictures":seen,"target_input_picture":216,"target_scored_frame":120,
        "target_required_nonzero_counters":required,"target_counters":target,
        "artifacts":artifacts,"decoder_validation":ident(decoder_path),
        "scope":"Neutral aggregate search-route delivery. Final partition selection and survival are unobserved. Selected candidates may lose partition search; counts are not pixels/bits and do not pair nonzero psy to a particular final decision.",
        "playback_observed":False}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"status":result["status"],"policy_delivery_pass":delivery,"seen_pictures":len(seen),"target":target}))

if __name__=="__main__":main()
