"""End-to-end native PQ diagnostics: analytic levels, colour and coverage."""
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[2]

def perceptual_level(code):
    signal=(code-64)/876
    p=signal**(1/78.84375)
    nits=10000*(max(p-.8359375,0)/(18.8515625-18.6875*p))**(1/.1593017578125)
    y=max(.005,min(10000,nits))**.9062562627
    return max(596.3148142*(((.353487901+.3734658629*y)/(1+8.277049286e-5*y))**.09150303166-.9099517204),0)

class NativePQTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='fgs-native-pq-')
        cls.root=Path(cls.temp.name);cls.exe=cls.root/'compare'
        subprocess.run([os.environ.get('CXX','g++'),'-std=c++17','-O2','-Wall',
            str(REPO/'tools/fgs/native_pq_compare.cpp'),'-o',str(cls.exe)],check=True)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def file(self,name,y=400,u=512,frames=2,width=16):
        p=self.root/name
        picture=struct.pack('<H',y)*(width*16)+struct.pack('<H',u)*(width*4)+struct.pack('<H',512)*(width*4)
        p.write_bytes(f'YUV4MPEG2 W{width} H16 F24:1 Ip A1:1 C420p10\n'.encode()+frames*(b'FRAME\n'+picture))
        return p

    def compare(self,a,b,peak=1000):
        result=subprocess.run([str(self.exe),str(a),str(b),str(peak)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        return [json.loads(line) for line in result.stdout.splitlines()]

    def test_identity_all_displays(self):
        source=self.file('identity.y4m')
        for peak in (400,1000,4000):
            rows=self.compare(source,source,peak);self.assertEqual(len(rows),2)
            for row in rows:
                self.assertEqual(row['peak_nits'],peak)
                for channel in row['channels']:self.assertEqual(channel,dict(rms=0,coarse8_rms=0,bias=0))

    def test_uniform_levels_against_analytic_mapping(self):
        source=self.file('levels-source.y4m')
        for code in (399,401):
            expected=perceptual_level(code)-perceptual_level(400)
            for row in self.compare(source,self.file(f'level-{code}.y4m',y=code)):
                for channel in row['channels']:
                    self.assertAlmostEqual(channel['bias'],expected,delta=1e-4)
                    self.assertAlmostEqual(channel['rms'],abs(expected),delta=1e-4)
                    self.assertAlmostEqual(channel['coarse8_rms'],abs(expected),delta=1e-4)

    def test_colour_error_is_not_hidden_by_unchanged_y(self):
        rows=self.compare(self.file('colour-source.y4m'),self.file('colour-shift.y4m',u=513))
        for row in rows:
            self.assertEqual(row['channels'][1]['rms'],0)  # Cb leaves red unchanged.
            self.assertGreater(row['channels'][2]['rms'],0)
            self.assertGreater(row['channels'][3]['rms'],0)

    def test_incomplete_and_mismatched_inputs_fail(self):
        source=self.file('coverage-source.y4m')
        truncated=self.file('truncated.y4m');truncated.write_bytes(truncated.read_bytes()[:-1])
        wrong_depth=self.file('wrong-depth.y4m');wrong_depth.write_bytes(wrong_depth.read_bytes().replace(b'C420p10',b'C420p12'))
        candidates=(truncated,wrong_depth,self.file('short.y4m',frames=1),self.file('long.y4m',frames=3),self.file('geometry.y4m',width=24))
        for candidate in candidates:
            result=subprocess.run([str(self.exe),str(source),str(candidate),'1000'],capture_output=True)
            self.assertNotEqual(result.returncode,0,candidate)

    def test_invalid_display_peak_fails(self):
        source=self.file('peak.y4m')
        for peak in ('nan','0','inf','10001'):
            result=subprocess.run([str(self.exe),str(source),str(source),peak],capture_output=True)
            self.assertNotEqual(result.returncode,0)

if __name__=='__main__':unittest.main()
