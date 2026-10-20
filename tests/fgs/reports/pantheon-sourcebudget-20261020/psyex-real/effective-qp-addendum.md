# R15 observed QP message addendum (read-only audit)

This addendum does not modify the hash-bound R15 runner, README, or source
audit and does not launch a process. The active pass-1 log contains:

```text
Svt[warn]: The input q value is ignored in vbr mode 43
```

The `43` is not the API default and not the final VBR static QP. It arises
because the first-pass setup explicitly sets `scs->static_config.qp = 43` at
`Source/Lib/Globals/enc_handle.c:3727-3741` when `config->pass == ENC_FIRST_PASS`.
The warning at lines 3877-3881 then reports that first-pass q as ignored in
VBR mode. This explains the log without implying that public QP1 escaped or
that TU q is 43.

The API default path is separate: `DEFAULT_QP` is 35 in
`enc_settings.h:22`, assigned at `enc_settings.c:974`. For VBR/final setup,
`enc_handle.c:3877-3898` recalculates `scs->static_config.qp` from
`target_bit_rate * 60 / (fps_num/fps_den) / (width*height)`. At request 10313,
24 fps and 1920x1080 this is 12.4336902006, above the final threshold 8, so
the predicted final VBR static QP remains 30. The 43 warning is therefore a
first-pass temporary value; it does not contradict final-pass prediction 30.

The three quantities remain distinct: API default 35, first-pass temporary
QP 43 (observed warning), and final VBR predicted static QP 30. Public bounds
1/1 map to internal qindex 4, while actual TU q remains unobserved until the
admitted trace. Source SHA256 identities and the active pass-1 log SHA are
recorded below for reproducibility.

## Final evidence identities

The cited source identities are:

- `Source/Lib/Globals/enc_handle.c`: `fa2a0b22120c4ac50872c23d48c63e1ce09d1bd1439e7f72cb6652212bbd9bd3`
- `Source/Lib/Globals/enc_settings.h`: `3e2f8e8861addba1a7a8866d939660cf2b8ce8a06d65392257cc3a162a7c17e2`
- `Source/Lib/Globals/enc_settings.c`: `d9d873f3b2014b07ffdb129e03c314d38f77376827db6128233748f360418d2d`
- Final completed pass-1 log `runs/e05-1440/r15-tf0-publicqp1/pass1.log`: SHA256 `63dd5c027b8a53474d7834692eb7eb79ab331e57b02b0facf8860d933e829f37`

The complete bound source chain and additional cited-file identities are in
`source-audit.md`.
