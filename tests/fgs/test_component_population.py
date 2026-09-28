import unittest
import numpy as np
from aligned_population_reference import prepare, diagnose_prepared
from component_population_reference import diagnose_component
from test_aligned_population import scene


def prepared(source, base, depth=8):
    return prepare(source, base, depth, list(range(8)), [i*41 for i in range(8)], [1]*8)


class ComponentPopulationTests(unittest.TestCase):
    def test_single_component_does_not_infer_shared_motion(self):
        source, clean = scene(sigma=2.)
        reverse, _ = scene(-7, sigma=2.)
        source[2] = reverse[2]
        p = prepared(source, [s[-1] for s in clean])
        self.assertFalse(diagnose_prepared(p, 96, 96)['registration_supported'])
        result = diagnose_component(p, 0, 192, 192)
        self.assertTrue(result['registration_supported'])
        self.assertEqual(result['registration']['dx'], -14)
        self.assertFalse(result['source_admission'])
        self.assertFalse(result['joint_admission'])

    def test_scalar_native_moments_and_each_component(self):
        source, clean = scene(sigma=2.)
        base = [np.rint(c[-1]+r*(s[-1].astype(float)-c[-1])).astype(np.uint16)
                for c,s,r in zip(clean,source,[.1,.25,.75])]
        p = prepared(source, base)
        for c in range(3):
            start, side, speed = (96,32,7) if c else (192,64,14)
            result = diagnose_component(p,c,start,start)
            self.assertTrue(result['registration_supported'])
            a = np.array([source[c][i,start:start+side,start-(7-i)*speed:start-(7-i)*speed+side]
                          for i in range(8)],dtype=float)
            b = base[c][start:start+side,start:start+side].astype(float)
            first,second = a[:3].mean(axis=0),a[3:7].mean(axis=0)
            def cross(x,y):
                x,y=x.ravel().tolist(),y.ravel().tolist();mx,my=sum(x)/len(x),sum(y)/len(y)
                return sum((u-mx)*(v-my) for u,v in zip(x,y))/(len(x)-1)
            evidence=result['evidence']
            self.assertEqual(evidence['samples'],side*side)
            self.assertAlmostEqual(evidence['source_residual_variance'],cross(a[-1]-first,a[-1]-second),places=11)
            self.assertAlmostEqual(evidence['source_base_residual_covariance'],
                .5*(cross(a[-1]-first,b-second)+cross(a[-1]-second,b-first)),places=11)
            self.assertGreater(result['unaligned']['source_residual_variance'],evidence['source_residual_variance']*5)

    def test_other_components_and_candidate_cannot_choose_motion(self):
        source,clean=scene(sigma=2.)
        a=diagnose_component(prepared(source,[s[-1] for s in clean]),0,192,192)
        source[1][:]=128;source[2][:]=128
        b=diagnose_component(prepared(source,[s[-1] for s in source]),0,192,192)
        self.assertEqual(a['registration'],b['registration'])
        self.assertEqual(a['aligned_native_sha256'],b['aligned_native_sha256'])
        self.assertEqual(a['evidence']['source_residual_variance'],b['evidence']['source_residual_variance'])
        self.assertNotEqual(a['candidate_native_sha256'],b['candidate_native_sha256'])

    def test_odd_native_motion_and_grain_free_detail(self):
        source,clean=scene(0)
        for i in range(8):source[0][i]=np.roll(clean[0][0],i*7,axis=1)
        result=diagnose_component(prepared(source,[s[-1] for s in source]),0,192,192)
        self.assertTrue(result['registration_supported'])
        self.assertEqual(result['registration']['dx'],-7)
        self.assertEqual(result['evidence']['source_residual_variance'],0)
        self.assertIn('conditional_variance_outside_study_range',result['evidence']['conflicts'])

    def test_validation_does_not_search_and_reversal_stays_unknown(self):
        source,clean=scene();before=diagnose_component(prepared(source,[s[-1] for s in source]),0,192,192)
        reverse,_=scene(-7);source[0][4:]=reverse[0][4:]
        after=diagnose_component(prepared(source,[s[-1] for s in source]),0,192,192)
        self.assertFalse(after['registration_supported'])
        self.assertEqual(after['reason'],'motion_not_independently_supported')
        for key in ('dx','dy','training_mse'):
            self.assertEqual(before['registration'][key],after['registration'][key])
        self.assertEqual(after['registration']['validation_searches'],0)

    def test_native_rows_are_not_averaged_away(self):
        source,clean=scene()
        lines=np.where(np.arange(512)%2,16,-16)[None,:,None]
        source[0]=(source[0].astype(np.int32)+lines).astype(np.uint16)
        result=diagnose_component(prepared(source,[s[-1] for s in clean]),0,192,192)
        self.assertTrue(result['registration_supported'])
        self.assertTrue(result['persistent_detail_conflict'])

    def test_source_overlap_flat_anchors_and_partial_border(self):
        source,_=scene()
        result=diagnose_component(prepared(source,[s[-1] for s in source]),0,64,192)
        self.assertEqual(result['reason'],'insufficient_full_history_overlap')
        flat=[np.full_like(s,128) for s in source]
        result=diagnose_component(prepared(flat,[s[-1] for s in flat]),0,192,192)
        self.assertEqual(result['reason'],'stationary_source_anchors_missing')
        short=[s[:,:-2,:-2] if c else s[:,:-4,:-4] for c,s in enumerate(source)]
        result=diagnose_component(prepared(short,[s[-1] for s in short]),0,448,448)
        self.assertEqual(result['reason'],'partial_current_border')
        self.assertEqual((result['width'],result['height']),(60,60))

    def test_native_depth_identity_and_immutable_input(self):
        source,clean=scene(sigma=2.)
        p=prepared(source,[s[-1] for s in clean]);a=diagnose_component(p,0,192,192)
        q=prepared([s*4 for s in source],[s[-1]*4 for s in clean],10)
        b=diagnose_component(q,0,192,192)
        self.assertEqual(a['evidence'],b['evidence'])
        source[0][:]=0
        self.assertEqual(a,diagnose_component(p,0,192,192))
        for args in ((True,192,192),(3,192,192),(0,True,192),(0,191,192),(0,192,-64),(1,512,0)):
            with self.assertRaises(ValueError):diagnose_component(p,*args)
        with self.assertRaises(ValueError):diagnose_component({},0,192,192)


if __name__=='__main__':unittest.main()
