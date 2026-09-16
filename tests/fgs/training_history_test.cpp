#include <cstdlib>
#include <iostream>
#include <limits>
#include <vector>
#include "NVEncFilmGrainTraining.h"

static void require(bool value, const char *message) {
    if (!value) { std::cerr << message << '\n'; std::exit(1); }
}

int main() {
    using fgsmodel::FilmGrainTrainingHistory;
    FilmGrainTrainingHistory h;
    std::vector<float> means(100, 100);
    auto step = [&](bool adjacent, double sigma=6) {
        return h.observe(adjacent, static_cast<int>(means.size()), [&](int i) { return means[i]; }, sigma);
    };
    require(!step(false) && !step(true) && step(true), "scored training lacked two source pairs");
    require(step(true), "continuous independent grain lost history");
    require(!FilmGrainTrainingHistory::supported(false,0), "strict-only startup biased the brightness fit");
    require(!FilmGrainTrainingHistory::supported(false,0), "unproven texture trained during warmup");
    require(!FilmGrainTrainingHistory::supported(true,1), "repeated texture trained as random grain");
    require(FilmGrainTrainingHistory::supported(true,.1), "independent strong grain rejected");
    require(!FilmGrainTrainingHistory::supported(true,std::numeric_limits<double>::quiet_NaN()), "invalid repeatability accepted");
    std::fill(means.begin(),means.end(),150);
    require(!step(true) && !step(true) && step(true), "scene cut borrowed old texture history");
    require(!step(true,20) && !step(true,20) && step(true,20), "noise transition borrowed old history");
    require(!step(false,20), "nonadjacent source retained training history");
    h.reset();
    require(!step(false), "fresh sequence unexpectedly qualified");
    require(h.missingPairs() == 2, "startup must require two independent adjacent pairs");
    auto ahead = h;
    require(!ahead.observe(true, 100, [&](int i) { return means[i]; }, 6), "one future pair qualified startup");
    require(ahead.observe(true, 100, [&](int i) { return means[i]; }, 6), "two future pairs did not qualify startup");
    require(h.missingPairs() == 2, "lookahead mutated causal history");
    ahead = h;
    require(!ahead.observe(true, 100, [](int) { return 40.0; }, 6), "future cut borrowed present history");
    require(!ahead.observe(true, 100, [](int) { return 40.0; }, 6), "future scene qualified earlier picture");
    h.reset();
    require(!step(true), "explicit reset retained training history");
    means.resize(80);
    require(!step(true), "geometry change retained training history");
    std::cout << "source training history tests passed\n";
}
