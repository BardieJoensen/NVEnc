// Replay independently recorded synthesis measurements through the batch search.
#include <iostream>
#include <stdexcept>
#include "NVEncFilmGrainRetainedStrengthBatch.h"
#include "json.hpp"
using Json=nlohmann::json;
int main() {
    try {
        Json j;std::cin>>j;const auto source=j.at("source").get<std::array<double,4>>();
        const auto base=j.at("base").get<std::array<double,4>>();
        std::array<fgsmodel::FilmGrainRetainedStrengthTarget,3> targets{};
        const unsigned indexes[3][2]={{0,1},{2,2},{3,3}};
        for(unsigned c=0;c<3;++c) {
            targets[c].channels=c?1:2;
            for(unsigned k=0;k<targets[c].channels;++k) {
                const auto i=indexes[c][k];targets[c].source[k]=source[i];targets[c].missing[k]=source[i]-base[i];
            }
        }
        size_t next=0;
        const auto result=fgsmodel::film_grain_calibrate_retained_strength_batch(targets,[&](const std::array<unsigned,3>& strengths) {
            const auto& row=j.at("measurements").at(next++);
            if(row.at("scales").get<std::array<unsigned,3>>()!=strengths)throw std::runtime_error("recorded batch request differs");
            const auto variance=row.at("total_variance").get<std::array<double,4>>();
            std::array<fgsmodel::FilmGrainRetainedStrengthMeasurement,3> measured;
            for(unsigned c=0;c<3;++c) {
                measured[c].valid=true;
                for(unsigned k=0;k<targets[c].channels;++k){const auto i=indexes[c][k];measured[c].variance[k]=variance[i]-base[i];}
            }
            return measured;
        });
        Json components=Json::array();for(const auto& c:result.components)components.push_back({{"valid",c.valid},{"strength",c.strength},{"error",c.error},{"evaluations",c.samples.size()}});
        if(next!=j.at("measurements").size())throw std::runtime_error("unused recorded measurement");
        std::cout<<Json({{"complete",result.complete},{"valid",result.valid},{"components",components},{"synthesis_calls",next}}).dump()<<'\n';return result.complete?0:1;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
