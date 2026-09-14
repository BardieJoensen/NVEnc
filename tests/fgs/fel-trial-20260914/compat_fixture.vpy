from fel_clip import core
bl = core.ffms2.Source('/trial/src/felbaker/test/samples/BL-150.hevc', threads=1)
el = core.ffms2.Source('/trial/src/felbaker/test/samples/EL-150.hevc', threads=1)
core.fel_compat.Bake(bl, el, no_resample=0, non_parallel=1, dovi_metadata=1).set_output()
