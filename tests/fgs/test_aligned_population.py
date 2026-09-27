import unittest
import numpy as np
from aligned_population_reference import diagnose, prepare, diagnose_prepared


def scene(speed=7, depth=8, sigma=0., seed=6741):
    rng=np.random.default_rng(seed);source=[];clean=[];scale=1<<(depth-8)
    for c in range(3):
        pattern=rng.integers(-12,13,(256,256),dtype=np.int32)
        if c==0:pattern=np.repeat(np.repeat(pattern,2,axis=0),2,axis=1)
        frames=np.array([(80 if c==0 else 128)+np.roll(pattern,t*speed*(1 if c else 2),axis=1) for t in range(8)])
        noise=rng.normal(0,sigma,frames.shape)
        clean.append((frames*scale).astype(np.uint16));source.append(np.rint((frames+noise)*scale).astype(np.uint16))
    return source,clean


def call(source,base,depth=8,x=96,y=96):
    return diagnose(source,base,depth,list(range(8)),[t*41 for t in range(8)],[1]*8,x,y)


class AlignedPopulationTests(unittest.TestCase):
    def test_noiseless_fast_motion_is_not_estimated_as_grain(self):
        source,clean=scene();result=call(source,[p[-1] for p in clean])
        self.assertTrue(result['registration_supported']);self.assertEqual(result['chroma_offset'],[0,-7])
        np.testing.assert_array_equal(result['evidence']['source_residual_covariance'],0)
        self.assertTrue(np.all(np.diag(result['unaligned']['source_residual_covariance'])>10))
        self.assertFalse(result['source_admission']);self.assertFalse(result['detail_admission'])
        self.assertTrue(all('conditional_variance_outside_study_range' in c for c in result['conflicts']))

    def test_independent_scalar_source_and_oriented_base_cross_moments(self):
        source,clean=scene(sigma=2.);base=[np.rint(c[-1]+r*(s[-1].astype(float)-c[-1])).astype(np.uint16)
            for s,c,r in zip(source,clean,[.1,.25,.75])]
        result=call(source,base);self.assertTrue(result['registration_supported'])
        self.assertTrue(np.all(np.diag(result['unaligned']['source_residual_covariance'])
                               >5*np.diag(result['evidence']['source_residual_covariance'])))
        # Independent scalar Cb/Cr cross sum, with the actual integer locations.
        fields=[]
        for c in (1,2):
            s=source[c][:,96:128];aligned=np.array([s[t,:,96-(7-t)*7:128-(7-t)*7] for t in range(8)],dtype=float)
            a=aligned[:3].mean(axis=0);h=aligned[3:7].mean(axis=0)
            fields.append([aligned[7]-a,aligned[7]-h,base[c][96:128,96:128].astype(float)-a,
                           base[c][96:128,96:128].astype(float)-h])
        def scalar(a,b):
            a=a.ravel().tolist();b=b.ravel().tolist();ma=sum(a)/len(a);mb=sum(b)/len(b)
            return sum((u-ma)*(v-mb) for u,v in zip(a,b))/(len(a)-1)
        expected=.5*(scalar(fields[0][0],fields[1][3])+scalar(fields[0][1],fields[1][2]))
        actual=result['evidence']['source_base_residual_covariance']
        self.assertAlmostEqual(actual[1,2],expected,places=11)
        self.assertFalse(np.allclose(actual,actual.T))

    def test_candidate_cannot_choose_registration_or_source_estimate(self):
        source,clean=scene(sigma=2.)
        a=call(source,[p[-1] for p in clean]);b=call(source,[p[-1] for p in source])
        self.assertEqual(a['registration_supported'],b['registration_supported'])
        self.assertEqual(a['chroma_offset'],b['chroma_offset'])
        self.assertEqual(a['aligned_native_sha256'],b['aligned_native_sha256'])
        np.testing.assert_array_equal(a['evidence']['source_residual_covariance'],b['evidence']['source_residual_covariance'])
        self.assertNotEqual(a['candidate_native_sha256'],b['candidate_native_sha256'])

    def test_full_native_refinement_resolves_phase_without_using_validation(self):
        source,clean=scene(sigma=2.);before=call(source,[p[-1] for p in clean])
        coarse=before['native_motion'][0];refined=before['registration'][0]
        self.assertEqual((coarse['dy'],coarse['dx']),(1,-13))
        self.assertEqual((refined['dy'],refined['dx']),(0,-14))
        expected=sum((int(source[0][b,y,x])-int(source[0][a,y,x-14]))**2
                     for a,b in [(0,1),(2,3)] for y in range(192,256) for x in range(192,256))/(2*64*64)
        self.assertEqual(refined['training_mse'],expected)
        rng=np.random.default_rng(67660)
        for c in range(3):source[c][4:]=rng.integers(64,192,source[c][4:].shape,dtype=np.uint16)
        after=call(source,[p[-1] for p in source]);self.assertFalse(after['registration_supported'])
        for a,b in zip(before['registration'],after['registration']):
            self.assertEqual((a['dy'],a['dx'],a['training_mse']),(b['dy'],b['dx'],b['training_mse']))
            self.assertEqual(b['validation_searches'],0)

    def test_reversal_and_disagreeing_components_remain_unknown(self):
        source,_=scene();backward,_=scene(-7);before=call(source,[p[-1] for p in source])
        source[2]=backward[2]
        self.assertEqual(call(source,[p[-1] for p in source])['reason'],'inconsistent_native_component_motion')
        source,_=scene()
        for c in range(3):source[c][4:]=backward[c][4:]
        after=call(source,[p[-1] for p in source])
        self.assertEqual(after['reason'],'motion_not_independently_supported')
        for a,b in zip(before['native_motion'],after['native_motion']):
            self.assertEqual((a['dx'],a['dy'],a['training_mse']),(b['dx'],b['dy'],b['training_mse']))

    def test_unavailable_history_is_not_wrapped_or_padded(self):
        source,_=scene();result=call(source,[p[-1] for p in source],x=32)
        self.assertEqual(result['reason'],'insufficient_full_history_overlap')
        self.assertIsNone(result['evidence']);self.assertFalse(result['registration_supported'])

    def test_zero_motion_requires_source_anchors_and_protects_native_rows(self):
        source,clean=scene(0,sigma=2.);result=call(source,[p[-1] for p in clean])
        self.assertTrue(result['registration_supported']);self.assertEqual(result['chroma_offset'],[0,0])
        flat=[np.full_like(p,128) for p in source]
        self.assertEqual(call(flat,[p[-1] for p in flat])['reason'],'stationary_source_anchors_missing')
        source,clean=scene()
        lines=np.where(np.arange(512)%2,16,-16)[None,:,None]
        source[0]=(source[0].astype(np.int32)+lines).astype(np.uint16)
        result=call(source,[p[-1] for p in clean])
        self.assertTrue(result['registration_supported']);self.assertTrue(result['persistent_detail_conflicts'][0])

    def test_native_depth_and_invalid_history_contract(self):
        source,clean=scene();a=call(source,[p[-1] for p in clean])
        b=call([p*4 for p in source],[p[-1]*4 for p in clean],10)
        self.assertEqual(a['chroma_offset'],b['chroma_offset'])
        np.testing.assert_allclose(a['evidence']['source_residual_covariance'],b['evidence']['source_residual_covariance'])
        args=[source,[p[-1] for p in clean],8,list(range(8)),list(range(8)),[1]*8,96,96]
        for index,value in [(2,True),(3,[0,1,2,3,4,5,6,9]),(4,[0]*8),(5,[1]*7+[2]),(6,95),(6,True)]:
            changed=args.copy();changed[index]=value
            with self.assertRaises(ValueError):diagnose(*changed)

    def test_prepared_census_owns_immutable_native_evidence(self):
        source,clean=scene();base=[p[-1].copy() for p in clean]
        prepared=prepare(source,base,8,list(range(8)),list(range(8)),[1]*8)
        before=diagnose_prepared(prepared,96,96)
        source[0][:]=0;base[1][:]=255
        after=diagnose_prepared(prepared,96,96)
        self.assertEqual(before['aligned_native_sha256'],after['aligned_native_sha256'])
        self.assertEqual(before['candidate_native_sha256'],after['candidate_native_sha256'])
        for p in (*prepared.history,*prepared.base):
            self.assertFalse(p.flags.writeable)
            with self.assertRaises(ValueError):p.flags.writeable=True
        with self.assertRaises(ValueError):diagnose_prepared({},96,96)


if __name__ == '__main__':unittest.main()
