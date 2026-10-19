/* Included only in the isolated SVT entropy_coding.c diagnostic build.
 * Each branch starts from the SAME real pre-TU coder/CDF state. Only the
 * original branch is returned to the encoder. No estimated RD costs here. */
static void rd_require(int ok, const char *why) {
    if (!ok) { fprintf(stderr, "Pantheon entropy validation failed: %s\n", why); abort(); }
}
static int rd_meta(const char *json, const char *key) {
    char needle[96]; snprintf(needle, sizeof(needle), "\"%s\":", key);
    const char *p = strstr(json, needle);
    rd_require(p != NULL, key);
    return atoi(p + strlen(needle));
}
typedef struct RdRecord {
    char meta[4096];
    int32_t initial[1024], final[1024];
    uint16_t initial_eob, final_eob;
    int have_initial, have_final, have_meta, have_initial_eob, have_final_eob;
} RdRecord;
static void rd_read(const char *path, int n, RdRecord *r) {
    FILE *f = fopen(path, "rb");
    if (!f) fprintf(stderr, "Missing TU: %s\n", path);
    rd_require(f != NULL, "missing keyed TU export");
    memset(r, 0, sizeof(*r));
    char key[33]; uint32_t count, size;
    size_t header_bytes;
    while ((header_bytes = fread(key, 1, 32, f)) != 0) {
        rd_require(header_bytes == 32, "partial trailing record header");
        key[32] = 0;
        rd_require(fread(&count, 4, 1, f) == 1 && fread(&size, 4, 1, f) == 1, "record header");
        size_t bytes = (size_t)count * size;
        void *dst = NULL;
        if (!strcmp(key, "meta")) {
            rd_require(size == 1 && bytes < sizeof(r->meta), "metadata size");
            dst = r->meta; r->have_meta = 1;
        } else if (!strcmp(key, "initial_qcoeff") || !strcmp(key, "final_qcoeff")) {
            rd_require(size == 4 && count == (uint32_t)n, "coefficient layout/length");
            if (key[0] == 'i') { dst = r->initial; r->have_initial = 1; }
            else { dst = r->final; r->have_final = 1; }
        } else if (!strcmp(key, "initial_eob") || !strcmp(key, "final_eob")) {
            rd_require(size == 2 && count == 1, "EOB layout");
            dst = key[0] == 'i' ? &r->initial_eob : &r->final_eob;
            if (key[0] == 'i') r->have_initial_eob = 1; else r->have_final_eob = 1;
        }
        if (dst) rd_require(fread(dst, 1, bytes, f) == bytes, "record payload");
        else {
            unsigned char discard[4096];
            while (bytes) {
                size_t chunk = bytes < sizeof(discard) ? bytes : sizeof(discard);
                rd_require(fread(discard, 1, chunk, f) == chunk, "unknown record payload");
                bytes -= chunk;
            }
        }
    }
    rd_require(feof(f) && !ferror(f) && r->have_meta, "TU complete");
    rd_require(!r->have_initial || (r->have_initial_eob && r->have_final && r->have_final_eob), "missing coefficient/EOB fields");
    fclose(f);
}
typedef struct RdClone {
    AomWriter writer;
    OutputBitstreamUnit owner;
    FRAME_CONTEXT cdf;
    EntropyCodingContext scratch;
} RdClone;
static RdClone *rd_clone(const AomWriter *w, const FRAME_CONTEXT *cdf, const EntropyCodingContext *scratch) {
    RdClone *c = malloc(sizeof(*c)); rd_require(c != NULL, "clone allocation");
    c->writer = *w; c->owner = *w->buffer_parent; c->cdf = *cdf; c->scratch = *scratch;
    rd_require(w->ec.buf == w->buffer_parent->buffer_begin_av1, "unexpected writer buffer origin");
    size_t written = (size_t)(w->ec.ptr-w->ec.buf), old_size = w->buffer_parent->size;
    rd_require(written <= old_size, "writer capacity");
    c->owner.size = old_size + 131072; /* private spare space for dense alternate */
    c->owner.buffer_begin_av1 = calloc(1, c->owner.size);
    rd_require(c->owner.buffer_begin_av1 != NULL, "clone buffer allocation");
    memcpy(c->owner.buffer_begin_av1, w->ec.buf, old_size);
    c->owner.buffer_av1 = w->buffer_parent->buffer_av1 ? c->owner.buffer_begin_av1 +
        (w->buffer_parent->buffer_av1-w->buffer_parent->buffer_begin_av1) : NULL;
    c->writer.buffer_parent = &c->owner;
    c->writer.ec.buf = c->owner.buffer_begin_av1;
    c->writer.ec.ptr = c->writer.ec.buf + written;
    return c;
}
static void rd_free(RdClone *c) { free(c->owner.buffer_begin_av1); free(c); }
static int rd_same(const RdClone *c, const AomWriter *w, const FRAME_CONTEXT *cdf, int *bytes, int *cdf_equal) {
    const OdEcEnc *a = &c->writer.ec, *b = &w->ec;
    size_t na = a->ptr-a->buf, nb = b->ptr-b->buf;
    *bytes = na == nb && !memcmp(a->buf, b->buf, nb);
    *cdf_equal = !memcmp(&c->cdf, cdf, sizeof(*cdf));
    return a->low == b->low && a->rng == b->rng && a->cnt == b->cnt && a->error == b->error &&
        na == nb && c->writer.allow_update_cdf == w->allow_update_cdf && c->writer.pos == w->pos &&
        svt_od_ec_enc_tell_frac(a) == svt_od_ec_enc_tell_frac(b);
}
static int32_t av1_write_coeffs_txb_1d(PictureParentControlSet* ppcs, FRAME_CONTEXT* frame_context, MbModeInfo* mbmi,
    AomWriter* ec_writer, EcBlkStruct* blk_ptr, TxSize tx_size, uint32_t txb_index,
    uint32_t intraLumaDir, int32_t* coeff_buffer_ptr, COMPONENT_TYPE component_type,
    int16_t txb_skip_ctx, int16_t dc_sign_ctx, int16_t eob, EntropyCodingContext* ec_ctx) {
    const char *dir = getenv("PANTHEON_RD_DETAIL_INPUT"), *frames = getenv("PANTHEON_RD_POC");
    char needle[32]; snprintf(needle, sizeof(needle), ",%llu,", (unsigned long long)ppcs->picture_number);
    int active = component_type == COMPONENT_LUMA && dir && frames && strstr(frames, needle);
    if (!active) return av1_write_coeffs_txb_1d_impl(ppcs, frame_context, mbmi, ec_writer, blk_ptr,
        tx_size, txb_index, intraLumaDir, coeff_buffer_ptr, component_type, txb_skip_ctx, dc_sign_ctx, eob, ec_ctx);
    rd_require(getenv("PANTHEON_TRACE_DIR") == NULL, "disable old trace side effects for cloned calls");
    rd_require(!mbmi->block_mi.skip, "whole-block skip is outside TU diagnostic");
    int w = tx_size_wide[tx_size], h = tx_size_high[tx_size], n = av1_get_max_eob(tx_size);
    rd_require(w <= 32 && h <= 32 && n <= 1024, "supported TX32 control required");
    int inter = is_inter_mode(mbmi->block_mi.mode) || mbmi->block_mi.use_intrabc;
    Position org = tx_org[mbmi->bsize][inter][mbmi->block_mi.tx_depth][txb_index];
    unsigned xx = pt_blk_x + org.x, yy = pt_blk_y + org.y;
    char path[2048]; snprintf(path, sizeof(path), "%s/%04llu-%04u-%04u.tu", dir,
        (unsigned long long)ppcs->picture_number, xx, yy);
    RdRecord r; rd_read(path, n, &r);
    rd_require(rd_meta(r.meta, "poc") == (int)ppcs->picture_number && rd_meta(r.meta, "x") == (int)xx &&
        rd_meta(r.meta, "y") == (int)yy && rd_meta(r.meta, "w") == w && rd_meta(r.meta, "h") == h &&
        rd_meta(r.meta, "block_x") == (int)pt_blk_x && rd_meta(r.meta, "block_y") == (int)pt_blk_y &&
        rd_meta(r.meta, "tx_size") == (int)tx_size && rd_meta(r.meta, "bsize") == (int)mbmi->bsize &&
        rd_meta(r.meta, "mode") == (int)mbmi->block_mi.mode &&
        rd_meta(r.meta, "effective_qindex") == blk_ptr->qindex, "key/geometry/mode/quantizer mismatch");
    if (!r.have_initial) {
        rd_require(!r.have_final && eob == 0, "bypass mismatch");
        return av1_write_coeffs_txb_1d_impl(ppcs, frame_context, mbmi, ec_writer, blk_ptr,
            tx_size, txb_index, intraLumaDir, coeff_buffer_ptr, component_type, txb_skip_ctx, dc_sign_ctx, eob, ec_ctx);
    }
    rd_require(r.have_final && r.final_eob == eob && !memcmp(r.final, coeff_buffer_ptr, n*sizeof(int32_t)),
        "exported final vector differs from coded vector");
    int exercised = rd_meta(r.meta, "tx_type"), final_type = blk_ptr->tx_type[txb_index];
    rd_require((eob == 0 && final_type == DCT_DCT) || final_type == exercised, "transform reset mismatch");
    const int16_t *scan = get_scan_order(tx_size, exercised)->scan;
    int derived_eob = 0;
    for (int k = 0; k < n; k++) if (r.initial[scan[k]]) derived_eob = k+1;
    rd_require(derived_eob == r.initial_eob, "retained EOB/scan mismatch");
    uint32_t before = svt_od_ec_enc_tell_frac(&ec_writer->ec);
    RdClone *same = rd_clone(ec_writer, frame_context, ec_ctx), *alt = rd_clone(ec_writer, frame_context, ec_ctx);
    EcBlkStruct same_blk = *blk_ptr, alt_blk = *blk_ptr;
    MbModeInfo same_mi = *mbmi, alt_mi = *mbmi;
    int32_t same_ret = av1_write_coeffs_txb_1d_impl(ppcs, &same->cdf, &same_mi, &same->writer, &same_blk,
        tx_size, txb_index, intraLumaDir, coeff_buffer_ptr, component_type, txb_skip_ctx, dc_sign_ctx, eob, &same->scratch);
    alt_blk.tx_type[txb_index] = r.initial_eob ? exercised : DCT_DCT;
    av1_write_coeffs_txb_1d_impl(ppcs, &alt->cdf, &alt_mi, &alt->writer, &alt_blk,
        tx_size, txb_index, intraLumaDir, r.initial, component_type, txb_skip_ctx, dc_sign_ctx, r.initial_eob, &alt->scratch);
    int32_t ret = av1_write_coeffs_txb_1d_impl(ppcs, frame_context, mbmi, ec_writer, blk_ptr,
        tx_size, txb_index, intraLumaDir, coeff_buffer_ptr, component_type, txb_skip_ctx, dc_sign_ctx, eob, ec_ctx);
    int bytes, cdf_equal;
    int state = rd_same(same, ec_writer, frame_context, &bytes, &cdf_equal);
    rd_require(state && bytes && cdf_equal && ret == same_ret, "same-symbol clone fails real coder equivalence");
    uint32_t base_after = svt_od_ec_enc_tell_frac(&ec_writer->ec), alt_after = svt_od_ec_enc_tell_frac(&alt->writer.ec);
    int changed = memcmp(r.initial, r.final, n*sizeof(int32_t)) != 0;
    if (!changed) rd_require(base_after == alt_after, "unchanged vector has different bit cost");
    const char *log = getenv("PANTHEON_RD_LOG"); rd_require(log != NULL, "log path required");
    FILE *f = fopen(log, "a"); rd_require(f != NULL, "log open");
    fprintf(f, "{\"poc\":%llu,\"x\":%u,\"y\":%u,\"w\":%d,\"h\":%d,\"effective_qindex\":%u,"
        "\"block_skip\":0,\"tx_type_exercised\":%d,\"tx_type_final\":%d,\"initial_eob\":%u,\"final_eob\":%d,"
        "\"before_tell_frac\":%u,\"baseline_after_tell_frac\":%u,\"retained_after_tell_frac\":%u,"
        "\"baseline_bits\":%.3f,\"retained_bits\":%.3f,\"delta_bits\":%.3f,\"changed\":%d,"
        "\"clone_state_equal\":%d,\"clone_bytes_equal\":%d,\"clone_cdf_equal\":%d,\"allow_update_cdf\":%u}\n",
        (unsigned long long)ppcs->picture_number, xx, yy, w, h, blk_ptr->qindex, exercised, final_type,
        r.initial_eob, eob, before, base_after, alt_after, ((int64_t)base_after-before)/8.,
        ((int64_t)alt_after-before)/8., ((int64_t)alt_after-base_after)/8., changed, state, bytes, cdf_equal, ec_writer->allow_update_cdf);
    fclose(f); rd_free(same); rd_free(alt);
    return ret;
}
