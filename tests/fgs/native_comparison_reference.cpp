#include <iostream>
#include "native_moments_json.h"
using namespace fgsmodel;
using fgsdiagnostic::Json;
int main() {
    try {
        Json input; std::cin>>input; Json output=Json::array();
        if (!input.is_array() || input.size()>1024) throw std::runtime_error("case budget");
        for (const auto& j:input) {
            const std::string mode=j.at("mode"); Json result;
            if (mode=="compare") {
                result=fgsdiagnostic::comparison(film_grain_compare_moments(
                    fgsdiagnostic::read(j.at("source")),fgsdiagnostic::read(j.at("actual"))));
            } else if (mode=="window") {
                const auto& rows=j.at("rows");
                if (!rows.is_array() || rows.size()>64) throw std::runtime_error("frame budget");
                FilmGrainMomentWindow window; Json checks=Json::array();
                for (const auto& row:rows) {
                    const auto old=window.windows();
                    const bool pass=window.push(row.at("ordinal"),row.at("segment"),
                        fgsdiagnostic::read(row.at("source")),fgsdiagnostic::read(row.at("actual")));
                    Json step={{"pass",pass},{"release_through",window.releaseThrough()},{"windows",window.windows()}};
                    if (window.windows()!=old || window.reason()==FilmGrainMomentWindowReason::Pooled)
                        step["comparison"]=fgsdiagnostic::comparison(window.lastWindow());
                    checks.push_back(step);
                    if (!pass) break;
                }
                const bool finished=window.finish();
                result={{"complete",finished},{"reason",int(window.reason())},{"frames",window.frames()},
                    {"release_through",window.releaseThrough()},{"windows",window.windows()},{"steps",checks}};
            } else throw std::runtime_error("unknown mode");
            output.push_back(result);
        }
        std::cout<<output.dump()<<'\n'; return 0;
    } catch (const std::exception& e) { std::cerr<<e.what()<<'\n'; return 1; }
}
