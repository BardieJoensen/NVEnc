"""Bind R18 inner receipts to their exact, successful parent invocations."""
import importlib.util
import json
from pathlib import Path

from read_cap_trace import fingerprint, strict_json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = HERE / "run.py"
RUN_SHA = "ebfce2b97bd8002db2e866086ed44ac8dece936d64bfeaa01062f29dc5bf6bb3"
OUTER = ROOT / "parent/psyex-real-r15/execute.py"
OUTER_SHA = "93c0740995afa0b6c1bf91c5c5bacbe620558e9a327493edf71406e8a68f4858"
BUILD = HERE / "build-1"
PINS_SHA = "c0e389a6ca98513c5b4117b48dab02552b7f21ea978585974243f747803e1fe7"
PREPARATION_SHA = "2785ef58fe327230d879a42a92d5220e44e9e598a1034be711fa1a9175486ec2"
PREFIX = ["/usr/bin/nice", "-n", "10", "/usr/bin/taskset", "-c", "8-11",
          str(ROOT / "analysis-venv/bin/python")]


def read(row):
    assert set(row) == {"path", "size", "sha256"}
    assert fingerprint(row["path"]) == row, row["path"]
    return strict_json(Path(row["path"]).read_text())


def outer(row, script, digest, arguments):
    obj = read(row)
    assert obj["status"] == "complete" and obj["returncode"] == 0
    assert obj["command"] == PREFIX + [str(script), *map(str, arguments)]
    assert obj["inputs_before"] == obj["inputs_after"]
    inputs = {x["path"]: x for x in obj["inputs_before"]}
    assert len(inputs) == len(obj["inputs_before"])
    assert inputs[str(OUTER)]["sha256"] == OUTER_SHA
    assert inputs[str(script)]["sha256"] == digest
    for item in obj["inputs_after"]:
        assert fingerprint(item["path"]) == item
    assert fingerprint(obj["log"]["path"]) == obj["log"]
    return obj


