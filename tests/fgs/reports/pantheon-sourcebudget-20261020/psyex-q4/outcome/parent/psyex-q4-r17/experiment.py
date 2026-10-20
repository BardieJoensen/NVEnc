#!/usr/bin/env python3
"""One R16 fixed-choice native FP q4 diagnostic; no encoder or coded-bit claim."""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path("/tmp/downloads/codex-work/pantheon-sourcebudget-20261020")
REPORT = Path("/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020")
P = Path(__file__).resolve().parent
OBS = ROOT / "parent/psyex-tf0-r16-refine/r16-refine-tbr10042-observations"
R12 = ROOT / "parent/psyex-scalar-r12"
DC = ROOT / "worker/psyex-r17-q4/dc-evidence/v4"
W, H = 1920, 1080
BOXES = {"shirt": (1200, 650, 200, 100), "background": (950, 50, 250, 180),
         "face": (160, 600, 500, 480)}
BEFORE = {}


def ident(path):
    path = Path(path).resolve()
    with path.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()
    return dict(path=str(path), sha256=digest, size=path.stat().st_size)


def remember(path, digest=None):
    row = ident(path)
    if digest is not None:
        assert row["sha256"] == digest, (path, row, digest)
    prior = BEFORE.setdefault(row["path"], row)
    assert prior == row, (path, "changed during preparation")
    return Path(row["path"])


def exact(row):
    path = remember(row["path"], row["sha256"])
    assert BEFORE[str(path)] == row, row
    return path


def read(path):
    return json.loads(Path(path).read_text())


