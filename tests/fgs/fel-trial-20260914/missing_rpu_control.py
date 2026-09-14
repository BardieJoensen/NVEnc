"""Missing RPU must fail rather than silently return a base-layer picture."""
import json
from pathlib import Path
from fel_clip import core, bounded, reconstructed
bl=bounded(core.ffms2.Source('/trial/src/felbaker/test/samples/BL-150.hevc',threads=1))
el=bounded(core.ffms2.Source('/trial/src/felbaker/test/samples/EL-150.hevc',threads=1))
bl=bounded(core.std.RemoveFrameProps(bl,props=['DolbyVisionRPU']))
el=bounded(core.std.RemoveFrameProps(el,props=['DolbyVisionRPU']))
try:
    with reconstructed(bl,el).get_frame(0):pass
except Exception as error:
    message=str(error)
    if 'RPU data is missing' not in message:raise
    Path('/trial/results/missing-rpu-control.json').write_text(json.dumps(dict(passed=True,expected_error=message),indent=2)+'\n')
    print('PASS: missing RPU rejected',flush=True)
else:
    raise AssertionError('missing RPU did not fail')
