#pragma once

#include <algorithm>
#include <cmath>
#include <vector>

namespace fgsmodel {

// The scored top-decile fallback can include deterministic roof/foliage
// texture. It needs two adjacent, same-scene source pairs before repeatability
// can distinguish that structure from independent grain. During warmup retain
// the source: using only strict flats biases a brightness-dependent fit towards
// cleaner regions. Keep this history independent of rejected fits.
class FilmGrainTrainingHistory {
public:
    void reset() { means_.clear(); frames_ = 0; sigma_ = 0; }

    template<typename MeanAt>
    bool observe(bool adjacent, int count, MeanAt meanAt, double sigma8) {
        bool continuous = adjacent && static_cast<int>(means_.size()) == count
            && count > 0 && std::isfinite(sigma8) && sigma8 > 0;
        double delta = 0;
        int changed = 0;
        if (continuous) {
            for (int i = 0; i < count; ++i) {
                const double difference = std::abs(meanAt(i) - means_[i]);
                delta += difference;
                changed += difference >= 20;
            }
            const double ratio = sigma8 / std::max(.01, sigma_);
            continuous = !(delta / count >= 12 && changed >= std::ceil(count * .65))
                && ratio >= .55 && ratio <= 1.80;
        }
        frames_ = continuous ? std::min(3, frames_ + 1) : 1;
        means_.resize(std::max(0, count));
        for (int i = 0; i < count; ++i) means_[i] = meanAt(i);
        sigma_ = sigma8;
        return frames_ >= 3;
    }

    int missingPairs() const { return std::max(0, 3 - frames_); }

    static bool supported(bool historyReady, double repeatability) {
        if (!historyReady) return false;
        return std::isfinite(repeatability) && repeatability < .5;
    }

private:
    std::vector<float> means_;
    int frames_ = 0;
    double sigma_ = 0;
};

} // namespace fgsmodel
