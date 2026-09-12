#pragma once

#include <algorithm>
#include <cmath>

namespace fgsmodel {

// Source preservation and synthesized grain can have different local texture.
// After falling back, a single acceptable fit is not evidence that it is safe
// to switch back. Keep the source until a settled rolling window remains usable
// for the normal 24-frame model-update interval. This state is deliberately
// independent of the fit history: low-confidence frames clear that history.
class FilmGrainSynthesisRecovery {
public:
    static constexpr int recoveryFrames = 24;
    static constexpr int rampFrames = 16;

    void reset() { m_active = false; m_frames = 0; m_ramp = rampFrames; }
    void preserveSource() { m_active = true; m_frames = 0; m_ramp = 0; }

    bool allow(bool modelAvailable, bool freshFit, bool settledWindow) {
        if (!modelAvailable) {
            preserveSource();
            return false;
        }
        if (!m_active) {
            if (freshFit && m_ramp < rampFrames) ++m_ramp;
            return true;
        }
        if (!freshFit || !settledWindow) {
            m_frames = 0;
            return false;
        }
        if (++m_frames < recoveryFrames) return false;
        // Past evidence cannot promise that the next frame remains usable.
        // Introduce synthesis gradually so an immediate new rejection does
        // not leave a full-strength one-frame overlay in the output.
        m_active = false;
        m_frames = 0;
        m_ramp = 1;
        return true;
    }

    bool active() const { return m_active; }
    int frames() const { return m_frames; }
    double gain() const { return static_cast<double>(m_ramp) / rampFrames; }

private:
    bool m_active = false;
    int m_frames = 0;
    int m_ramp = rampFrames;
};

// Apply after any existing luma residual retention. Given its coefficient r,
// blend an additional q of source into that base, so the combined coefficient
// R = r + q*(1-r) satisfies R^2 + gain^2*(1-r^2) = 1. Scaling grain without
// this matching source blend would temporarily remove the original texture.
inline double film_grain_recovery_source_blend(double gain, double retained) {
    gain = std::clamp(gain, 0.0, 1.0);
    retained = std::clamp(retained, 0.0, 1.0);
    if (retained == 1.0 || gain == 1.0) return 0.0;
    const double combined = std::sqrt(std::max(0.0, 1.0 - gain * gain * (1.0 - retained * retained)));
    return std::clamp((combined - retained) / (1.0 - retained), 0.0, 1.0);
}

} // namespace fgsmodel
