// Exact component preservation BEFORE lossy compression, for experimental retention.
// A copied base and zero curve are insufficient if the decoder clips its range.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include "NVEncFilmGrainRetentionSelect.h"
#include "NVEncFilmGrainSyntax.h"

namespace fgsmodel {
// POD reduction result; valid only after the caller's device stream completes.
// Invalid storage padding bits count as invalid samples in the GPU version.
struct FilmGrainNativeComponentCounts {
    unsigned long long samples, changedSamples, invalidSamples;
    unsigned minimum, maximum;
};
struct FilmGrainSourceComponentCounts {
    FilmGrainRetentionFrame frame{};
    uint64_t modelId = 0; // Binds the full joint model AND the actual native base.
    unsigned component = 3;
    uint64_t samples = 0, changedSamples = 0, invalidSamples = 0;
    unsigned minimum = 0, maximum = 0;
    bool complete = false;
};

// Attach a COMPLETED measurement to its actual frame/model. This does not
// synchronize a device or establish the provenance of a caller-supplied scan.
inline FilmGrainSourceComponentCounts film_grain_source_component_counts_from_native(
    const FilmGrainRetentionFrame& frame, uint64_t modelId, unsigned component,
    const FilmGrainNativeComponentCounts& native) {
    FilmGrainSourceComponentCounts out;
    if (!frame.valid() || !modelId || component > 2
        || native.samples != uint64_t(frame.width) * frame.height / (component ? 4 : 1)
        || native.changedSamples > native.samples || native.invalidSamples > native.samples
        || native.minimum > native.maximum) return out;
    out.frame = frame; out.modelId = modelId; out.component = component;
    out.samples = native.samples; out.changedSamples = native.changedSamples;
    out.invalidSamples = native.invalidSamples; out.minimum = native.minimum; out.maximum = native.maximum;
    out.complete = true;
    return out;
}

// CPU reference over the COMPLETE component, including borders. Inputs are
// unpacked native integer codes; this must never dereference GPU frame pointers.
// A future device reduction must independently reproduce these exact counters.
inline FilmGrainSourceComponentCounts film_grain_source_component_counts(
    const FilmGrainRetentionFrame& frame, uint64_t modelId, unsigned component,
    const uint16_t* source, const uint16_t* base, size_t samples) {
    FilmGrainSourceComponentCounts out;
    if (!frame.valid() || !modelId || component > 2 || !source || !base
        || samples != uint64_t(frame.width) * frame.height / (component ? 4 : 1)) return out;
    out.frame = frame; out.modelId = modelId; out.component = component;
    out.minimum = (1u << frame.bitDepth) - 1;
    for (size_t i = 0; i < samples; ++i) {
        out.invalidSamples += source[i] >= (1u << frame.bitDepth) || base[i] >= (1u << frame.bitDepth);
        out.changedSamples += source[i] != base[i];
        if (source[i] < out.minimum) out.minimum = source[i];
        if (source[i] > out.maximum) out.maximum = source[i];
    }
    out.samples = samples; out.complete = true;
    return out;
}

// The caller supplies the current full-model identity and matrix interpretation.
// This proves pre-compression equality for ALL synthesis seeds. It does not
// prove compatibility with another component whose source noise is replaced.
inline bool film_grain_component_source_preserved(const FilmGrainSourceComponentCounts& counts,
    const FilmGrainRetentionFrame& frame, uint64_t modelId, unsigned component,
    const NV_ENC_FILM_GRAIN_PARAMS_AV1& params, bool matrixIdentity) {
    if (!frame.valid() || !modelId || component > 2 || !counts.complete
        || !(counts.frame == frame) || counts.modelId != modelId || counts.component != component
        || counts.samples != uint64_t(frame.width) * frame.height / (component ? 4 : 1)
        || counts.changedSamples || counts.invalidSamples || counts.minimum > counts.maximum
        || counts.maximum >= (1u << frame.bitDepth) || !film_grain_params_420_valid(params, frame.bitDepth)) return false;
    if (!params.applyGrain) return true;
    const bool fromY = component == 0 || params.chromaScalingFromLuma;
    const unsigned n = fromY ? params.numYPoints : component == 1 ? params.numCbPoints : params.numCrPoints;
    const uint8_t* scaling = fromY ? params.pointYScaling : component == 1 ? params.pointCbScaling : params.pointCrScaling;
    for (unsigned i = 0; i < n; ++i) if (scaling[i]) return false;
    // A present zero curve still runs the decoder's final pixel clamp.
    // Chroma-from-luma also activates it when the inherited Y curve is empty.
    const bool active = n > 0 || (component != 0 && params.chromaScalingFromLuma);
    if (active && params.clipToRestrictedRange) {
        const unsigned low = 16u << (frame.bitDepth - 8);
        const unsigned high = (component == 0 || matrixIdentity ? 235u : 240u) << (frame.bitDepth - 8);
        if (counts.minimum < low || counts.maximum > high) return false;
    }
    return true;
}
} // namespace fgsmodel
