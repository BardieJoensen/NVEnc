#!/usr/bin/env python3
"""Freeze reviewed R15 small evidence; retain immutable external payload pins."""
import hashlib, json, shutil
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
WORK = ROOT / "worker/psyex-r15-real"
RUN = WORK / "runs/e05-1440/r15-tf0-publicqp1"
REVIEW = ROOT / "reviewer"
SCORES = ROOT / "parent/scores/e05-1440"
REPORT = Path("/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020")
OUT = REPORT / "psyex-real"

def ident(path):
    path = Path(path).resolve()
    with path.open("rb") as f:
        sha = hashlib.file_digest(f, "sha256").hexdigest()
    return dict(path=str(path), sha256=sha, size=path.stat().st_size)

def checked(path, sha):
    row = ident(path)
    assert row["sha256"] == sha
    return json.loads(path.read_text()), row

def main():
    pins = {
        "encode": (RUN / "command.json", "8234fcf3c6c8d69522646d6e4b34973639dcdbce30696f4bb0474b583630996a"),
        "admission": (P / "admitted-1/admission.json", "10e7bc21ae29e3913fc022ae0d472929b829df0ef3cd6393fef46aa08cf66ecf"),
        "stages": (P / "stages-1.json", "52f50218e8bc873db29b9a7feab71361183a238cce4e93a7f6280ff80f300c4f"),
        "assessment": (RUN / "assessment.json", "a099d5799c7bbc4d218043d0dd79267c03c892b02f8a7def81515bb9e54ad1e5"),
        "comparison": (P / "controls-versus-r8-1.json", "147b2a06989d58deda82123f951340837d11189a5b37368678c0bd59df545ef6"),
        "campaign": (SCORES / "r15-tf0-publicqp1-result.json", "2597792b19ae4e0b3790d1d58395d7be642ad3cfd7d236f3e50b96515470bc7c"),
        "independent_quality": (REVIEW / "round15-outcome/quality-check.json", "f04b22193aa2fd676f5b18728c28e8b9e8657fbd16d19162823310a4b22aca7f"),
    }
    data, inputs = {}, {}
    for key, (path, sha) in pins.items():
        data[key], inputs[key] = checked(path, sha)
    assert ident(REVIEW / "round15-outcome-review.md")["sha256"] == "ed323c4dc1713cbbe9d468d98e55e2ec352e7da499f6ed759cb180f0a5356b6d"
    assert data["admission"]["status"] == "admitted"
    assert data["assessment"]["playback_observed"] is False
    assert not data["assessment"]["practical_rate_eligible"]
    OUT.mkdir(exist_ok=False)
    files = {}
    def add(path, name=None):
        path = Path(path)
        name = name or path.name
        assert name not in files and path.stat().st_size < 1024 * 1024
        original = ident(path)
        shutil.copyfile(path, OUT / name)
        copied = ident(OUT / name)
        assert copied["sha256"] == original["sha256"] and copied["size"] == original["size"]
        files[name] = dict(source=original, frozen=copied)
    for path in (
        P / "freeze.py", P / "execute.py", P / "validate_decoders.py",
        P / "replay_decoder.py", P / "admit.py", P / "parsers.py",
        P / "prepare_parsers.py", P / "parser-control.json", P / "stage_diagnostic.py",
        P / "compare_controls.py", P / "resource-expansion.json", P / "ARCHIVAL_NOTES.md",
        WORK / "encode_r15.py", WORK / "replay_r15.py", WORK / "score_r15.py",
        WORK / "source-audit.md", WORK / "effective-qp-addendum.md",
        WORK / "score_r15.py.v1-failed-schema", WORK / "score_r15.py.v2-size-schema",
        REVIEW / "round15-binding/bind_r15_headers.py",
        REVIEW / "round15-outcome/derive_admission.py",
        REVIEW / "round15-outcome/derive_quality.py",
        REVIEW / "round15-outcome/admission-check.json",
    ):
        add(path)
    add(WORK / "README.md", "encoder-README.md")
    for key, (path, _) in pins.items():
        add(path, key + ".json")
    add(RUN / "decoder-validation/decoder-validation.json")
    add(REVIEW / "round15-binding/run-1/result.json", "syntax-binding.json")
    add(REVIEW / "round15-binding/run-1-review.md", "syntax-binding-review.md")
    for path in sorted(REVIEW.glob("round15-*.md")):
        add(path)
    for mode in ("off", "on"):
        add(WORK / f"replays/{mode}-1/command.json", f"encoder-{mode}.json")
        add(P / f"decoder-{mode}-1/command.json", f"decoder-{mode}.json")
    for path in sorted(P.glob("*-execution*.json")):
        add(path)
    add(P / "score-execution-1.log", "failed-score-schema.log")
    add(SCORES / "r15-tf0-publicqp1-texture.json", "texture-240.json")
    add(SCORES / "metrics-cuda-r15-tf0-publicqp1.json", "metrics-cuda.json")
    add(SCORES / "ssimu2-r15-tf0-publicqp1.json", "ssimu2.json")
    add(SCORES / "butter-r15-tf0-publicqp1.json", "butter.json")
    add(ROOT / "worker/psyex-r15-stills/result/manifest.json", "stills-manifest.json")
    add(ROOT / "worker/psyex-r15-stills/render.py", "render-stills.py")
    add(ROOT / "worker/psyex-r15-stills/command.json", "render-stills-command.json")
    add(ROOT / "worker/psyex-r15-stills/README.md", "stills-README.md")
    external = [ident(RUN / name) for name in ("out.ivf", "out.mkv", "recon.yuv", "controls.json")]
    external += [
        ident(WORK / "replays/on-1/coeff.bin"),
        ident(WORK / "replays/on-1/boundary.bin"),
        ident(P / "decoder-on-1/trace.jsonl"),
        ident(P / "decoder-on-1/payload.bin"),
        ident(P / "admitted-1/tokens.json"),
        ident(P / "admitted-1/decoder-admission.json"),
    ]
    compact = dict(
        status="reviewed_high_rate_numerical_preservation",
        scope="One E05 fixture; not practical, not matched-rate, not playback-qualified; E04 and full episodes unresolved.",
        inputs=inputs, actual_mbps=data["encode"]["actual_mbps"],
        source_mbps=data["assessment"]["source_mbps"],
        relative_source_rate=data["assessment"]["relative_source_rate"],
        two_pass_seconds=data["assessment"]["two_pass_wall_seconds"],
        native_quantization=data["admission"]["quantization"],
        source_change_count=data["admission"]["source_change_count"],
        tokens=data["admission"]["tokens"], positive_units=data["admission"]["positive_units"],
        texture_screen=data["assessment"]["texture_screen"],
        controls_versus_r8=data["comparison"]["summary"],
        face=data["comparison"]["face"],
        campaign={key: value for key, value in data["campaign"].items() if key != "alignment_all_blocks"},
        temporal_and_tails=data["independent_quality"],
        stage_descriptors=data["stages"]["fixed_roi"],
        playback_observed=False, external_artifacts=external,
    )
    cp = REPORT / "psyex-real-result.json"
    assert not cp.exists()
    cp.write_text(json.dumps(compact, indent=2, allow_nan=False) + "\n")
    (OUT / "manifest.json").write_text(json.dumps(dict(files=files, external_artifacts=external, compact=ident(cp)), indent=2) + "\n")
    (OUT / "README.md").write_text(
        "# R15 frozen reproduction and evidence\n\n"
        "See ../PSYEX_REAL.md and ../ROUND15_REAL_CONTRACT.md for conclusions and scope.\n"
        "manifest.json binds each frozen file to its measured scratch source. Native traces,\n"
        "media and full control tiles remain external and hash-bound; their receipts retain\n"
        "original paths. The historical scripts intentionally retain original-prefix pins.\n"
        "ARCHIVAL_NOTES.md explains why a relocation symlink alone cannot satisfy exact-path\n"
        "execution checks. No archive has been made yet; later rounds still depend on these files.\n\n"
        "Reproduce in the original scratch prefix with pinned R8 app/library, R11 observer,\n"
        "R10 decoder, original fixture and recorded dependencies restored. encode.json contains\n"
        "both literal encode commands; encoder-{off,on}.json and decoder-{off,on}.json contain\n"
        "all neutral replay commands. *-execution*.json contain actual validation, admission,\n"
        "scoring, stage and comparison invocations with script hashes and return codes. Use\n"
        "fresh output directories for reruns; do not overwrite evidence. The first scoring\n"
        "attempt failed before metrics on an identity-schema bug; the second is the valid run.\n"
    )
    for key, (path, sha) in pins.items():
        assert ident(path)["sha256"] == sha
    print(json.dumps(dict(compact=ident(cp), manifest=ident(OUT / "manifest.json"), frozen_files=len(files))))

if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
