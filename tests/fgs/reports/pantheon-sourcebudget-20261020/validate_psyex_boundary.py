#!/usr/bin/env python3
"""Admit byte-neutral R9 boundary trace; no repair or quantizer inference."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import numpy as np

ROOT = Path(os.environ.get("PANTHEON_SOURCEBUDGET_ROOT",
                         "/tmp/downloads/codex-work/pantheon-sourcebudget-20261020"))
OBS = ROOT / "parent/psyex-boundary-r9"
ORIGINAL = ROOT / "worker/psyex-r8/runs/e05-1440/psyex-1x1"
FIXTURE = ROOT / "fixtures/e05-1440"
W, H, FRAME_BYTES = 1920, 1080, 1920 * 1080 * 3
ORIGINAL_SHA = "ceea9943cb7b0fd31331a7505089ac72bb06dc78c7e150589f0972d469cfa138"
REPLAY_SHA = "77b5407e435e27ce1ddc888ac7ab01537171cda48bb9744251b118f99330300a"
BUILD_PINS = {
    "boundary.patch": "69c61c844532966496bc313cb2beaeb6d867bae5f93b5139c2774f4f0d069f3e",
    "schema.json": "c9f4cf3095d91ab280738aa8c9cd4f5d21326bbd98a895ab0d51e00c5676477a",
    "source-manifest-before.json": "12f345e1f738b97fd00d9b9b2978864c53df995ad7590374edc21d31004124ce",
    "source-manifest-after.json": "12f345e1f738b97fd00d9b9b2978864c53df995ad7590374edc21d31004124ce",
    "measured-runner.sh": "933ef9a3607a6e8e0b46f4bb1c31e0d885cac11590bf18b6ecc3ebd6bb54ca75",
}


def sha(p):
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ident(p):
    p = Path(p)
    return {"path": str(p), "sha256": sha(p), "size": p.stat().st_size}


def dump(p, data):
    Path(p).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def planes(raw, w=W, h=H):
    assert len(raw) == w * h * 3
    a = np.frombuffer(raw, dtype="<u2")
    assert int(a.max()) <= 1023
    n = w * h
    return [a[:n].reshape(h, w), a[n:n+n//4].reshape(h//2, w//2),
            a[n+n//4:].reshape(h//2, w//2)]


def pack(arrays):
    return b"".join(np.asarray(a, dtype="<u2").tobytes() for a in arrays)


def read_frame(path, n, total):
    assert Path(path).stat().st_size == total * FRAME_BYTES
    with Path(path).open("rb") as f:
        f.seek(n * FRAME_BYTES)
        raw = f.read(FRAME_BYTES)
    planes(raw)
    return raw


def unique_json(pairs):
    obj = {}
    for k, v in pairs:
        assert k not in obj, "duplicate JSON key"
        obj[k] = v
    return obj


def parse_trace(path):
    """Validate every attempt, exact sample ownership and terminal framing."""
    assert 64 < Path(path).stat().st_size <= 512 * 2**20
    generation = sequence = 0
    attempts, records, accepted, post, end = [], [], None, None, None
    inputs = [np.zeros((H, W), dtype="<u2"),
              np.zeros((H//2, W//2), dtype="<u2"), np.zeros((H//2, W//2), dtype="<u2")]
    masks = [np.zeros_like(a, dtype=np.uint8) for a in inputs]
    seen, sb_size, decode_order = set(), None, None
    with Path(path).open("rb") as f:
        while hdr := f.read(64):
            assert len(hdr) == 64 and end is None
            magic, version, typ, gen, picture, seq, nj, nb = struct.unpack("<8Q", hdr)
            assert (magic, version, picture, seq, gen) == (
                0x31594342504e5450, 1, 216, sequence, generation)
            assert 0 <= generation < 16 and typ in (1, 2, 3, 4)
            assert 0 < nj < 4096 and nb <= FRAME_BYTES
            meta = f.read(nj)
            assert len(meta) == nj
            m = json.loads(meta, object_pairs_hook=unique_json)
            assert type(m) is dict
            raw = f.read(nb)
            assert len(raw) == nb
            records.append({"sequence": seq, "type": typ, "generation": gen,
                            "metadata": m, "payload_sha256": hashlib.sha256(raw).hexdigest(),
                            "payload_bytes": nb})
            if typ == 1:
                assert accepted is None and post is None
                size = m["sb_size"]
                assert size in (64, 128)
                if sb_size is None:
                    sb_size = size
                assert sb_size == size
                x, y, w, h = (m[k] for k in ("x", "y", "width", "height"))
                assert all(type(v) is int for v in (x, y, w, h))
                assert 0 <= x < W and 0 <= y < H and x % size == y % size == 0
                assert (w, h) == (min(size, W-x), min(size, H-y))
                cols = (W+size-1)//size
                idx = (y//size)*cols+x//size
                assert m["sb_id"] == idx and idx not in seen
                assert (m["bit_depth"], m["planes"], m["origin_used"]) == (10, 3, [0, 0])
                assert len(m["strides"]) == 3 and m["strides"][0] >= w
                assert all(s >= w//2 for s in m["strides"][1:])
                seen.add(idx)
                for p, a in enumerate(planes(raw, w, h)):
                    sh = int(p != 0)
                    sl = np.s_[y >> sh:(y+h) >> sh, x >> sh:(x+w) >> sh]
                    assert not masks[p][sl].any()
                    masks[p][sl] += 1
                    inputs[p][sl] = a
            elif typ in (2, 3):
                assert sb_size is not None and all(np.all(a == 1) for a in masks)
                total = ((W+sb_size-1)//sb_size)*((H+sb_size-1)//sb_size)
                assert seen == set(range(total))
                assert (m["picture"], m["width"], m["height"], m["bit_depth"],
                        m["planes"], m["subsampling"], m["sb_size"],
                        m["sb_count"], m["sb_total_count"], m["sb_based_dlf"]) == (
                            216, W, H, 10, 3, [1, 1], sb_size, total, total, 0)
                assert m["do_recode"] in (0, 1) and m["dlf_enabled"] in (0, 1)
                assert m["frame_type"] in range(4)
                for k in ("show_frame", "showable_frame", "is_ref"):
                    assert m[k] in (0, 1)
                # SVT's member is a DPB slot, not the separately written flag.
                # Its active/inactive status is not captured by this trace.
                assert type(m["show_existing_frame"]) is int and 0 <= m["show_existing_frame"] < 8
                if decode_order is None:
                    decode_order = m["decode_order"]
                assert m["decode_order"] == decode_order
                assert len(m["origin"]) == 2 and all(v >= 0 and v % 2 == 0 for v in m["origin"])
                assert len(m["strides"]) == 3 and m["strides"][0] >= W+m["origin"][0]
                assert all(s >= (W+m["origin"][0])//2 for s in m["strides"][1:])
                assert len(m["buffer_dimensions"]) == 2
                assert m["buffer_dimensions"][0] >= W and m["buffer_dimensions"][1] >= H
                planes(raw)
                if typ == 2:
                    assert accepted is None and post is None
                    attempt = {"generation": generation, "metadata": m,
                               "coding_input": pack(inputs), "preloop": raw}
                    attempts.append(attempt)
                    if m["do_recode"]:
                        generation += 1
                        seen.clear()
                        for mask in masks:
                            mask.fill(0)
                    else:
                        accepted = attempt
                else:
                    assert accepted is not None and post is None and m["do_recode"] == 0
                    for k in ("decode_order", "order_hint", "frame_type", "show_frame",
                              "show_existing_frame", "showable_frame", "is_ref"):
                        assert m[k] == accepted["metadata"][k], k
                    post = raw
            else:
                assert nb == 0 and accepted is not None and post is not None
                assert m == {"status": "complete", "accepted_generation": generation,
                             "attempts": generation+1, "post_count": 1, "records_before_end": sequence}
                assert len(attempts) == generation+1
                end = m
            sequence += 1
    assert end is not None
    return attempts, post, records, end


def main():
    if not __debug__:
        raise RuntimeError("Do not disable admission assertions")
    ap = argparse.ArgumentParser()
    ap.add_argument("off_tag")
    ap.add_argument("on_tag")
    ap.add_argument("build_pins", type=Path)
    ap.add_argument("output", type=Path)
    a = ap.parse_args()
    for tag in (a.off_tag, a.on_tag):
        assert "/" not in tag and tag not in ("", ".", "..")
    assert not a.output.exists()
    artifacts = {}

    def bind(key, p, h=None):
        obj = ident(p)
        if h is not None:
            assert obj["sha256"] == h, key
        artifacts[key] = obj
        return obj

    bind("original_receipt", ORIGINAL/"command.json", ORIGINAL_SHA)
    original = json.loads((ORIGINAL/"command.json").read_text())
    assert original["status"] == "encoded" and original["returncode"] == 0
    for key in ("input", "ivf_output", "recon", "stats"):
        assert bind("original_"+key, original[key]["path"]) == original[key]
    for p, h in BUILD_PINS.items():
        bind("build_"+p, OBS/p, h)
    build_pins = json.loads(a.build_pins.read_text())
    bind("completed_build_pins", a.build_pins,
         "b103a2af7c3aabcba15158c04a71ff7668e2043799c76468f8b60cb3bba799a7")
    assert set(build_pins) == {"build-receipt.log", "build-artifact-hashes.txt",
                              "build/bin/SvtAv1EncApp", "build/bin/libSvtAv1Enc.so.3.0.2"}
    for p, h in build_pins.items():
        bind("build_"+p, OBS/p, h)
    assert (OBS/"build-receipt.log").read_text().endswith("exit_code=0\n")
    assert (OBS/"build-receipt.log").read_text().count("final_status=build_complete\n") == 1
    canonical_build = {}
    for line in (OBS/"build-artifact-hashes.txt").read_text().splitlines():
        h, p = line.split(maxsplit=1)
        p = p.lstrip("*")
        assert sha(p) == h and p not in canonical_build
        canonical_build[p] = h
    decoder = ORIGINAL/"decoder-validation/decoder-validation.json"
    bind("decoder_receipt", decoder, "7bf52faa5f6340d89a58fee99ebaf4912d051a0b837bc2c3907ba1c1c5f368ac")
    dec = json.loads(decoder.read_text())
    assert dec["status"] == "admitted" and dec["all336_allplanes_app_dav1d_libaom_NVDEC_exact"]
    assert dec["inputs"]["command.json"]["sha256"] == ORIGINAL_SHA
    for mode, tag in (("off", a.off_tag), ("on", a.on_tag)):
        d = OBS/"runs"/tag
        bind(mode+"_receipt", d/"command.json")
        r = json.loads((d/"command.json").read_text())
        assert (r["status"], r["mode"], r["tag"], r["returncode"], r["case"]) == (
            "neutral", mode, tag, 0, "e05-1440")
        assert r["exact_unmodified_ivf"] and r["exact_unmodified_reconstruction"]
        assert r["original_receipt"] == artifacts["original_receipt"]
        assert r["identity_before"] == r["identity_after"]
        for p, h in r["identity_after"].items():
            assert sha(p) == h
        assert r["script"]["sha256"] == r["source_script"]["sha256"] == REPLAY_SHA
        for key, path in (("app", "build/bin/SvtAv1EncApp"),
                          ("library", "build/bin/libSvtAv1Enc.so.3.0.2"),
                          ("patch", "boundary.patch"), ("schema", "schema.json"),
                          ("build_receipt", "build-receipt.log")):
            assert r[key] == artifacts["build_"+path], key
        assert r["build_artifacts"] == canonical_build
        assert r["stats"]["sha256"] == original["stats"]["sha256"]
        for key in ("script", "source_script", "stats", "log"):
            assert bind(mode+"_"+key, r[key]["path"]) == r[key]
        for key, parent_key in (("out.ivf", "ivf_output"), ("recon.yuv", "recon")):
            assert bind(mode+"_"+key, d/key) == r[key]
            assert r[key]["sha256"] == original[parent_key]["sha256"]
        expected = list(original["commands"]["pass2"])
        expected[6] = r["app"]["path"]
        for flag, value in {"--stats": str(d/"pass.stats"), "-b": str(d/"out.ivf"),
                            "-o": str(d/"recon.yuv")}.items():
            assert expected.count(flag) == 1
            expected[expected.index(flag)+1] = value
        assert expected == r["argv"]
        env = r["environment"]
        assert set(env) == ({"LD_LIBRARY_PATH", "SVT_PANTHEON_BOUNDARY_FD"} if mode == "on" else {"LD_LIBRARY_PATH"})
        assert env["LD_LIBRARY_PATH"] == str(OBS/"build/bin")
        if mode == "on":
            assert int(env["SVT_PANTHEON_BOUNDARY_FD"]) >= 3
            assert bind("trace", d/"boundary.bin") == r["observation"]
        else:
            assert not (d/"boundary.bin").exists()
    bind("source_raw", FIXTURE/"source.yuv",
         "ca3356ad056ee70ddb483acc2a4a0dac8ccd98d70b9096d8b4786d49a1f88fd3")
    bind("source_y4m", FIXTURE/"input10.y4m",
         "232abb5ffee869be4bedf682aa103c166eb473bb3fdad5daf28956cca60148d4")
    source = read_frame(FIXTURE/"source.yuv", 120, 240)
    assert hashlib.sha256(source).hexdigest() == "c2798d9c00f53bdbe7041575249b353a478a8f5557bc4dd5b61d9ae03f13ea12"
    with (FIXTURE/"input10.y4m").open("rb") as f:
        header = f.readline()
        assert b"W1920" in header and b"H1080" in header and b"F24:1" in header and b"C420p10" in header
        for n in range(217):
            assert f.readline() == b"FRAME\n"
            raw = f.read(FRAME_BYTES)
            assert len(raw) == FRAME_BYTES
        assert raw == source
    attempts, post, records, terminal = parse_trace(artifacts["trace"]["path"])
    assert post == read_frame(original["recon"]["path"], 216, 336)
    assert hashlib.md5(post).hexdigest() == dec["hashes"][216]
    a.output.mkdir(parents=True)
    stages = {}
    accepted = attempts[-1]
    for name, raw in (("original", source), ("coding_input", accepted["coding_input"]),
                      ("preloop", accepted["preloop"]), ("postloop", post)):
        p = a.output/(name+".yuv")
        p.write_bytes(raw)
        stages[name] = ident(p)
    attempt_summaries = []
    for attempt in attempts:
        row = {"generation": attempt["generation"], "metadata": attempt["metadata"]}
        for name in ("coding_input", "preloop"):
            raw = attempt[name]
            row[name+"_sha256"] = hashlib.sha256(raw).hexdigest()
            row[name+"_plane_sha256"] = [hashlib.sha256(p.tobytes()).hexdigest() for p in planes(raw)]
        attempt_summaries.append(row)
    dump(a.output/"records.json", records)
    bind("record_metadata", a.output/"records.json")
    result = {"status": "admitted", "case": "e05-1440", "input_frame": 216, "scored_frame": 120,
              "dimensions": [W, H], "pix_fmt": "yuv420p10le", "terminal": terminal,
              "all_attempts_exact_visible_coverage": True, "postloop_exact_admitted_R8_frame": True,
              "off_on_exact_original_IVF_and_recon": True, "attempts": attempt_summaries,
              "stages": stages, "artifacts": artifacts, "script": ident(__file__),
              "metadata_interpretation": {"show_existing_frame":
                  "Raw SVT DPB slot member, not the AV1 show_existing flag. Active status was not captured; may be inactive/stale. Not used to infer a bitstream event."},
              "scope": "Single-frame coding-input/preloop/postloop observation. No per-TU quantizer, search survival, repair or playback claim."}
    dump(a.output/"admission.json", result)
    print(json.dumps({"status": "admitted", "terminal": terminal, "stages": stages}))


if __name__ == "__main__":
    main()
