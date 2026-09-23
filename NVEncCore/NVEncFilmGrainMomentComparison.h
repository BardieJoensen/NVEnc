// Finite development diagnostic policy, not source or perceptual admission.
// Keep individual failures alongside the separate eight-picture pooled policy.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include <deque>
#include <limits>
#include <vector>
#include "NVEncFilmGrainNativeMoments.h"

namespace fgsmodel {
struct FilmGrainMomentMatrixCheck {
    bool valid = false, pass = false;
    double variance = 0., covariance = 0.;
};
struct FilmGrainMomentFoldCheck {
    FilmGrainMomentMatrixCheck y{}, cb{}, cr{}, common{};
    double cross = 0.;
    bool valid = false, fullPass = false, framePass = false;
};
struct FilmGrainMomentComparison {
    std::array<double,3> meanError{};
    std::array<FilmGrainMomentFoldCheck,2> folds{};
    bool valid = false, meanPass = false, fullPass = false;
};

inline bool film_grain_moment_layout(const FilmGrainNativeMoments& m) {
    if (!m.valid || m.width < 64 || m.width > 4096 || m.height < 64
        || m.height > 2160 || m.width % 64 || m.height % 64
        || (m.depth != 8 && m.depth != 10)) return false;
    const uint64_t columns = m.width/64, rows = m.height/64;
    const std::array<uint64_t,2> expected = {(columns*rows+1)/2, columns*rows/2};
    return m.blocks == expected && expected[1] > 0;
}

inline bool film_grain_moment_same_layout(
    const FilmGrainNativeMoments& a, const FilmGrainNativeMoments& b) {
    return film_grain_moment_layout(a) && film_grain_moment_layout(b)
        && a.width == b.width && a.height == b.height && a.depth == b.depth
        && a.blocks == b.blocks;
}

template<size_t N>
inline FilmGrainMomentMatrixCheck film_grain_compare_moment_matrix(
    const std::array<double,N*N>& source, const std::array<double,N*N>& actual) {
    FilmGrainMomentMatrixCheck result;
    for (size_t i = 0; i < N; ++i) {
        if (!std::isfinite(source[i*N+i]) || source[i*N+i] <= 1e-12
            || !std::isfinite(actual[i*N+i]) || actual[i*N+i] < 0.) return result;
    }
    for (size_t i = 0; i < N; ++i) for (size_t j = 0; j < N; ++j) {
        if (!std::isfinite(source[i*N+j]) || !std::isfinite(actual[i*N+j])) return result;
        // Separate square roots avoid intermediate products overflowing.
        const double error = std::abs((actual[i*N+j]-source[i*N+j])
            /std::sqrt(source[i*N+i])/std::sqrt(source[j*N+j]));
        if (!std::isfinite(error)) return result;
        if (i == j) result.variance = std::max(result.variance, error);
        else result.covariance = std::max(result.covariance, error);
    }
    result.valid = true;
    result.pass = result.variance <= .08 && result.covariance <= .08;
    return result;
}

inline FilmGrainMomentComparison film_grain_compare_moments(
    const FilmGrainNativeMoments& source, const FilmGrainNativeMoments& actual) {
    FilmGrainMomentComparison result;
    if (!film_grain_moment_same_layout(source, actual)) return result;
    result.meanPass = true;
    for (unsigned c = 0; c < 3; ++c) {
        if (!std::isfinite(source.mean[c]) || !std::isfinite(actual.mean[c])) return {};
        result.meanError[c] = actual.mean[c]-source.mean[c];
        if (!std::isfinite(result.meanError[c])) return {};
        result.meanPass &= std::abs(result.meanError[c]) <= .125;
    }
    result.valid = true;
    result.fullPass = result.meanPass;
    for (unsigned fold = 0; fold < 2; ++fold) {
        const auto& a = source.folds[fold];
        const auto& b = actual.folds[fold];
        auto& check = result.folds[fold];
        check.y = film_grain_compare_moment_matrix<25>(a.y, b.y);
        check.cb = film_grain_compare_moment_matrix<26>(a.colour[0], b.colour[0]);
        check.cr = film_grain_compare_moment_matrix<26>(a.colour[1], b.colour[1]);
        check.common = film_grain_compare_moment_matrix<3>(a.common, b.common);
        check.valid = check.y.valid && check.cb.valid && check.cr.valid && check.common.valid;
        if (check.valid) for (unsigned i = 0; i < 49; ++i) {
            const double error = std::abs((b.cross[i]-a.cross[i])
                /std::sqrt(a.common[4])/std::sqrt(a.common[8]));
            if (!std::isfinite(error)) { check.valid = false; break; }
            check.cross = std::max(check.cross, error);
        }
        check.fullPass = check.valid && check.y.pass && check.cb.pass && check.cr.pass
            && check.common.pass && check.cross <= .08;
        check.framePass = check.valid && result.meanPass && check.y.pass
            && check.cb.variance <= .08 && check.cr.variance <= .08
            && check.common.variance <= .08;
        result.valid &= check.valid;
        result.fullPass &= check.fullPass;
    }
    return result;
}

// Equal-weight picture average, preserving the per-picture tile normalization.
// Caller supplies a single continuous segment. This never merges layouts or
// interprets invalid/quiet evidence as zero-valued valid covariance.
inline FilmGrainNativeMoments film_grain_average_moments(
    const FilmGrainNativeMoments* const* pictures, size_t count) {
    FilmGrainNativeMoments result;
    if (!pictures || !count || count > 8 || !pictures[0]
        || !film_grain_moment_layout(*pictures[0])) return result;
    result.width = pictures[0]->width; result.height = pictures[0]->height;
    result.depth = pictures[0]->depth; result.blocks = pictures[0]->blocks;
    auto add = [](auto& out, const auto& in) {
        for (size_t i = 0; i < out.size(); ++i) {
            if (!std::isfinite(in[i])) return false;
            out[i] += in[i];
            if (!std::isfinite(out[i])) return false;
        }
        return true;
    };
    for (size_t i = 0; i < count; ++i) {
        if (!pictures[i] || !film_grain_moment_same_layout(*pictures[0], *pictures[i])) return result;
        if (!add(result.mean, pictures[i]->mean)) return result;
        for (unsigned f = 0; f < 2; ++f) {
            auto& out = result.folds[f]; const auto& in = pictures[i]->folds[f];
            if (!add(out.y, in.y) || !add(out.common, in.common) || !add(out.cross, in.cross)
                || !add(out.colour[0], in.colour[0]) || !add(out.colour[1], in.colour[1])) return result;
        }
    }
    auto divide = [count](auto& values) { for (auto& value : values) value /= count; };
    divide(result.mean);
    for (auto& fold : result.folds) {
        divide(fold.y); divide(fold.colour[0]); divide(fold.colour[1]);
        divide(fold.common); divide(fold.cross);
    }
    result.valid = true;
    return result;
}

struct FilmGrainMomentCandidate {
    bool calibrated = false;
    std::array<unsigned,3> strengths{};
    FilmGrainNativeMoments moments{};
};
struct FilmGrainMomentAttempt {
    unsigned seed = 0;
    bool calibrated = false;
    std::array<unsigned,3> strengths{};
    FilmGrainMomentComparison comparison{};
};
enum class FilmGrainMomentSelectionReason { Invalid, NoTrainingCandidate, CheckFold, Pass };
enum class FilmGrainMomentSpatialPolicy { FrameWindow, FullPicture };
struct FilmGrainMomentSelection {
    FilmGrainMomentSelectionReason reason = FilmGrainMomentSelectionReason::Invalid;
    std::vector<FilmGrainMomentAttempt> attempts;
    int selected = -1;
    bool complete = false, passesDiagnostic = false;
};

// Callback executes calibration and measurement. The check fold NEVER selects
// the seed: failure on the first training-pass candidate rejects the trial.
// Supplied shape/base/eligible populations must remain fixed across attempts.
template<class Measure>
inline FilmGrainMomentSelection film_grain_select_moment_seed(
    const FilmGrainNativeMoments& source, const unsigned* seeds, size_t count, Measure measure,
    FilmGrainMomentSpatialPolicy policy=FilmGrainMomentSpatialPolicy::FrameWindow) {
    FilmGrainMomentSelection result;
    if (!film_grain_moment_layout(source) || !seeds || !count || count > 4) return result;
    if (policy!=FilmGrainMomentSpatialPolicy::FrameWindow && policy!=FilmGrainMomentSpatialPolicy::FullPicture) return result;
    for (size_t i = 0; i < count; ++i) {
        if (seeds[i] > 65535 || seeds[i] == 0 || seeds[i] == 18904 || seeds[i] == 46372) return result;
        for (size_t j = 0; j < i; ++j) if (seeds[i] == seeds[j]) return result;
    }
    result.reason = FilmGrainMomentSelectionReason::NoTrainingCandidate;
    for (size_t i = 0; i < count; ++i) {
        const auto candidate = measure(seeds[i]);
        FilmGrainMomentAttempt attempt;
        attempt.seed = seeds[i]; attempt.calibrated = candidate.calibrated;
        attempt.strengths = candidate.strengths;
        for (auto strength : attempt.strengths) if (strength > 255) attempt.calibrated = false;
        if (attempt.calibrated) attempt.comparison = film_grain_compare_moments(source, candidate.moments);
        result.attempts.push_back(attempt);
        const bool full=policy==FilmGrainMomentSpatialPolicy::FullPicture;
        // Full-picture mode selects using ONLY the training fold's spatial
        // statistics. The global mean includes independent pixels, so its
        // failure vetoes the selected seed instead of selecting another one.
        if (!(full ? attempt.comparison.folds[0].fullPass : attempt.comparison.folds[0].framePass)) continue;
        result.selected = int(i);
        result.passesDiagnostic = full ? attempt.comparison.fullPass : attempt.comparison.folds[1].framePass;
        result.reason = result.passesDiagnostic ? FilmGrainMomentSelectionReason::Pass
            : FilmGrainMomentSelectionReason::CheckFold;
        break;
    }
    result.complete = true;
    return result;
}

enum class FilmGrainMomentWindowReason { None, State, Identity, PerFrame, Pooled, Incomplete };
class FilmGrainMomentWindow {
    struct Pair { FilmGrainNativeMoments source, actual; };
    std::deque<Pair> pending_;
    uint64_t segment_ = 0, frames_ = 0, windows_ = 0;
    int64_t releaseThrough_ = -1;
    bool finished_ = false;
    FilmGrainMomentWindowReason reason_ = FilmGrainMomentWindowReason::None;
    FilmGrainMomentComparison lastWindow_{};
    bool reject(FilmGrainMomentWindowReason why) {
        if (reason_ == FilmGrainMomentWindowReason::None) reason_ = why;
        return false;
    }
public:
    // One object per continuous segment, starting at display-input ordinal 0.
    // Failure is terminal. A compressed partial base is not source fallback.
    bool push(uint64_t ordinal, uint64_t segment, const FilmGrainNativeMoments& source,
        const FilmGrainNativeMoments& actual) {
        if (reason_ != FilmGrainMomentWindowReason::None || finished_) return reject(FilmGrainMomentWindowReason::State);
        if (ordinal != frames_ || ordinal >= uint64_t(std::numeric_limits<int64_t>::max())
            || (frames_ && segment != segment_)) return reject(FilmGrainMomentWindowReason::Identity);
        if (!pending_.empty() && !film_grain_moment_same_layout(pending_.back().source, source))
            return reject(FilmGrainMomentWindowReason::Identity);
        const auto frame = film_grain_compare_moments(source, actual);
        if (!frame.folds[0].framePass || !frame.folds[1].framePass) return reject(FilmGrainMomentWindowReason::PerFrame);
        pending_.push_back({source,actual}); segment_ = segment; ++frames_;
        if (pending_.size() == 8) {
            std::array<const FilmGrainNativeMoments*,8> sources{}, outputs{};
            for (size_t i = 0; i < 8; ++i) { sources[i] = &pending_[i].source; outputs[i] = &pending_[i].actual; }
            lastWindow_ = film_grain_compare_moments(film_grain_average_moments(sources.data(),8),
                film_grain_average_moments(outputs.data(),8));
            if (!lastWindow_.fullPass) return reject(FilmGrainMomentWindowReason::Pooled);
            ++windows_; releaseThrough_ = int64_t(frames_-8); pending_.pop_front();
        }
        return true;
    }
    bool finish() {
        if (reason_ != FilmGrainMomentWindowReason::None || finished_) return reject(FilmGrainMomentWindowReason::State);
        if (!windows_) return reject(FilmGrainMomentWindowReason::Incomplete);
        finished_ = true; releaseThrough_ = int64_t(frames_-1); pending_.clear(); return true;
    }
    int64_t releaseThrough() const { return releaseThrough_; }
    uint64_t frames() const { return frames_; }
    uint64_t windows() const { return windows_; }
    FilmGrainMomentWindowReason reason() const { return reason_; }
    const FilmGrainMomentComparison& lastWindow() const { return lastWindow_; }
};
} // namespace fgsmodel
