// Bounded adapter for independent eigenvalue qualification of the PSD guard.
#include "NVEncFilmGrainJointModel.h"
#include "../../json/json.hpp"
#include <iostream>
#include <stdexcept>
using Json=nlohmann::json;
template<size_t N> static bool check(const Json& j) {
    if(!j.is_array() || j.size()!=N*N)throw std::runtime_error("matrix shape differs");
    std::array<double,N*N> a{};
    for(size_t i=0;i<a.size();++i) {
        if(!j[i].is_number())throw std::runtime_error("matrix value is not numeric");
        a[i]=j[i].get<double>();
    }
    return fgsmodel::joint_model_detail::semidefinite<N>(a);
}
int main(){try {
    Json input;std::cin>>input;
    if(!input.is_array() || input.empty() || input.size()>2048)throw std::runtime_error("matrix budget");
    Json result=Json::array();
    for(const auto& j:input) {
        const auto& n=j.at("order");
        if(!n.is_number_integer())throw std::runtime_error("matrix order type");
        switch(n.get<int>()) {
        case 2:result.push_back(check<2>(j.at("matrix")));break;
        case 25:result.push_back(check<25>(j.at("matrix")));break;
        case 26:result.push_back(check<26>(j.at("matrix")));break;
        case 52:result.push_back(check<52>(j.at("matrix")));break;
        default:throw std::runtime_error("matrix order outside scope");
        }
    }
    std::cout<<result.dump()<<'\n';
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
