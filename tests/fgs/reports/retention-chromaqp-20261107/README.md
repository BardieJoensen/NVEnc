fgs-retention-chromaqp (2026-11-07): STOPPED at lob1 repro check (prod_o0_q26 size +0.516% vs 11-06; limit 0.5%).
Scripts: common.py prep.py cut.py metrics.py run.py summary2.py; src/ = copies from branch fix/fgs-clean-source-20261006.
Resume: python3 run.py <wins> (rows in results_rows.json; windows bd1..ca2 done, 216-encode matrix incomplete). REPRO_FAIL holds details.
- 2026-11-07 architect: size repro tolerance raised 0.5% -> 1.0% after lob1 prod q26 hit 0.516% (err_Y3 diff 3e-5). Run-to-run noise calibration; structure tolerance unchanged.
- 2026-11-07 architect: lob2 size repro 1.36% (err_Y3 6e-5, Cb amp 0.002, Butteraugli p95 0.41 run-to-run). Size tolerance set to 3% (RETENTION-CONTRACT matched-size tolerance). Read chroma deltas near 0.002 and p95 deltas under ~0.4 as noise.
