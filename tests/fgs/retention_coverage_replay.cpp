// Manual policy replay of a complete native-population census. No media writes.
#include "NVEncFilmGrainRetentionSelect.h"
#include "json.hpp"
#include <fstream>
#include <iostream>
using namespace fgsmodel;
using nlohmann::json;
int main(int argc, char** argv) {
    json report = {{"complete", false}, {"cases", json::array()},
        {"scope", "Coverage only. No fitted model, joint compatibility or encoded-output qualification."}};
    try {
        if (argc != 3) throw std::runtime_error("usage: retention-coverage CENSUS REPORT");
        json manifest; std::ifstream(argv[1]) >> manifest;
        for (const auto& c : manifest.at("cases")) {
            const auto& f = c.at("frame");
            FilmGrainRetentionFrame frame{f.at("width"), f.at("height"), f.at("depth"),
                f.at("frame_id"), f.at("pts"), f.at("epoch"), f.at("population_id")};
            std::vector<FilmGrainRetentionPopulationCell> cells;
            for (const auto& row : c.at("cells")) {
                FilmGrainRetentionPopulationCell cell;
                cell.population = static_cast<FilmGrainRetentionPopulation>(row.at("population").get<unsigned>());
                cell.nativeLookup = row.at("native_lookup"); cell.scaling = row.at("scaling");
                cell.samples = row.at("samples"); cell.changedSamples = row.at("changed_samples");
                cell.trainBlocks = row.at("train_blocks"); cell.checkBlocks = row.at("check_blocks");
                cell.checks = {row.at("measured"), row.at("passed")}; cells.push_back(cell);
            }
            const auto r = film_grain_retention_coverage(frame, c.at("component"), cells);
            report["cases"].push_back({{"id", c.at("id")}, {"coverage_pass", r.reasons == 0},
                {"reasons", r.reasons}, {"samples", r.samples}, {"exact_zero_samples", r.exactZeroSamples},
                {"supported_samples", r.supportedSamples}, {"unsupported_synthesis_samples", r.unsupportedSynthesisSamples},
                {"unproven_changed_samples", r.unprovenChangedSamples}, {"population_samples", r.populationSamples}});
        }
        report["complete"] = true;
    } catch (const std::exception& error) { report["error"] = error.what(); std::cerr << error.what() << '\n'; }
    if (argc == 3) { std::ofstream output(argv[2]); output << report.dump(2) << '\n'; }
    return report["complete"].get<bool>() ? 0 : 1;
}