def validate(index_path, index_sha):
    """Index contains inner+outer identities for all four modes and build steps."""
    index_row = fingerprint(index_path)
    assert index_row["sha256"] == index_sha
    index = read(index_row)
    assert set(index) == {"runs", "build"}
    assert fingerprint(RUN)["sha256"] == RUN_SHA
    assert fingerprint(OUTER)["sha256"] == OUTER_SHA
    spec = importlib.util.spec_from_file_location("r18_verified_runner", RUN)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    assert set(index["runs"]) == {"baseline", "pass1", "cap", "trace"}
    results = {}
    for mode in ("baseline", "pass1", "cap", "trace"):
        item = index["runs"][mode]
        assert set(item) == {"inner", "outer"}
        obj = read(item["inner"])
        assert obj["mode"] == mode and obj["status"] == "complete" and obj["returncode"] == 0
        assert obj["script"] == fingerprint(RUN)
        assert obj["identity_before"] == obj["identity_after"]
        assert obj["contract"]["sha256"] == runner.CONTRACT_SHA
        assert obj["original_receipt"] == fingerprint(runner.ORIGINAL)
        assert Path(item["inner"]["path"]).parent == HERE / "runs" / obj["tag"]
        args = [mode, obj["tag"], obj["pins"]["path"], obj["pins"]["sha256"]]
        if mode in ("cap", "trace"):
            assert obj["control"] == index["runs"]["baseline"]["inner"]
            assert obj["parent"] == index["runs"]["pass1" if mode == "cap" else "cap"]["inner"]
            args += ["--control", obj["control"]["path"], "--control-sha", obj["control"]["sha256"],
                     "--parent", obj["parent"]["path"], "--parent-sha", obj["parent"]["sha256"]]
        outer(item["outer"], RUN, RUN_SHA, args)
        if mode != "trace":
            obj = runner.read_receipt(item["inner"]["path"], item["inner"]["sha256"], mode)
        else:
            cap = results["cap"]
            for name in ("pins", "case", "request_kbps", "input", "validity", "source_mbps", "settings"):
                assert obj[name] == cap[name], name
            expected_cmd = list(cap["argv"])
            folder = Path(item["inner"]["path"]).parent
            for flag, name in (("--stats", "pass.stats"), ("-b", "out.ivf"), ("-o", "recon.yuv")):
                expected_cmd[expected_cmd.index(flag) + 1] = str(folder / name)
            assert obj["argv"] == expected_cmd
            expected_env = dict(cap["environment"])
            fds = []
            for key in ("SVT_PANTHEON_R18_FD", "SVT_PANTHEON_BOUNDARY_FD", "SVT_PANTHEON_COEFF_FD"):
                value = obj["environment"][key]
                assert value.isdigit() and int(value) >= 3
                fds.append(value)
                expected_env[key] = value
            assert len(set(fds)) == 3 and obj["environment"] == expected_env
            assert obj["exact_policy_observer_neutrality"] is True
            for name in ("out.ivf", "recon.yuv", "pass.stats"):
                assert obj["outputs"][name]["sha256"] == cap["outputs"][name]["sha256"]
            for identity in obj["identity_after"]:
                assert fingerprint(identity["path"]) == identity
            for identity in obj["outputs"].values():
                assert fingerprint(identity["path"]) == identity
        results[mode] = obj
    pins_row = results["trace"]["pins"]
    assert pins_row["path"] == str(BUILD / "completed-build-pins.json")
    assert pins_row["sha256"] == PINS_SHA
    assert all(obj["pins"] == pins_row for obj in results.values())
    pins = read(pins_row)
    assert pins["source_manifest"]["sha256"] == "f405193d6b35d74919d452457e9b8c93e52938ebbf184dda07c7622180af75ca"
    assert pins["patch"]["sha256"] == "5f03edf1ba320c84006e65484e88742ffb60b2de422b73b10346ea90ca9ed5d0"
    assert pins["implementation_review"]["sha256"] == "5406b49c7adf70f5b1261f46d701186f15c0e17b89a87fddc32fc539e2b88e2c"
    assert pins["preparation"]["path"] == str(BUILD / "preparation.json")
    assert pins["preparation"]["sha256"] == PREPARATION_SHA
    prep = read(pins["preparation"])
    build_root = Path(pins["preparation"]["path"]).parent
    assert set(index["build"]) == {"prepare", "build", "pin"}
    outer(index["build"]["prepare"], HERE / "prepare_build.py",
          "f0c29f5be5bd910f7bf7ea04b021005fbdeb7dbfeb4730937386f4d6510b58e8",
          [prep["source"], prep["manifest"]["path"], prep["manifest"]["sha256"], build_root])
    outer(index["build"]["build"], HERE / "execute_build.py",
          "7f366b22bcd3d38bd87e32c7af58753925a4efd99920280fc7b47248531b6a32",
          [pins["preparation"]["path"], pins["preparation"]["sha256"]])
    launch = read(fingerprint(build_root / "launch.json"))
    assert launch["status"] == "complete" and launch["returncode"] == 0
    assert launch["argv"] == ["/usr/bin/bash", prep["runner"]["path"]]
    assert launch["inputs_before"] == launch["inputs_after"]
    assert {x["path"] for x in launch["inputs_before"]} == {
        str(HERE / "execute_build.py"), pins["preparation"]["path"],
        prep["runner"]["path"], "/usr/bin/bash"}
    for item in launch["inputs_after"]:
        assert fingerprint(item["path"]) == item
    outer(index["build"]["pin"], HERE / "pin_build.py",
          "dd5093a3cddd6e309e36e51f329dea2937c2591c8524c5659b55896655f84d9a",
          [build_root, pins["preparation"]["sha256"], pins["patch"]["path"], pins["patch"]["sha256"],
           pins["implementation_review"]["path"], pins["implementation_review"]["sha256"]])
    assert fingerprint(index_path) == index_row
    return results, index_row
