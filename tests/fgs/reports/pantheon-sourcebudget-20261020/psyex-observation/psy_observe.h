#ifndef PANTHEON_PSY_OBSERVE_H
#define PANTHEON_PSY_OBSERVE_H
#include <stdint.h>
#include "EbSvtAv1Enc.h"
enum PsyObsKind {
    PO_OPT_ENTER, PO_OPT_LUMA, PO_OPT_EARLY_RATE, PO_OPT_EARLY_EOB,
    PO_OPT_GUARD, PO_OPT_ZERO_WEIGHT, PO_OPT_COMPLETE, PO_NOISE_CALL,
    PO_FAST_CALL, PO_FAST_NONZERO, PO_TX_PRED_CALL, PO_TX_PRED_NONZERO,
    PO_TX_RECON_CALL, PO_TX_RECON_NONZERO, PO_FULL_SPATIAL, PO_FULL_TX_DOMAIN,
    PO_FULL_PRED_CALL, PO_FULL_PRED_NONZERO, PO_FULL_RECON_CALL, PO_FULL_RECON_NONZERO,
    PO_ZERO_COMPARE, PO_ZERO_CHOICE, PO_ZERO_SPATIAL_COMPARE,
    PO_SKIPMODE_COMPARE, PO_SKIPMODE_CHOICE, PO_SKIPMODE_SPATIAL_COMPARE,
    PO_MODE_CALL, PO_MODE_CANDIDATES, PO_MODE_HBD, PO_MODE_SPATIAL,
    PO_MODE_INTER, PO_MODE_INTRA, PO_MODE_SKIP, PO_MODE_COEFF, PO_KIND_COUNT
};
void psy_obs_add(uint64_t picture, unsigned md_stage, enum PsyObsKind kind, uint64_t amount);
uint64_t psy_obs_term(uint64_t picture, unsigned md_stage, enum PsyObsKind call_kind,
                      enum PsyObsKind nonzero_kind, uint64_t value);
void psy_obs_flush(const EbSvtAv1EncConfiguration *cfg, unsigned instances);
#define PO_COUNT(pcs, ctx, kind) psy_obs_add((pcs)->picture_number, (ctx)->md_stage, (kind), 1)
#endif
