# Round6 private trace schema3

All records start with explicit LE `<IIIIQ>` (magic0x31525455, version3,
kind, payloadbytes, unsaturatedgeneration). Packedmetadata sizes are compiled
staticasserts: header96, TU228, final112. Field lists are in SCHEMA.json.

Header binds original and effective fullYUV MD5, source216,1920x1080 10bit420,
actual frame/show/reference/GF identity. Sourcepixels are independently exported
in parent/tu-observation/binding-v2/original.yuv; source-minus-predictor must equal
exported exercised residuals. Every targetattempt has header/TUs/end; final
selects only the lastgeneration after completed packing. Priorattempts remain
unadmitted. Final includes fullpreloop/postloop visibleY ANDactualpackedOBUbytes.

TU data follows the JSONschema payloadnote. Coefficients are signedint32, scan
signedint16, mapsuint16, residualsignedint16, all rowpacked withoutstridepadding.
No-transform skip spans have n=0, txsize/type/qindex=-1 and no coefficient/scan/
residual arrays; four maps contain actualpredictor. ExercisedEOB0 retains actual
initial/finalvectors and independent scratchinverse. RawEOB is scan-derived.
Flags1/2/4=raw/initial/finalvectors,8=exactfinalscratch,16=maps.
Quantflags1=trellispolicy,2=setupuseopt,4=actualoptcall,8=actualdropoutcall.
Quantidx is encoder AV1_XFORM_QUANT enum; selected rounding/quant entries follow
FP/B mode. Dequant/zbin/shift included; lossless/reducedtxset/logscale explicit.

Inter/intracallback observation onlyOUTPUT_ENABLED inside mainframeattempt.
Sourceidentity gates actualtarget; unsupportedtargetsuperres/qmatrix/intrabc/
pipelinedfilter/frameparallel/geometry failclosed. AnyIO/scan/inverse/geometry
failure reaches encoder AOM_CODEC_ERROR, no successreceipt.250MBcap. No encoder
pixels,coefficients,predictors,CDFs or decisions are modified. Scratchinverses
use identical initializedpredictors; packedreduceddomains are not unpacked.

Parent requires exactinstalled+samebinarydisabledIVF, exactallpixelownership,
allactualTUhashes==finalscratch, assembledfinal==preloopplane, postloop==decoded,
OBUbytes==independenttarget, and source/residual/executedquantizer bindings before
analyzing. Private mosaics are diagnostics, never legalencodes or bitrateclaims.
