# R15 source audit (pre-execution)

This is a preparation audit only. No R15 encoder process has been launched.
The source is the admitted unmodified PSYEX R8 tree under `../psyex-r8/source`,
whose six cited files have SHA256 recorded below.

|file|SHA256|evidence|
|---|---|---|
|`Source/App/app_config.c`|d19166cd3fa9f7fa298c8b1e2dbddcfc4f5c7e7367c4f083656f9dd078cebcbf|option tokens/CLI table: `--min-qp`, `--max-qp`, `--enable-tf` (97, 119-120, 884-888, 1107); config assignment (2126-27, 2180)|
|`Source/Lib/Globals/enc_settings.c`|d9d873f3b2014b07ffdb129e03c314d38f77376827db6128233748f360418d2d|range validation 325-333; defaults 995-996/1048; effective config print 1248-1255|
|`Source/Lib/Globals/enc_handle.c`|fa2a0b22120c4ac50872c23d48c63e1ce09d1bd1439e7f72cb6652212bbd9bd3|config transfer 4442-4451/4535; TF gate `do_tf = enable_tf && hierarchical_levels >=1 && !lossless` at 3326|
|`Source/Lib/Codec/pass2_strategy.c`|fbab5cea32b8de5d438c1ffb8e00fd33c39a1751bf1454060d2cce0638a64807|VBR allowed q bounds are `quantizer_to_qindex[min/max_qp_allowed]` at 1178-79; frame qindex clamp at 1614-25|
|`Source/Lib/Codec/rc_process.c`|5187c76a6f9d132ab05c445f71b26258d83499b9c17118f76b3c294dc65531e5|frame/base qindex and QP scaling, offsets and repeated min/max clipping at 3380-3465; this is why requested bounds do not by themselves prove every TU's realized q|
|`Source/Lib/Codec/temporal_filtering.c`|f5a89aabdadeb4c2803f9ba82f944820385889580f1d0207f7d2c5816d8aa61a|TF implementation/strength paths (around 2905 and 2958+)|

The installed app help accepts `--enable-tf [0-2]`, `--min-qp [1-63]`, and
`--max-qp [1-63]`. Source validation rejects `min_qp >= MAX_QP_VALUE` and
requires `min_qp <= max_qp` (`enc_settings.c:325-333`), so `1/1` is valid.
`pass2_strategy.c` and `rc_process.c` show the bounds constrain frame/RC
qindex selection through `quantizer_to_qindex`; the source also applies QP
scaling/offsets before repeated clipping. Thus R15 records the requested
bounds but deliberately does not assert a uniform TU q=1. R11 trace reuse or
later coefficient admission must establish exercised block q values.

`enc_handle.c:3326` makes `enable_tf=0` disable the temporal-filter path when
hierarchical levels and lossless conditions would otherwise permit it. The
runtime config printer only emits temporal-filter strength lines for enabled
TF (`enc_settings.c:1248-1255`); the runner therefore expects those lines to
be absent and treats that as an effective-log check, while retaining the exact
flag argv.

For request 10313 kbps, the source formula computes 10313*1000*60/(24*1920*1080) = 12.4336902 bits/sample, above the final band threshold 8, so the VBR setup predicts static QP 30. This is distinct from API default 35, public bounds 1/1, base qindex 4, and unknown realized TU q.

The internal mapping is explicit in `Source/Lib/Codec/md_process.h:1266-1271`:
external QP 1 maps to qindex 4 (QP 0 maps to 0); therefore “q1” is a
public-QP bound, not an assertion that all coded blocks carry qindex 1.
`enc_dec_process.c:2735-2751` initializes every SB qindex from the frame base
then can change it through variance boost and TPL QP derivation. The fixed
R8 policy enables variance boost and AQ, so a later TU must be observed to
know its effective qindex. `full_loop.c:1610-1618` selects the adjusted TX QM
and applies `segmentation_qp_offset`; `full_loop.c:1798-1816` then invokes
`svt_av1_optimize_b` on the selected TU. These paths are why the R15 runner
records requested controls but leaves realized-q admission to a separate trace.

Additional cited source identities required by the R15 contract (`ROUND15_REAL_CONTRACT.md`, SHA256 `65abe8440193c14cd4925961f2cf712081e2c9876d18de8ab90440ac8d5099f3`):

|file|SHA256|role|
|---|---|---|
|`Source/Lib/Codec/md_process.h`|21b710b6ebbbfabbc02682bc7aee92eac08aafd67661435857d951f46d56f417|`quantizer_to_qindex` table, lines 1266-1271|
|`Source/Lib/Codec/enc_dec_process.c`|a5233ac2ed205502e7d6a9c829841119a7e73a83eddf068596cf57ac47e12dc1|SB qindex initialization/variance and TPL adjustments, lines 2735-2756|
|`Source/Lib/Codec/full_loop.c`|bf49b663847a0cb0666e359131f728a3d19c28db1cff2630cb50b2f8fd4d9d4c|adjusted TX/QM, segmentation offset and optimize-b call, lines 1610-1618 and 1798-1816|

`enc_settings.h:22` defines `DEFAULT_QP 35`, and `enc_settings.c:974` assigns it as the static QP default. R15 leaves
that default untouched and adds only public min/max bounds. The contract and
runner therefore distinguish public QP 1 from internal qindex 4 and from any
realized TU q; no q=1 claim is made.
