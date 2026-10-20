# R17 source and helper audit

- Contract: `ROUND17_FIXED_Q4_CONTRACT.md`, SHA `c6ce21643dde4213ade5cb666771dcf3259b6934c620d61d57e59aae0a9af619`.
- R12 Python/native wrapper: `parent/psyex-scalar-r12/experiment.py`, SHA `87eb15f8a7c082bb875f91edb790ed66a8e592db9d64bc5f554943040f705ee2`; native source SHA `8f1cf5b69700e1a1b2d26d8bf29a0cb87cfe2f2e0b2351881be20106731934fc`; library SHA `07fe2554623523d8e6dfe5218d94a89cdb2437bb2221123a86678090af6f2228`.
- R12 build receipt SHA `4b56e9cbd1450f68ec42d02a70d6db2e082db065c6314f34ef17443ef6cb7df5`; R12 wrapper supports `rp_fp_tables(qindex,y_dc_delta,out)`, direct/runtime quantization, and native inverse with `n <= 1024` and packed transform dimensions.
- R13 methodology/experiment SHA `dd5dd4ae87a7101be0d580997dd125190f250f2363a0c0b2f894a03482966e11`; R13 result and q1 arrays remain immutable evidence, not R17 inputs.
- P16R producer: `parent/psyex-tf0-r16-refine/admit.py`, SHA `fd190fae6a20aa3cd2efd06e6d6fc9c32471d602272a214b7168667aab511cbb`. It validates native packed `n`, TX/type, scan/DQ layout, EOB, qindex, QM/IQM, geometry and offsets; the runner repeats baseline helper controls because producer admission alone does not prove R12 helper equivalence.

The q4 label means native FP tables generated at qindex 4 with each token's captured DC delta. A zero DC delta must be established from the captured token metadata/table equality, never assumed. If table generation, array dimensions, or packed 64x64 support diverges, the runner fails closed.
