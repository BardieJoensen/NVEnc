// Manual identity/buffering replay; JSON evidence is not source qualification.
#include <iostream>
#include "NVEncFilmGrainPacketIdentity.h"
#include "json.hpp"
using Json=nlohmann::json;
int main() {
    try {
        Json j;std::cin>>j;
        fgsmodel::FilmGrainPacketIdentity state(j.value("max_forward",32u),j.value("max_packets",64u),j.value("max_bytes",256ull*1024*1024));
        Json result={{"complete",false},{"packets",Json::array()}};
        for(const auto& p:j.at("packets")) {
            std::vector<fgsmodel::FilmGrainPacketHeader> headers;
            for(const auto& h:p.at("headers")) headers.push_back({h.at("coded_index"),h.at("order_hint"),h.at("order_hint_bits"),h.at("refresh"),h.at("show_existing"),h.at("show"),h.at("showable")});
            const auto r=state.observe(p.at("received_input"),p.at("pts"),p.at("bytes"),headers);
            Json pictures=Json::array();for(const auto& b:r.pictures)pictures.push_back({{"coded_index",b.coded},{"input_ordinal",b.inputOrdinal},{"order_hint",b.hint}});
            result["packets"].push_back({{"valid",r.valid},{"reason",int(r.reason)},{"pictures",pictures},{"latest_input",r.latestInput},{"ready_packets",r.readyPackets},{"pending_bytes",r.pendingBytes},{"pending_packets",r.pendingPackets},{"peak_bytes",r.peakBytes},{"peak_packets",r.peakPackets}});
            if(!r.valid){std::cout<<result.dump()<<'\n';return 1;}
        }
        result["complete"]=state.finish();std::cout<<result.dump()<<'\n';return result["complete"].get<bool>()?0:1;
    } catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
