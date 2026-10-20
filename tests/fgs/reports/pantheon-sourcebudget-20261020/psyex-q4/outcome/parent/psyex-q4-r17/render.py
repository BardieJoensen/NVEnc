#!/usr/bin/env python3
"""Native-size diagnostic luma panels from unchanged floating point mosaics."""
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

P = Path(__file__).resolve().parent
RESULT = P / "result-1/result.json"
RESULT_SHA = "a04eb728936d62662afb4ab6dbc554db394c25f1ac433c563beff59278b3abdb"
STAGES = ("original", "raw", "scalar", "q4")


def ident(p):
    p = Path(p).resolve()
    with p.open("rb") as f:
        h = hashlib.file_digest(f, "sha256").hexdigest()
    return dict(path=str(p), size=p.stat().st_size, sha256=h)


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=False)
    before = ident(__file__)
    start = time.monotonic()
    assert ident(RESULT)["sha256"] == RESULT_SHA
    result = json.loads(RESULT.read_text())
    assert result["status"] == "complete"
    source = result["mosaics"]
    assert ident(source["path"]) == source
    arrays = np.load(source["path"], allow_pickle=False)
    panels = {}
    for name, row in result["rois"].items():
        x, y, w, h = row["xywh"]
        canvas = Image.new("L", (4*w+5*18, h+70), 24)
        draw = ImageDraw.Draw(canvas)
        draw.text((18, 7), f"{name}: fixed-choice diagnostic; no playback", fill=235)
        for i, stage in enumerate(STAGES):
            # Mosaics already use 8-bit-equivalent code levels; no second scaling.
            crop = arrays[stage][y:y+h, x:x+w]
            assert np.isfinite(crop).all()
            pixels = np.clip(np.rint(crop), 0, 255).astype(np.uint8)
            left = 18+i*(w+18)
            draw.text((left, 27), stage, fill=235)
            canvas.paste(Image.fromarray(pixels), (left, 48))
        path = out / (name+"-4panel.png")
        canvas.save(path)
        panels[name] = ident(path)
    assert ident(source["path"]) == source and ident(__file__) == before
    receipt = dict(status="complete", argv=sys.argv, script=before, result=ident(RESULT),
                   mosaics=source, panels=panels, seconds=time.monotonic()-start,
                   transform="already8bit-equivalent float -> round/clip uint8 once",
                   resized=False, enhancement="none", playback=False)
    (out / "manifest.json").write_text(json.dumps(receipt, indent=2)+"\n")


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
