// JSON interchange for development adapters only; not part of encoder ABI.
#pragma once
#include <fstream>
#include "NVEncFilmGrainMomentComparison.h"
#include "json.hpp"
namespace fgsdiagnostic {
using Json=nlohmann::json;
inline fgsmodel::FilmGrainNativeMoments moments(const Json& j) {
    fgsmodel::FilmGrainNativeMoments m;
    m.valid=j.at("valid"); m.width=j.at("width"); m.height=j.at("height"); m.depth=j.at("depth");
    m.mean=j.at("mean").get<decltype(m.mean)>(); m.blocks=j.at("blocks").get<decltype(m.blocks)>();
    if (j.at("folds").size()!=2) throw std::runtime_error("expected two folds");
    for (unsigned f=0;f<2;++f) {
        auto& a=m.folds[f]; const auto& b=j.at("folds").at(f);
        a.y=b.at("y").get<decltype(a.y)>(); a.colour=b.at("colour").get<decltype(a.colour)>();
        a.common=b.at("common").get<decltype(a.common)>(); a.cross=b.at("cross").get<decltype(a.cross)>();
    }
    return m;
}
inline fgsmodel::FilmGrainNativeMoments read(const Json& path) {
    std::ifstream file(path.get<std::string>()); Json j; file>>j; return moments(j);
}
inline Json moments(const fgsmodel::FilmGrainNativeMoments& m) {
    Json folds=Json::array();
    for (const auto& f:m.folds) folds.push_back({{"y",f.y},{"colour",f.colour},{"common",f.common},{"cross",f.cross}});
    return {{"valid",m.valid},{"width",m.width},{"height",m.height},{"depth",m.depth},
        {"blocks",m.blocks},{"mean",m.mean},{"folds",folds}};
}
inline Json matrix(const fgsmodel::FilmGrainMomentMatrixCheck& c) {
    return {{"valid",c.valid},{"variance",c.variance},{"covariance",c.covariance},{"pass_bounds",c.pass}};
}
inline Json comparison(const fgsmodel::FilmGrainMomentComparison& c) {
    Json folds=Json::array();
    for (const auto& f:c.folds) folds.push_back({{"valid",f.valid},{"y",matrix(f.y)},
        {"cb",matrix(f.cb)},{"cr",matrix(f.cr)},{"common",matrix(f.common)},
        {"cbcr_lag_max",f.cross},{"pass_bounds",f.fullPass},{"frame_pass",f.framePass}});
    return {{"valid",c.valid},{"mean_error",c.meanError},{"mean_pass",c.meanPass},
        {"folds",folds},{"pass_bounds",c.fullPass}};
}
inline Json selection(const fgsmodel::FilmGrainMomentSelection& s) {
    Json attempts=Json::array();
    for (const auto& a:s.attempts) attempts.push_back({{"seed",a.seed},{"calibrated",a.calibrated},
        {"scales",a.strengths},{"comparison",comparison(a.comparison)}});
    return {{"complete",s.complete},{"selected",s.selected},{"passes_diagnostic",s.passesDiagnostic},
        {"reason",int(s.reason)},{"attempts",attempts}};
}
} // namespace fgsdiagnostic
