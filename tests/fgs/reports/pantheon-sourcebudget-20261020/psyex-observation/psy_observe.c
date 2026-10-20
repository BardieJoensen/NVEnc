#define _POSIX_C_SOURCE 200809L
#include "psy_observe.h"
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <unistd.h>

static uint64_t counts[336][4][PO_KIND_COUNT];
static uint64_t invalid, overflow;
static int state, output_fd = -1, flushed;
static void die(const char *message) {
    fprintf(stderr, "Pantheon observation failed: %s\n", message);
    _exit(86);
}
static int enabled(void) {
    int s = __atomic_load_n(&state, __ATOMIC_ACQUIRE);
    if (s >= 2) return s == 2;
    int expected = 0;
    if (!__atomic_compare_exchange_n(&state, &expected, 1, 0, __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE)) {
        do { s = __atomic_load_n(&state, __ATOMIC_ACQUIRE); } while (s == 1);
        return s == 2;
    }
    const char *text = getenv("SVT_PSYEX_OBS_FD");
    if (!text) { __atomic_store_n(&state, 3, __ATOMIC_RELEASE); return 0; }
    char *end; errno = 0;
    long fd = strtol(text, &end, 10);
    if (errno || end == text || *end || fd < 3 || fd > INT_MAX) die("invalid inherited FD");
    int flags = fcntl((int)fd, F_GETFL); struct stat st;
    if (flags < 0 || !(flags & O_APPEND) || (flags & O_ACCMODE) == O_RDONLY ||
        fstat((int)fd, &st) || !S_ISREG(st.st_mode) || st.st_size != 0)
        die("FD must be a fresh writable append-only regular file");
    output_fd = (int)fd;
    __atomic_store_n(&state, 2, __ATOMIC_RELEASE);
    return 1;
}
void psy_obs_add(uint64_t picture, unsigned md_stage, enum PsyObsKind kind, uint64_t amount) {
    if (!enabled()) return;
    if (picture >= 336 || md_stage >= 4 || (unsigned)kind >= PO_KIND_COUNT) {
        __atomic_fetch_add(&invalid, 1, __ATOMIC_RELAXED); return;
    }
    uint64_t *cell = &counts[picture][md_stage][kind];
    uint64_t old = __atomic_load_n(cell, __ATOMIC_RELAXED);
    for (;;) {
        if (amount > UINT64_MAX-old) { __atomic_fetch_add(&overflow, 1, __ATOMIC_RELAXED); return; }
        if (__atomic_compare_exchange_n(cell, &old, old+amount, 0, __ATOMIC_RELAXED, __ATOMIC_RELAXED)) return;
    }
}
uint64_t psy_obs_term(uint64_t picture, unsigned md_stage, enum PsyObsKind call_kind,
                      enum PsyObsKind nonzero_kind, uint64_t value) {
    psy_obs_add(picture, md_stage, call_kind, 1);
    if (value) psy_obs_add(picture, md_stage, nonzero_kind, 1);
    return value;
}
void psy_obs_flush(const EbSvtAv1EncConfiguration *cfg, unsigned instances) {
    if (!enabled()) return;
    if (__atomic_exchange_n(&flushed, 1, __ATOMIC_ACQ_REL)) die("duplicate flush/encoder instance");
    if (!cfg || instances != 1 || cfg->active_channel_count != 1 || cfg->channel_id != 0 || cfg->pass != 2)
        die("requires one actual pass-2 encoder channel");
    if (cfg->source_width != 1920 || cfg->source_height != 1080 || cfg->encoder_bit_depth != 10 ||
        cfg->frame_rate_numerator != 24 || cfg->frame_rate_denominator != 1)
        die("unexpected fixture geometry/cadence");
    if (__atomic_load_n(&invalid, __ATOMIC_RELAXED) || __atomic_load_n(&overflow, __ATOMIC_RELAXED))
        die("out-of-domain or overflowing counters");
    int copy = dup(output_fd); if (copy < 0) die("dup");
    FILE *out = fdopen(copy, "a"); if (!out) die("fdopen");
    fprintf(out, "{\"schema\":3,\"status\":\"complete\",\"instances\":%u,\"config\":{", instances);
#define CFG_I(field) fprintf(out, "\"" #field "\":%lld,", (long long)cfg->field)
    CFG_I(pass); CFG_I(active_channel_count); CFG_I(channel_id);
    CFG_I(source_width); CFG_I(source_height); CFG_I(encoder_bit_depth); CFG_I(encoder_color_format);
    CFG_I(frame_rate_numerator); CFG_I(frame_rate_denominator); CFG_I(enc_mode); CFG_I(tune);
    CFG_I(scene_change_detection); CFG_I(level_of_parallelism); CFG_I(color_range);
    CFG_I(color_primaries); CFG_I(transfer_characteristics); CFG_I(matrix_coefficients);
    CFG_I(sharp_tx); CFG_I(sharpness); CFG_I(spy_rd); CFG_I(hbd_mds); CFG_I(complex_hvs);
    CFG_I(noise_norm_strength); CFG_I(noise_adaptive_filtering); CFG_I(rate_control_mode);
    CFG_I(pred_structure); CFG_I(intra_period_length); CFG_I(intra_refresh_type); CFG_I(hierarchical_levels);
    CFG_I(enable_adaptive_quantization); CFG_I(enable_variance_boost); CFG_I(variance_boost_strength);
    CFG_I(variance_octile); CFG_I(variance_boost_curve); CFG_I(enable_qm); CFG_I(min_qm_level);
    CFG_I(max_qm_level); CFG_I(min_chroma_qm_level); CFG_I(max_chroma_qm_level);
    CFG_I(enable_tf); CFG_I(tf_strength); CFG_I(kf_tf_strength); CFG_I(enable_overlays);
    CFG_I(enable_dlf_flag); CFG_I(cdef_level); CFG_I(enable_restoration_filtering);
    CFG_I(film_grain_denoise_strength); CFG_I(film_grain_denoise_apply); CFG_I(target_bit_rate);
    fprintf(out,"\"psy_rd\":%.17g,\"qp_scale_compress_strength\":%.17g},", cfg->psy_rd, cfg->qp_scale_compress_strength);
#undef CFG_I
    fprintf(out,"\"shape\":[336,4,%u],\"invalid\":0,\"overflow\":0,\"counts\":[",(unsigned)PO_KIND_COUNT);
    for (unsigned p=0; p<336; ++p) {
        fprintf(out,"%s[",p?",":"");
        for(unsigned s=0;s<4;++s) {
            fprintf(out,"%s[",s?",":"");
            for(unsigned k=0;k<PO_KIND_COUNT;++k)
                fprintf(out,"%s%" PRIu64,k?",":"",__atomic_load_n(&counts[p][s][k],__ATOMIC_RELAXED));
            fprintf(out,"]");
        }
        fprintf(out,"]");
    }
    fprintf(out,"]}\n");
    if (ferror(out) || fflush(out)) die("write/flush error");
    if (fclose(out)) die("close error");
}
