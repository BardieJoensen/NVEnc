import unittest
import numpy as np
from motion_detail_reference import measure


class MotionDetailTests(unittest.TestCase):
    def scene(self, speed=7):
        p=np.random.default_rng(19384).integers(96, 160, (64, 64), dtype=np.uint16)
        return np.array([np.roll(p, t*speed, axis=1) for t in range(8)])

    def call(self, source, base=None, depth=8):
        return measure(source, source[-1] if base is None else base, depth, 32, 8, 2,
                       list(range(8)), [41*t for t in range(8)])

    def test_fast_motion_and_exact_source_protection(self):
        s=self.scene(); r=self.call(s)
        self.assertFalse(r['source_admission']); self.assertFalse(r['detail_admission'])
        for t in r['tiles']:
            self.assertEqual((t['dy'], t['dx']), (0, -7))
            self.assertTrue(t['anchor_supported']); self.assertFalse(t['conflict'])
            self.assertEqual(t['contrast_change'], 0)
        for direction in (0, 2):
            base=(128+direction*(s[-1].astype(np.int32)-128)).astype(np.uint16)
            r=self.call(s, base)
            self.assertTrue(all(t['conflict'] for t in r['tiles']))
            np.testing.assert_allclose([t['contrast_change'] for t in r['tiles']], 1-direction)

    def test_proposal_is_independent_of_base_and_validation(self):
        s=self.scene(); old=self.call(s); s[4:]=self.scene(-7)[4:]
        new=self.call(s, np.full((64, 64), 128, np.uint16))
        for a,b in zip(old['tiles'], new['tiles']):
            self.assertEqual((a['dx'], a['dy'], a['training_mse']), (b['dx'], b['dy'], b['training_mse']))
            self.assertFalse(b['motion_supported']); self.assertFalse(b['conflict'])
        self.assertTrue(any(min(t['improvement']) < 0 for t in new['tiles']))

    def test_native_rows_are_not_lost_by_matching_smoothing(self):
        s=self.scene(); rows=np.where(np.arange(64)%2, 24, -24).astype(np.int32)
        native=(s.astype(np.int32)+rows[None, :, None]).astype(np.uint16)
        r=self.call(native, s[-1])
        self.assertTrue(all(t['conflict'] for t in r['tiles']))
        self.assertTrue(all(t['removed_projection_rms'] > 10 for t in r['tiles']))
        scaled=self.call(native*4, s[-1]*4, 10)
        for a,b in zip(r['tiles'], scaled['tiles']):
            for key in a: np.testing.assert_allclose(a[key], b[key], atol=1e-12)

    def test_independent_grain_and_quiet_ties_do_not_approve(self):
        rng=np.random.default_rng(923100)
        s=np.rint(128+rng.normal(0, 2, (8, 64, 64))).astype(np.uint16)
        r=self.call(s, np.full((64, 64), 128, np.uint16))
        self.assertFalse(r['detail_admission'])
        self.assertTrue(all(not t['conflict'] for t in r['tiles']))
        r=self.call(np.full_like(s, 128))
        self.assertTrue(all(t['dx']==t['dy']==0 and not any(t['relative_defined']) for t in r['tiles']))

    def test_partial_borders_and_insufficient_search_are_unknown(self):
        s=np.full((8, 66, 130), 128, np.uint16); b=s[-1].copy(); b[-1, -1]=129
        r=measure(s, b, 8, 64, 32, 4, list(range(8)), list(range(8)))
        self.assertEqual(sum(t['samples'] for t in r['tiles']), 66*130)
        t=r['tiles'][-1]
        self.assertEqual((t['samples'], t['changed_samples'], t['fit_samples']), (4, 1, 0))
        self.assertFalse(t['anchor_supported']); self.assertFalse(r['detail_admission'])

    def test_scalar_native_projection_is_independent(self):
        s=self.scene(); b=np.rint(128+.75*(s[-1].astype(float)-128)).astype(np.uint16)
        t=self.call(s,b)['tiles'][0]; values=[]
        for y in range(32):
            for x in range(7,32): values.append((int(s[7,y,x]), int(s[6,y,x-7]), int(s[7,y,x])-int(b[y,x])))
        means=[sum(v[i] for v in values)/len(values) for i in range(3)]
        cov=lambda i,j:sum((v[i]-means[i])*(v[j]-means[j]) for v in values)/len(values)
        self.assertAlmostEqual(t['contrast_change'],cov(2,1)/cov(0,1),places=12)
        self.assertAlmostEqual(t['removed_projection_rms'],abs(cov(2,1))/cov(1,1)**.5,places=12)
        self.assertAlmostEqual(t['mean_error'],means[2],places=12)

    def test_native_matching_detects_smoothed_alternating_line_nullspace(self):
        pattern=np.broadcast_to(np.where(np.arange(128)%2,144,112)[:,None],(128,128))
        s=np.array([np.roll(pattern,t,axis=0) for t in range(8)],dtype=np.uint16)
        base=np.full((128,128),128,np.uint16)
        args=(s,base,8,64,32,4,list(range(8)),list(range(8)))
        smooth=measure(*args);native=measure(*args,native_match=True)
        self.assertTrue(all(not t['motion_supported'] for t in smooth['tiles']))
        self.assertTrue(all(t['conflict'] for t in native['tiles']))
        self.assertFalse(native['detail_admission'])
        with self.assertRaises(ValueError):measure(*args,native_match=1)

    def test_invalid_native_history(self):
        s=self.scene(); base=s[-1]; args=[s,base,8,32,8,2,list(range(8)),list(range(8))]
        for pos,value in [(0,s[:-1]),(0,s.astype(float)),(2,True),(2,9),(3,16),(4,33),(5,3),
                          (6,[0,1,2,3,4,5,6,8]),(7,[0,1,2,3,4,5,6,6]),(7,list(map(float,range(8))))]:
            changed=args.copy();changed[pos]=value
            with self.assertRaises(ValueError):measure(*changed)
        s=s.copy();s[0,0,0]=256
        with self.assertRaises(ValueError):self.call(s)


if __name__ == '__main__': unittest.main()
