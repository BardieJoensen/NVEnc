#pragma once

namespace fgsmodel {

// Source preservation and synthesized grain can have different local texture.
// After falling back, a single acceptable fit is not evidence that it is safe
// to switch back. Keep the source until a settled rolling window remains usable
// for the normal 24-frame model-update interval. This state is deliberately
// independent of the fit history: low-confidence frames clear that history.
class FilmGrainSynthesisRecovery {
public:
    static constexpr int recoveryFrames = 24;

    void reset() { m_active = false; m_frames = 0; }
    void preserveSource() { m_active = true; m_frames = 0; }

    bool allow(bool modelAvailable, bool freshFit, bool settledWindow) {
        if (!modelAvailable) {
            preserveSource();
            return false;
        }
        if (!m_active) return true;
        if (!freshFit || !settledWindow) {
            m_frames = 0;
            return false;
        }
        if (++m_frames < recoveryFrames) return false;
        reset();
        return true;
    }

    bool active() const { return m_active; }
    int frames() const { return m_frames; }

private:
    bool m_active = false;
    int m_frames = 0;
};

} // namespace fgsmodel
