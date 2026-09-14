from pathlib import Path
import hashlib
import json
import resource
import time
from fel_clip import inputs, reconstructed

rows = []
for directory in sorted(Path('/trial/clips').iterdir()):
    start = time.monotonic()
    bl, el = inputs(directory)
    rgb = reconstructed(bl, el)
    frame = rgb.get_frame(0)
    with el.get_frame(0) as f:
        rpu = f.props.get('DolbyVisionRPU', b'')
    record = dict(name=directory.name, frames=bl.num_frames, fps=[bl.fps_num, bl.fps_den],
        bl_dimensions=[bl.width, bl.height], el_dimensions=[el.width, el.height],
        rgb_format=frame.format.name, rgb_props={k:v for k,v in frame.props.items()
        if isinstance(v, (int, float, str)) and (k.startswith('_dovi') or k in ['_Matrix','_Transfer','_Primaries','_ColorRange','_SceneChangePrev'])},
        first_el_rpu_bytes=len(rpu), first_el_rpu_sha256=hashlib.sha256(rpu).hexdigest(),
        first_frame_seconds=time.monotonic()-start, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    frame.close()
    rows.append(record)
    Path('/trial/results/clip-probes.json').write_text(json.dumps(rows, indent=2)+'\n')
    print(directory.name, bl.num_frames, 'frames', record['first_frame_seconds'], flush=True)
    del rgb, bl, el
