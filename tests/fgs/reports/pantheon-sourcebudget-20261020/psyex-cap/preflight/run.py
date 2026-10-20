#!/usr/bin/env python3
"""One bounded R18 pass: neutrality, fresh stats, real cap, or observer replay."""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REPORT = Path("/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020")
R16 = ROOT / "worker/psyex-r16-calibration-refine"
ORIGINAL = R16 / "runs/e05-1440/r16-refine-tbr10042/command.json"
ORIGINAL_SHA = "00bb9243453fb55f1c878842e2ecfd3760f8403144e1e5b507530477a03ef497"
LINEAGE = R16 / "encode_refine.py"
LINEAGE_SHA = "5804a1a5985d0676975abe28fba2d8c7a8d6af71c2f70d39dab11436bf2941e4"
CONTRACT = REPORT / "ROUND18_ABSOLUTE_CAP_CONTRACT.md"
CONTRACT_SHA = "97d68ee39c6ad1922c1025143583fffc02d480b3370f4aaa1c58817029f7b4bf"
FRAME_BYTES = 1920 * 1080 * 3


def ident(path):
    path = Path(path).resolve()
    with path.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()
    return dict(path=str(path), size=path.stat().st_size, sha256=digest)


def verify(row):
    assert ident(row["path"]) == row, row["path"]


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read_receipt(path, digest, mode):
    assert path and digest and ident(path)["sha256"] == digest
    obj = json.loads(Path(path).read_text())
    assert obj["status"] == "complete" and obj["returncode"] == 0
    assert obj["mode"] == mode and obj["identity_before"] == obj["identity_after"]
    assert obj["contract"]["sha256"] == CONTRACT_SHA
    assert obj["script"] == ident(__file__), "prerequisite producer is not this reviewed runner"
    assert obj["original_receipt"] == ident(ORIGINAL)
    original = json.loads(ORIGINAL.read_text())
    assert obj["case"] == "e05-1440" and obj["request_kbps"] == 10042
    assert obj["settings"] == original["settings"]
    assert obj["input"] == original["input"] and obj["validity"] == original["validity"]
    assert obj["source_mbps"] == original["source_mbps"]
    pins = json.loads(Path(obj["pins"]["path"]).read_text())
    verify(obj["pins"])
    folder = Path(path).resolve().parent
    template = list(original["commands"]["pass1" if mode == "pass1" else "pass2"])
    template[6] = pins["app"]["path"]
    for flag, name in (("--stats", "pass.stats"), ("-b", "out.ivf")):
        template[template.index(flag) + 1] = str(folder / name)
    if mode != "pass1":
        template[template.index("-o") + 1] = str(folder / "recon.yuv")
    assert obj["argv"] == template, "prerequisite command differs from frozen policy"
    expected_env = {"LD_LIBRARY_PATH": str(Path(pins["library"]["path"]).parent)}
    if mode == "cap":
        expected_env["SVT_PANTHEON_R18_CAP"] = "1"
    assert obj["environment"] == expected_env
    assert obj["outputs"]["pass.stats"]["sha256"] == original["stats"]["sha256"]
    if mode == "baseline":
        assert obj["exact_r16_ivf_and_all336_reconstruction"] is True
        assert obj["outputs"]["out.ivf"]["sha256"] == original["ivf_output"]["sha256"]
        assert obj["outputs"]["recon.yuv"]["sha256"] == original["recon"]["sha256"]
    elif mode == "cap":
        prior = read_receipt(obj["parent"]["path"], obj["parent"]["sha256"], "pass1")
        base = read_receipt(obj["control"]["path"], obj["control"]["sha256"], "baseline")
        assert prior["pins"] == base["pins"] == obj["pins"]
    for row in obj["identity_after"]:
        verify(row)
    for row in obj["outputs"].values():
        verify(row)
    return obj


