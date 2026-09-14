"""Exercise the final cache-bounded graph against the published 100-frame SHA."""
from fel_clip import core, bounded, reconstructed
bl=bounded(core.ffms2.Source('/trial/src/felbaker/test/samples/BL-150.hevc',threads=2)[:100])
el=bounded(core.ffms2.Source('/trial/src/felbaker/test/samples/EL-150.hevc',threads=2)[:100])
reconstructed(bl,el).set_output()
