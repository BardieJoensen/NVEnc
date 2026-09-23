/*
 * AV1 film-grain seed correction experiment.
 * Copyright (c) 2026
 *
 * This file is part of FFmpeg and is distributed under the GNU Lesser
 * General Public License, version 2.1 or later. See COPYING.LGPLv2.1.
 */

#include "libavutil/common.h"
#include "libavutil/mem.h"
#include "bsf_internal.h"
#include "cbs.h"
#include "get_bits.h"

#define MAX_SEED_FIELDS 4096
#define MAX_PACKET_BYTES (32 * 1024 * 1024)

typedef struct AV1GrainSeedField {
    unsigned bit;
    uint16_t before;
} AV1GrainSeedField;

typedef struct AV1GrainSeedContext {
    CodedBitstreamContext *cbc;
    CodedBitstreamFragment fragment;
    const uint8_t *packet_data;
    size_t packet_size;
    AV1GrainSeedField fields[MAX_SEED_FIELDS];
    unsigned nb_fields;
    int error, failed;
} AV1GrainSeedContext;

/* CBS supplies the parsed syntax element and its precise bit position. This
 * callback belongs to this parser instance; it does not change global logging.
 * Record edits only, then apply them after the ENTIRE packet parses correctly.
 */
static void av1_grain_seed_trace(void *opaque, GetBitContext *gb,
                                 int length, const char *name,
                                 const int *subscripts, int64_t value)
{
    AV1GrainSeedContext *ctx = opaque;
    uintptr_t buffer, begin;
    size_t bit;
    int position;
    (void)subscripts;
    if (strcmp(name, "grain_seed") ||
        (value != 0 && value != 46372 && value != 18904))
        return;
    position = get_bits_count(gb);
    buffer = (uintptr_t)gb->buffer;
    begin = (uintptr_t)ctx->packet_data;
    if (!ctx->packet_data || length != 16 || position < 0 ||
        get_bits_left(gb) < 16 || buffer < begin ||
        buffer - begin >= ctx->packet_size ||
        (size_t)position > ctx->packet_size * 8 ||
        show_bits(gb, 16) != value || ctx->nb_fields == MAX_SEED_FIELDS) {
        ctx->error = AVERROR_INVALIDDATA;
        return;
    }
    bit = (buffer - begin) * 8 + position;
    if (bit + 16 > ctx->packet_size * 8 ||
        (ctx->nb_fields && bit < ctx->fields[ctx->nb_fields - 1].bit + 16)) {
        ctx->error = AVERROR_INVALIDDATA;
        return;
    }
    ctx->fields[ctx->nb_fields++] = (AV1GrainSeedField){bit, value};
}

static int av1_grain_seed_init(AVBSFContext *bsf)
{
    AV1GrainSeedContext *ctx = bsf->priv_data;
    int err = ff_cbs_init(&ctx->cbc, AV_CODEC_ID_AV1, bsf);
    if (err < 0)
        return err;
    ctx->cbc->trace_enable = 1;
    ctx->cbc->trace_level = AV_LOG_TRACE;
    ctx->cbc->trace_context = ctx;
    ctx->cbc->trace_read_callback = av1_grain_seed_trace;
    if (bsf->par_in->extradata) {
        err = ff_cbs_read_extradata(ctx->cbc, &ctx->fragment, bsf->par_in);
        ff_cbs_fragment_reset(&ctx->fragment);
    }
    return err < 0 ? err : ctx->error;
}

static int av1_grain_seed_filter(AVBSFContext *bsf, AVPacket *pkt)
{
    AV1GrainSeedContext *ctx = bsf->priv_data;
    unsigned i, j;
    int err = ff_bsf_get_packet_ref(bsf, pkt);
    if (err < 0)
        return err;
    if (ctx->failed) {
        av_packet_unref(pkt);
        return AVERROR_INVALIDDATA;
    }
    ctx->error = 0;
    ctx->nb_fields = 0;
    ctx->packet_data = NULL;
    ctx->packet_size = 0;
    if (pkt->size <= 0 || pkt->size > MAX_PACKET_BYTES) {
        err = AVERROR_INVALIDDATA;
        goto fail;
    }
    if (av_packet_get_side_data(pkt, AV_PKT_DATA_NEW_EXTRADATA, NULL)) {
        err = ff_cbs_read_packet_side_data(ctx->cbc, &ctx->fragment, pkt);
        ff_cbs_fragment_reset(&ctx->fragment);
        if (err < 0 || ctx->error)
            goto fail;
    }
    ctx->packet_data = pkt->data;
    ctx->packet_size = pkt->size;
    err = ff_cbs_read_packet(ctx->cbc, &ctx->fragment, pkt);
    ff_cbs_fragment_reset(&ctx->fragment);
    ctx->packet_data = NULL;
    if (err < 0 || ctx->error)
        goto fail;
    if (!ctx->nb_fields)
        return 0; /* Ordinary packets stay byte-identical and need no copy. */
    err = av_packet_make_writable(pkt);
    if (err < 0)
        goto fail;
    /* Recheck every planned edit before modifying even the first bit. */
    for (i = 0; i < ctx->nb_fields; i++) {
        unsigned found = 0;
        for (j = 0; j < 16; j++) {
            const unsigned bit = ctx->fields[i].bit + j;
            found = (found << 1) | ((pkt->data[bit / 8] >> (7 - bit % 8)) & 1);
        }
        if (found != ctx->fields[i].before) {
            err = AVERROR_INVALIDDATA;
            goto fail;
        }
    }
    for (i = 0; i < ctx->nb_fields; i++) {
        const unsigned next = ctx->fields[i].before + 1;
        for (j = 0; j < 16; j++) {
            const unsigned bit = ctx->fields[i].bit + j;
            const uint8_t mask = 1u << (7 - bit % 8);
            pkt->data[bit / 8] = (pkt->data[bit / 8] & ~mask) |
                (((next >> (15 - j)) & 1) ? mask : 0);
        }
    }
    return 0;
fail:
    /* A failed parse may have consumed reference state. Never continue with
     * that state after an error; an explicit flush recreates the parser. */
    ctx->failed = 1;
    ctx->packet_data = NULL;
    av_packet_unref(pkt);
    return err < 0 ? err : ctx->error;
}

static void av1_grain_seed_close(AVBSFContext *bsf)
{
    AV1GrainSeedContext *ctx = bsf->priv_data;
    ff_cbs_fragment_free(&ctx->fragment);
    ff_cbs_close(&ctx->cbc);
}

static void av1_grain_seed_flush(AVBSFContext *bsf)
{
    AV1GrainSeedContext *ctx = bsf->priv_data;
    av1_grain_seed_close(bsf);
    ctx->packet_data = NULL;
    ctx->packet_size = 0;
    ctx->nb_fields = 0;
    ctx->error = ctx->failed = 0;
    if (av1_grain_seed_init(bsf) < 0)
        ctx->failed = 1;
}

const FFBitStreamFilter ff_av1_grain_seed_bsf = {
    .p.name         = "av1_grain_seed",
    .p.codec_ids    = (const enum AVCodecID[]){ AV_CODEC_ID_AV1, AV_CODEC_ID_NONE },
    .priv_data_size = sizeof(AV1GrainSeedContext),
    .init           = av1_grain_seed_init,
    .filter         = av1_grain_seed_filter,
    .flush          = av1_grain_seed_flush,
    .close          = av1_grain_seed_close,
};