def write(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def module(path, name):
    path = remember(path)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def crop(array, box):
    x, y, w, h = box
    return array[y:y+h, x:x+w]


def finish_inputs():
    after = {p: ident(p) for p in BEFORE}
    assert after == BEFORE, "dependency mutation"
    return after


def prepare():
    remember(__file__)
    remember(P / "README.md")
    remember(sys.executable)
    remember(REPORT / "ROUND17_FIXED_Q4_CONTRACT.md",
             "c207781f7fd77d488df17a9892988c78d660cf88c3ab8216209a91c73ab29f8c")
    ad = read(remember(OBS / "admitted/admission.json",
                      "a86db1bcc3e4ff49b8e0aa66dfc601ac8bc7b67bb4415b3886263df7daaf50ab"))
    assert ad["status"] == "admitted" and ad["case"] == "e05-1440"
    assert ad["script"]["sha256"] == "fd190fae6a20aa3cd2efd06e6d6fc9c32471d602272a214b7168667aab511cbb"
    for key in ("actual_committed_owner", "all336_exact",
                "all_traced_roi_owners_source_predictor_preloop_exact",
                "all_traced_positive_units_dq_iqm_exact_with_all_traced_eob_q_exact"):
        assert ad[key] is True, key
    for key in ("script", "trace", "token_manifest", "decoder_admission", "original_receipt"):
        exact(ad[key])
    assert ad["original_receipt"]["sha256"] == "00bb9243453fb55f1c878842e2ecfd3760f8403144e1e5b507530477a03ef497"
    command = read(ad["original_receipt"]["path"])
    assert command["status"] == "encoded" and command["returncode"] == 0
    binding = read(exact(ad["artifacts"]["syntax_binding"]))
    assert binding["encode_receipt"] == ad["original_receipt"]
    target = binding["target_coded_event"]
    assert (target["event_index"], target["coded_ordinal"], target["packet_index"],
            target["packet_event_index"]) == (314, 210, 209, 1)
    dc = read(remember(DC / "result.json",
                      "beca735ea45536e43c6230efd12289d03d5a0c4502b1f23e0a895ec5416785f3"))
    remember(DC / "extract_dc_evidence_v4.py",
             "e1085f5817b3c7562f12e388d2dfd54a45876c3e7034edddd9c8fa02f6f9b7a8")
    remember(DC / "execution_v4.json",
             "eac7cff03af51e340b7f14ce1263830b20d88db93e52bd1f8075ce9ddfa914ca")
    assert dc["status"] == "admitted"
    for row in dc["inputs"].values():
        exact(row)
    assert dc["inputs"]["binding_result"] == ad["artifacts"]["syntax_binding"]
    assert dc["target"]["obu"] == target["obu"]
    assert dc["target"]["event_index"] == 314 and dc["target"]["coded_ordinal"] == 210
    assert dc["target"]["delta_q_y_dc"]["delta_coded"] == 0
    assert dc["target"]["delta_q_y_dc"]["effective_delta"] == 0
    lines = Path(dc["inputs"]["trace_log"]["path"]).read_text().splitlines()
    first = dc["target"]["frame_header_start_line_1based"]
    end = dc["target"]["frame_header_end_exclusive_1based"]
    block = lines[first-1:end-1]
    assert block == dc["target"]["header_text_lines"]
    assert lines[first-1].endswith(" Frame Header") and lines[end-1].endswith(" Frame Header")
    assert not any(line.endswith(" Frame Header") for line in block[1:])
    delta = dc["target"]["delta_q_y_dc"]
    assert delta["log_line_1based"] == delta["splitlines_index_zero_based"]+1
    assert lines[delta["splitlines_index_zero_based"]] == delta["text"]

    build = read(remember(R12 / "build-2/receipt.json",
                         "4b56e9cbd1450f68ec42d02a70d6db2e082db065c6314f34ef17443ef6cb7df5"))
    assert build["status"] == "complete" and len(build["commands"]) == 2
    for command in build["commands"]:
        assert command["returncode"] == 0
        exact(command["log"])
    inputs = read(exact(build["inputs_before"]))
    assert inputs == read(exact(build["inputs_after"])) and len(inputs) == 275
    for row in inputs:
        exact(row)
    for key in ("source_manifest", "library", "object"):
        exact(build[key])
    assert build["library"]["sha256"] == "07fe2554623523d8e6dfe5218d94a89cdb2437bb2221123a86678090af6f2228"
    remember(R12 / "native.c", "8f1cf5b69700e1a1b2d26d8bf29a0cb87cfe2f2e0b2351881be20106731934fc")
    remember(R12 / "experiment.py", "87eb15f8a7c082bb875f91edb790ed66a8e592db9d64bc5f554943040f705ee2")
    parser_path = remember(ROOT / "parent/psyex-real-r15/parsers.py",
                           "45f11c246037e1a58a2762235a62db9a0bcb71e85fe992cfcc35897fa24983e3")
    analyze_path = remember(ROOT / "parent/psyex-coeff-r11/analyze.py",
                            "44b8037c2a922b7e893cd66c8488f3683c45b8859400ff6b082bd0910286f64e")
    unit_path = remember(ROOT / "worker/decoder-r10-analysis/analyze_decoder_units.py",
                         "d10bfb16859ad02f59ba876b7890f591fee592b690d4c65a6aa0f043a7ae3cb3")
    helper_path = remember(REPORT / "analyze_psyex_boundary.py",
                           "1027e9a0ec2a5f3b12a6aa908b97cad185df615fe48852a8acbe4daf5fb22ea3")
    inherited = read(remember(ROOT / "parent/psyex-boundary-r9/analysis-1.json",
                             "b2d4a19ac93eeab29cb78870cea45f03165f7741f22584955081498553ed5bc5"))
    for row in inherited["metric_helpers"].values():
        exact(row)
    # The legacy helper imports high_pass from this underlying source.
    remember(REPORT.parents[1] / "matched_rate_sweep.py",
             "024ef20a46f32a8320967b354ac6682fe09be13897b49cfd97b3deb7e4ec3196")
    parser = module(parser_path, "r17_parser")
    analyze = module(analyze_path, "r17_analyze")
    unit = module(unit_path, "r17_unit")
    helper = module(helper_path, "r17_boundary")
    native_api = module(R12 / "experiment.py", "r17_native_api")
    assert ident(helper.analyze_mod.__file__) == inherited["metric_helpers"]["analyze_py"]
    tokens, terminal = parser.parse_coeff(Path(ad["trace"]["path"]), target["coded_ordinal"])
    assert terminal == ad["terminal"] and len(tokens) == ad["tokens"] == 2870
    joins = read(ad["token_manifest"]["path"])
    joined = {row["token"]: row for row in joins}
    assert len(joined) == len(joins) == len(tokens) and set(joined) == set(tokens)
    for key, t in tokens.items():
        row = joined[key]
        for field in ("begin", "info", "end", "commit", "payload_offsets"):
            assert row.get(field) == t.get(field), (key, field)
        stages = [{k: v for k, v in s.items() if k not in ("q", "dq", "inverse")}
                  for s in t["stages"]]
        assert row["stages"] == stages
        if not t["stages"]:
            assert t.get("info") is None and t["end"]["eob"] == 0
            assert np.array_equal(t["predictor"], t["reconstruction"])
        else:
            assert t["stages"][0]["stage"] == "scalar_fp"
            assert t["info"]["depth"] == 10 and t["info"]["seg_delta"] == 0
            assert np.array_equal(t["stages"][-1]["inverse"], t["reconstruction"])
    invoked = {k: t for k, t in tokens.items() if t["stages"]}
    assert len(invoked) == 2169 and len(tokens)-len(invoked) == 701
    assert sum(t["end"]["eob"] == 0 for t in invoked.values()) == 39
    assert sum(t["end"]["eob"] > 0 for t in tokens.values()) == ad["positive_units"] == 2130
    dec = read(ad["decoder_admission"]["path"])
    refs = {k: unit.load_luma(exact(row)) for k, row in ad["source_boundaries"].items()}
    refs["predictor"] = unit.load_luma(exact(dec["artifacts"]["predictor"]))
    assert np.array_equal(refs["original"], refs["coding_input"])
    frames, covered = analyze.make_mosaics(tokens)
    assert np.array_equal(frames["predictor"][covered], refs["predictor"][covered])
    assert np.array_equal(frames["final"][covered], refs["preloop"][covered])
    for box in BOXES.values():
        assert crop(covered, box).all()
    return ad, dc, tokens, joined, invoked, frames, covered, refs, analyze, unit, helper, native_api, build


def quant_tables(native, api, q, delta):
    table = np.zeros((3, 8), dtype="<i2")
    assert native.lib.rp_fp_tables(q, delta, api.ptr(table, "<i2")) == 0
    return table


def population_metrics(ref, raw, images, mask, helper):
    """Legacy masked descriptors use 3x3 valid support and pair-valid ACF."""
    count = int(mask.sum())
    support = helper.analyze_mod.minimum_filter(mask.astype(np.uint8), size=3,
                                               mode="constant")[1:-1, 1:-1].astype(bool)
    pair_h = int((support[:, :-1] & support[:, 1:]).sum())
    pair_v = int((support[:-1, :] & support[1:, :]).sum())
    base = helper.analyze_mod.masked(ref, ref, mask)
    result = dict(pixels=count, hf_pixels=int(support.sum()), horizontal_pairs=pair_h,
                  vertical_pairs=pair_v, original_masked=base, stages={})
    for name, image in images.items():
        vs_original = float(np.square(image[mask]-ref[mask]).sum())
        vs_raw = float(np.square(image[mask]-raw[mask]).sum())
        desc = helper.analyze_mod.masked(ref, image, mask)
        for key in ("hf_sigma", "acf1"):
            x, y = desc.get(key), base.get(key)
            desc[key+"_abs_error"] = abs(x-y) if x is not None and y is not None else None
        result["stages"][name] = dict(sse_original=vs_original, sse_raw=vs_raw,
            mse_original=vs_original/count if count else None,
            mse_raw=vs_raw/count if count else None, masked=desc)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--preflight", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    receipt = dict(status="prepared", argv=sys.argv, started_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    start = time.monotonic()
    try:
        (ad, dc, tokens, joins, invoked, frames, covered, refs, analyze, unit,
         helper, api, build) = prepare()
        receipt["inputs_before"] = dict(BEFORE)
        write(args.out / "receipt.json", receipt)
        counts = dict(tokens=2870, invoked=2169, uninvoked=701, positive_eob=2130,
                      invoked_zero_eob=39)
        if args.preflight:
            receipt.update(status="preflight_pass", counts=counts, native_loaded=False,
                           inputs_after=finish_inputs())
            return
        native = api.Native(Path(build["library"]["path"]))
        baseline, q4, tables = {}, {}, {}
        # Complete every baseline control before starting the novel q4 arm.
        for key, t in invoked.items():
            z, info = t["begin"], t["info"]
            assert info["actual_qindex"] > 4
            n = z["n"]
            assert n == len(t["raw"]) == len(t["scan"]) == len(t["iscan"]) <= 1024
            assert n == min(z["w"], 32)*min(z["h"], 32)
            assert t["predictor"].shape == t["raw_inverse"].shape == (z["h"], z["w"])
            fp = quant_tables(native, api, info["actual_qindex"], 0)
            assert np.array_equal(fp, t["tables"][[0, 1, 6]])
            tables[str(info["actual_qindex"])] = fp.tolist()
            b = native.paired(t, 0, t["tables"])
            assert b["eob"] == t["stages"][0]["eob"]
            for field in ("q", "dq", "inverse"):
                assert np.array_equal(b[field], t["stages"][0][field]), (key, field)
            raw_c = native.inverse(t, t["raw"], t["raw_eob"], 0)
            raw_rt = native.inverse(t, t["raw"], t["raw_eob"], 1)
            assert np.array_equal(raw_c, raw_rt) and np.array_equal(raw_rt, t["raw_inverse"])
            baseline[key] = b
        controls = dict(status="exact", counts=counts, runtime_cpu_flags=native.flags,
            dc_evidence=ident(DC / "result.json"), dc_delta=0, native_current_tables=tables,
            baseline_c_runtime_capture_exact=2169, raw_c_runtime_capture_exact=2169)
        write(args.out / "baseline-control.json", controls)
        new_rows = quant_tables(native, api, 4, 0)
        for key, t in invoked.items():
            table = t["tables"].copy()
            table[[0, 1, 6]] = new_rows
            assert np.array_equal(table[[2, 3, 4, 5]], t["tables"][[2, 3, 4, 5]])
            q4[key] = native.paired(t, 0, table)

        frames["q4"] = frames["scalar"].copy()
        invmask = np.zeros((H, W), bool)
        txmap = np.full((H, W), -1, np.int16)
        for key, t in tokens.items():
            z = t["begin"]
            x, y, w, h = (z[k] for k in ("x", "y", "w", "h"))
            vh = min(h, H-y)
            sl = np.s_[y:y+vh, x:x+w]
            txmap[sl] = z["tx"]
            if key in invoked:
                invmask[sl] = True
                frames["q4"][sl] = q4[key]["inverse"][:vh].astype(np.float64)/4
        assert np.isfinite(frames["q4"][covered]).all()
        assert np.array_equal(frames["q4"][covered & ~invmask], frames["predictor"][covered & ~invmask])
        stages = {"original": refs["original"], "raw": frames["raw_executed"],
                  "scalar": frames["scalar"], "final": frames["final"], "q4": frames["q4"]}
        rois = {}
        for name, box in BOXES.items():
            images = {k: crop(v, box) for k, v in stages.items()}
            ref, raw = images["original"], images["raw"]
            valid, inv, tx = crop(covered, box), crop(invmask, box), crop(txmap, box)
            assert valid.all()
            whole = {k: analyze.descriptor(unit, helper, ref, v) for k, v in images.items()}
            masks = {"all": valid, "invoked": inv, "uninvoked": ~inv}
            pops = {k: population_metrics(ref, raw, images, mask, helper) for k, mask in masks.items()}
            strata = {}
            for pop in ("invoked", "uninvoked"):
                strata[pop] = {}
                for t in sorted(np.unique(tx[masks[pop]]).tolist()):
                    mask = masks[pop] & (tx == t)
                    strata[pop][str(t)] = population_metrics(ref, raw, images, mask, helper)
                assert sum(v["pixels"] for v in strata[pop].values()) == pops[pop]["pixels"]
                for stage in images:
                    for metric in ("sse_original", "sse_raw"):
                        assert sum(v["stages"][stage][metric] for v in strata[pop].values()) == pops[pop]["stages"][stage][metric]
            for stage in images:
                for metric in ("sse_original", "sse_raw"):
                    assert pops["all"]["stages"][stage][metric] == sum(pops[p]["stages"][stage][metric] for p in ("invoked", "uninvoked"))
            rois[name] = dict(xywh=box, whole=whole, populations=pops, transform_strata=strata)

        arrays, rows = {}, []
        co = po = 0
        for key, t in invoked.items():
            z = t["begin"]
            n, pixels = z["n"], z["w"]*z["h"]
            rows.append(dict(token=key, coefficient_offset=co, pixel_offset=po, n=n,
                pixels=pixels, native_wh=[z["w"], z["h"]], tx=z["tx"], type=z["type"],
                actual_qindex=t["info"]["actual_qindex"], q4_qindex=4, dc_delta=0,
                trace_payload_offsets=t["payload_offsets"], unit=joins[key]["unit"]))
            co += n
            po += pixels
        for arm, output in (("baseline", baseline), ("q4", q4)):
            for key in ("q", "dq", "inverse"):
                arrays[arm+"_"+key] = np.concatenate([output[k][key].ravel() for k in invoked])
                assert len(arrays[arm+"_"+key]) == (po if key == "inverse" else co)
            arrays[arm+"_eob"] = np.array([output[k]["eob"] for k in invoked], dtype="<u2")
        arrays["raw_inverse"] = np.concatenate([t["raw_inverse"].ravel() for t in invoked.values()])
        arrays["token_ids"] = np.array(list(invoked), dtype="<u8")
        assert len(arrays["raw_inverse"]) == po and len(arrays["token_ids"]) == 2169
        arrays["q4_fp_rows"] = new_rows
        np.savez_compressed(args.out / "native-arrays.npz", **arrays)
        np.savez_compressed(args.out / "mosaics.npz", **stages, covered=covered,
                            invoked=invmask, tx=txmap, predictor=frames["predictor"])
        write(args.out / "tokens.json", rows)
        geometry = {}
        for t in tokens.values():
            z = t["begin"]
            wh = [z["w"], z["h"]]
            assert geometry.setdefault(str(z["tx"]), wh) == wh
        result = dict(status="complete", scope="single-frame fixed-choice q4 diagnostic; no coded bits, filtering, feedback, full-window or playback claim",
            counts=counts, q4_c_runtime_exact=2169, controls=ident(args.out / "baseline-control.json"),
            arrays=ident(args.out / "native-arrays.npz"), mosaics=ident(args.out / "mosaics.npz"),
            tokens=ident(args.out / "tokens.json"), trace=ad["trace"], token_manifest=ad["token_manifest"],
            rois=rois, native_wh_by_tx=geometry,
            inputs_before=dict(BEFORE), inputs_after=finish_inputs())
        write(args.out / "result.json", result)
        receipt.update(status="complete", result=ident(args.out / "result.json"),
                       inputs_after=result["inputs_after"])
    except BaseException as e:
        receipt.update(status="failed", error=repr(e), inputs_before=dict(BEFORE))
        raise
    finally:
        receipt["ended_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        receipt["seconds"] = time.monotonic()-start
        write(args.out / "receipt.json", receipt)


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
