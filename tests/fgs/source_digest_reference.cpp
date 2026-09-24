#include "NVEncFilmGrainSourceDigest.h"
#include "../../json/json.hpp"
#include <iostream>
int main(){try{nlohmann::json input;std::cin>>input;std::cout<<fgsdiagnostic::nativeSourceDigest(
    input.at("samples").get<std::vector<uint16_t>>(),input.at("depth").get<unsigned>())<<'\n';
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
