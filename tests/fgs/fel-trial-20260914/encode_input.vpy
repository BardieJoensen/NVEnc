from pathlib import Path
from fel_clip import inputs, reconstructed, rgb_to_pq10, ROOT

directory = (ROOT/'clips'/clip_name).resolve()
if directory.parent != (ROOT/'clips').resolve():
    raise ValueError('clip must be one prepared trial directory')
bl, el = inputs(directory)
mode = globals().get('mode', 'default')
rgb_to_pq10(reconstructed(bl, el, mode=mode)).set_output()
