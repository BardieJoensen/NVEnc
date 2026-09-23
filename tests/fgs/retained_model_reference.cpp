// Manual JSON adapter for independent whole-frame candidate experiments.
#include <iostream>
#include <string>
#include "NVEncFilmGrainRetainedModel.h"
#include "json.hpp"
using nlohmann::json;
int main() {
    std::string line;
    while (std::getline(std::cin, line)) {
        const auto in = json::parse(line);
        const auto l = in.at("luma");
        fgsmodel::FilmGrainJointTemplateParameters p;
        p.bitDepth = l.at("depth"); p.lag = 3; p.arShift = l.at("shift");
        p.grainShift = l.at("grain_shift"); p.lumaActive = p.cbActive = p.crActive = true;
        const auto coefficients = l.at("coefficients").get<std::vector<int>>();
        if (coefficients.size() != 24) return 2;
        for (unsigned i = 0; i < 24; ++i) {
            if (coefficients[i] < -128 || coefficients[i] > 127) return 2;
            p.y[i] = coefficients[i] + 128;
        }
        const auto seeds = in.at("seeds").get<std::vector<uint16_t>>();
        auto luma = fgsmodel::film_grain_retained_luma(p, seeds.data(), seeds.size());
        uint32_t nativeReasons = 0;
        if (in.contains("native_luma")) {
            std::vector<fgsmodel::FilmGrainRetainedLumaMoments> native;
            for (const auto& group : in.at("native_luma")) {
                fgsmodel::FilmGrainRetainedLumaMoments m;
                m.blocks = group.at("blocks"); m.observations = group.at("observations");
                m.source = group.at("source").get<fgsmodel::FilmGrainRetainedLumaMatrix>();
                m.base = group.at("base").get<fgsmodel::FilmGrainRetainedLumaMatrix>();
                m.sourceBase = group.at("sourceBase").get<fgsmodel::FilmGrainRetainedLumaMatrix>();
                native.push_back(m);
            }
            const auto fit = fgsmodel::film_grain_fit_retained_luma(native, p.bitDepth,
                p.arShift, p.grainShift, seeds.data(), seeds.size());
            luma = fit.luma; nativeReasons = fit.reasons;
        }
        std::vector<fgsmodel::FilmGrainJointMoments> groups;
        for (const auto& group : in.at("groups")) {
            fgsmodel::FilmGrainJointMoments m;
            m.blocks = group.at("blocks"); m.observations = group.at("observations");
            m.source = group.at("source").get<fgsmodel::FilmGrainJointMatrix>();
            m.base = group.at("base").get<fgsmodel::FilmGrainJointMatrix>();
            m.sourceBase = group.at("sourceBase").get<fgsmodel::FilmGrainJointMatrix>();
            groups.push_back(m);
        }
        const auto model = fgsmodel::film_grain_fit_retained_chroma(groups, luma);
        std::array<int, 25> signedCoefficients{};
        for (unsigned i = 0; i < 25; ++i) signedCoefficients[i] = int(model.coefficients[i])-128;
        std::array<int, 24> signedLuma{};
        for (unsigned i = 0; i < 24; ++i) signedLuma[i] = int(luma.parameters().y[i])-128;
        json out = {{"valid", model.valid()}, {"reasons", model.reasons},
            {"luma_valid", luma.valid()}, {"luma_gain", luma.power().nominalLumaGain},
            {"native_luma_reasons", nativeReasons}, {"luma_coefficients", signedLuma},
            {"luma_driver_power", luma.power().roundedAverageLumaPower},
            {"coefficients", signedCoefficients}, {"predictors", model.groupPredictors},
            {"training_excess", model.quantizedTrainingExcess},
            {"fit_excess", model.balanced.maximumRelativeExcess},
            {"fit_gap", model.balanced.dualityGap}, {"fit_iterations", model.balanced.iterations}};
        std::cout << out.dump() << '\n';
    }
}
