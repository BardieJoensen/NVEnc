// Interactive manual adapter: a separate reference supplies measured variance.
#include <iostream>
#include "NVEncFilmGrainRetainedStrength.h"
#include "json.hpp"
using nlohmann::json;
int main() {
    json in; if (!(std::cin>>in)) return 2;
    fgsmodel::FilmGrainRetainedStrengthTarget target;
    target.channels=in.at("channels");
    target.missing=in.at("missing").get<std::array<double,2>>();
    target.source=in.at("source").get<std::array<double,2>>();
    const auto result=fgsmodel::film_grain_calibrate_retained_strength(target,
        [](unsigned strength) {
            std::cout<<json({{"measure",strength}}).dump()<<std::endl;
            json reply; fgsmodel::FilmGrainRetainedStrengthMeasurement m;
            if (!(std::cin>>reply) || reply.at("strength").get<unsigned>()!=strength) return m;
            m.valid=reply.at("valid"); m.variance=reply.at("variance").get<std::array<double,2>>();
            return m;
        });
    std::cout<<json({{"complete",true},{"valid",result.valid},{"strength",result.strength},
        {"error",result.error},{"evaluations",result.samples.size()}}).dump()<<std::endl;
}
