"""Verify source mastering metadata at AV1's field quantization precision."""
from fractions import Fraction
import json
from pathlib import Path
import subprocess
from run_encoder_trials import T,L

rows=[]
for entry in json.loads((L/'output-validation.json').read_text()):
    output=Path(entry['output'])
    command=['ffprobe','-v','error','-threads','2','-select_streams','v:0',
        '-read_intervals','%+#1','-show_frames','-show_entries','frame=side_data_list','-of','json',str(output)]
    result=subprocess.run(command,capture_output=True,text=True,check=True,timeout=60)
    data=json.loads(result.stdout)
    (output.parent/'hdr-first-frame.json').write_text(result.stdout)
    md=next(x for x in data['frames'][0]['side_data_list'] if x['side_data_type']=='Mastering display metadata')
    source=json.loads((T/'clips'/entry['name']/'hdr-static-probe.json').read_text())
    original=next(x for x in source['frames'][0]['side_data_list'] if x['side_data_type']=='Mastering display metadata')
    checks=[]
    for key in ['red_x','red_y','green_x','green_y','blue_x','blue_y','white_point_x','white_point_y','min_luminance','max_luminance']:
        denominator=int(md[key].split('/')[1])
        error=abs(Fraction(md[key])-Fraction(original[key]))
        assert error<=Fraction(1,denominator)
        checks.append(dict(field=key,source=original[key],output=md[key],absolute_error=str(error),tolerance=str(Fraction(1,denominator))))
    rows.append(dict(name=entry['name'],mode=entry['mode'],passed=True,checks=checks,command=command))
(L/'hdr-mastering-validation.json').write_text(json.dumps(rows,indent=2)+'\n')
print(len(rows),'mastering metadata checks passed at output field quantization precision')