def ivf_packets(path):
    packets = []
    with Path(path).open("rb") as f:
        header = f.read(32)
        assert len(header) == 32 and header[:4] == b"DKIF"
        assert struct.unpack_from("<HH", header, 12) == (1920, 1080)
        assert struct.unpack_from("<II", header, 16) == (24, 1)
        assert struct.unpack_from("<I", header, 24)[0] == 336
        for _ in range(336):
            packet = f.read(12)
            assert len(packet) == 12
            size, pts = struct.unpack("<IQ", packet)
            assert size > 0 and len(f.read(size)) == size
            packets.append(dict(pts=pts, bytes=size))
        assert not f.read(1)
    assert [x["pts"] for x in packets] == list(range(336))
    return dict(packets=packets,
                full_mbps=sum(x["bytes"] for x in packets) * 8 / 14 / 1e6,
                scored_mbps=sum(x["bytes"] for x in packets[96:336]) * 8 / 10 / 1e6,
                scope="IVF coded packet payload; remux packet accounting is separately required.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["baseline", "pass1", "cap", "trace"])
    ap.add_argument("tag")
    ap.add_argument("pins", type=Path)
    ap.add_argument("pins_sha")
    ap.add_argument("--control", type=Path)
    ap.add_argument("--control-sha")
    ap.add_argument("--parent", type=Path)
    ap.add_argument("--parent-sha")
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.tag)
    for name in ("LD_LIBRARY_PATH", "LD_PRELOAD", "LD_AUDIT"):
        assert not os.environ.get(name), name
    assert not any(k.startswith(("SVT_PANTHEON_", "SVT_PSYEX_")) for k in os.environ)
    assert shutil.disk_usage(ROOT).free >= 160 * 2**30
    assert ident(CONTRACT)["sha256"] == CONTRACT_SHA
    assert ident(ORIGINAL)["sha256"] == ORIGINAL_SHA
    assert ident(LINEAGE)["sha256"] == LINEAGE_SHA
    spec = importlib.util.spec_from_file_location("r18_lineage", LINEAGE)
    lineage = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lineage)
    original, ancestors = lineage.validate_chain(ORIGINAL, ORIGINAL_SHA)
    assert original["status"] == "encoded" and original["returncode"] == 0
    assert original["request_kbps"] == 10042
    assert original["settings"]["--enable-tf"] == "0"
    assert original["identity_before"] == original["identity_after"]
    assert ident(args.pins)["sha256"] == args.pins_sha
    pins = json.loads(args.pins.read_text())
    assert pins["status"] == "build_complete" and pins["returncode"] == 0
    pinned_files = [v for v in pins.values() if isinstance(v, dict) and {"path", "sha256", "size"} <= v.keys()]
    for row in pinned_files:
        verify(row)
    assert pins["source_manifest"]["sha256"] == pins["manifest_before"]["sha256"] == pins["manifest_after"]["sha256"]
    source = Path(pins["source_root"])
    for rel, size, digest in json.loads(Path(pins["source_manifest"]["path"]).read_text()):
        observed = ident(source / rel)
        assert (observed["size"], observed["sha256"]) == (size, digest), rel
    app = Path(pins["app"]["path"])
    lib = Path(pins["library"]["path"])
    for name in ("input", "stats", "stats_snapshot", "ivf_output", "recon", "validity"):
        verify(original[name])
    assert original["stats"]["sha256"] == original["stats_snapshot"]["sha256"]
    control = parent = None
    if args.mode in ("cap", "trace"):
        control = read_receipt(args.control, args.control_sha, "baseline")
        assert control["pins"]["sha256"] == args.pins_sha
        parent = read_receipt(args.parent, args.parent_sha, "pass1" if args.mode == "cap" else "cap")
        assert parent["pins"]["sha256"] == args.pins_sha
    else:
        assert not args.control and not args.control_sha and not args.parent and not args.parent_sha
    run = HERE / "runs" / args.tag
    pass_number = 1 if args.mode == "pass1" else 2
    cmd = list(original["commands"]["pass" + str(pass_number)])
    assert cmd[:6] == ["/usr/bin/nice", "-n", "10", "/usr/bin/taskset", "-c", "0-7"]
    assert cmd[6] == original["binary"]["path"]
    cmd[6] = str(app)
    stats = run / "pass.stats"
    for flag, value in {"--stats": str(stats), "-b": str(run / "out.ivf")}.items():
        assert cmd.count(flag) == 1
        cmd[cmd.index(flag) + 1] = value
    if pass_number == 2:
        assert cmd.count("-o") == 1
        cmd[cmd.index("-o") + 1] = str(run / "recon.yuv")
    else:
        assert "-o" not in cmd
    assert cmd[cmd.index("--pass") + 1] == str(pass_number)
    assert cmd[cmd.index("--tbr") + 1] == "10042"
    assert "--min-qp" not in cmd and "--max-qp" not in cmd
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PANTHEON_", "SVT_PANTHEON_", "SVT_PSYEX_"))}
    env["LD_LIBRARY_PATH"] = str(lib.parent)
    if args.mode in ("cap", "trace"):
        env["SVT_PANTHEON_R18_CAP"] = "1"
    if args.preview:
        print(json.dumps(dict(mode=args.mode, argv=cmd, cap=env.get("SVT_PANTHEON_R18_CAP"),
                              trace=args.mode == "trace", build=ident(args.pins)), indent=2))
        return
    run.mkdir(parents=True, exist_ok=False)
    receipt = dict(status="prepared", mode=args.mode, tag=args.tag, argv=cmd, case="e05-1440",
                   started_utc=utc(), script=ident(__file__), pins=ident(args.pins),
                   original_receipt=ident(ORIGINAL), contract=ident(CONTRACT),
                   settings=original["settings"], request_kbps=10042,
                   input=original["input"], validity=original["validity"],
                   source_mbps=original["source_mbps"], outputs={},
                   scope="Scratch policy/control only; native delivery, decoder admission and quality remain separate.")
    if control:
        receipt["control"] = ident(args.control)
        receipt["parent"] = ident(args.parent)
    def save():
        (run / "command.json").write_text(json.dumps(receipt, indent=2) + "\n")
    save()
    fds = []
    try:
        shutil.copyfile(__file__, run / "measured-runner.py")
        if pass_number == 2:
            chosen = original["stats"] if args.mode == "baseline" else parent["outputs"]["pass.stats"]
            verify(chosen)
            assert chosen["sha256"] == original["stats"]["sha256"]
            shutil.copyfile(chosen["path"], stats)
        paths = [Path(__file__), run / "measured-runner.py", CONTRACT, ORIGINAL, LINEAGE,
                 args.pins, *map(Path, ancestors),
                 *[Path(x) for x in original["identity_after"]],
                 *[Path(x["path"]) for x in pinned_files],
                 Path("/usr/bin/nice"), Path("/usr/bin/taskset"), Path("/usr/bin/ldd")]
        if pass_number == 2:
            paths.append(stats)
        if control:
            paths.extend([args.control, args.parent])
        paths = sorted(set(path.resolve() for path in paths))
        receipt["identity_before"] = [ident(path) for path in paths]
        ld = subprocess.run(["/usr/bin/ldd", str(app)], env=env, capture_output=True, text=True)
        receipt["ldd"] = dict(returncode=ld.returncode, stdout=ld.stdout, stderr=ld.stderr)
        found = re.search(r"libSvtAv1Enc\.so\.3\s+=>\s+(\S+)", ld.stdout)
        assert ld.returncode == 0 and found and Path(found.group(1)).resolve() == lib.resolve()
        if args.mode == "trace":
            for variable, filename in (
                ("SVT_PANTHEON_R18_FD", "r18-trace.bin"),
                ("SVT_PANTHEON_BOUNDARY_FD", "boundary.bin"),
                ("SVT_PANTHEON_COEFF_FD", "coeff.bin"),
            ):
                fd = os.open(run / filename, os.O_CREAT | os.O_EXCL | os.O_APPEND | os.O_WRONLY, 0o644)
                fds.append(fd)
                env[variable] = str(fd)
        receipt["environment"] = {k: v for k, v in env.items() if k == "LD_LIBRARY_PATH" or k.startswith("SVT_PANTHEON_")}
        receipt["resource_before"] = dict(free_bytes=shutil.disk_usage(ROOT).free,
                                          loadavg=Path("/proc/loadavg").read_text())
        receipt["status"] = "running"
        save()
        started = time.monotonic()
        with (run / "encode.log").open("x") as log:
            process = subprocess.run(cmd, cwd=run, env=env, stdout=log,
                                     stderr=subprocess.STDOUT, pass_fds=tuple(fds))
        receipt.update(returncode=process.returncode, seconds=time.monotonic() - started)
        for fd in fds:
            os.close(fd)
        fds.clear()
        for filename in ("out.ivf", "recon.yuv", "pass.stats", "encode.log",
                         "r18-trace.bin", "boundary.bin", "coeff.bin"):
            if (run / filename).exists():
                receipt["outputs"][filename] = ident(run / filename)
        save()
        assert process.returncode == 0
        outputs = receipt["outputs"]
        assert outputs["pass.stats"]["sha256"] == original["stats"]["sha256"]
        if pass_number == 2:
            assert outputs["recon.yuv"]["size"] == 336 * FRAME_BYTES
            receipt["ivf_payload"] = ivf_packets(run / "out.ivf")
        if args.mode == "baseline":
            assert outputs["out.ivf"]["sha256"] == original["ivf_output"]["sha256"]
            assert outputs["recon.yuv"]["sha256"] == original["recon"]["sha256"]
            receipt["exact_r16_ivf_and_all336_reconstruction"] = True
        elif args.mode == "trace":
            for key in ("out.ivf", "recon.yuv", "pass.stats"):
                assert outputs[key]["sha256"] == parent["outputs"][key]["sha256"], key
            for key in ("r18-trace.bin", "boundary.bin", "coeff.bin"):
                assert 64 < outputs[key]["size"] <= 2**30, key
            receipt["exact_policy_observer_neutrality"] = True
        else:
            assert not any(name in outputs for name in ("r18-trace.bin", "boundary.bin", "coeff.bin"))
        receipt["identity_after"] = [ident(path) for path in paths]
        assert receipt["identity_after"] == receipt["identity_before"]
        receipt["resource_after"] = dict(free_bytes=shutil.disk_usage(ROOT).free,
                                         loadavg=Path("/proc/loadavg").read_text())
        assert receipt["resource_after"]["free_bytes"] >= 120 * 2**30
        receipt.update(status="complete", ended_utc=utc())
        save()
        print(json.dumps(dict(receipt=ident(run / "command.json"), seconds=receipt["seconds"],
                              mode=args.mode, status=receipt["status"])))
    except BaseException as error:
        receipt.update(status="failed", error=repr(error), ended_utc=utc())
        receipt["resource_after"] = dict(free_bytes=shutil.disk_usage(ROOT).free,
                                         loadavg=Path("/proc/loadavg").read_text())
        save()
        raise
    finally:
        for fd in fds:
            os.close(fd)


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
