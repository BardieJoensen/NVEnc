// CPU replay of the exact live encoder adapter, including P010/NV12 conversion.
#include <iostream>
#include "NVEncFilmGrainNativeProbe.h"
using Json=nlohmann::json;
static void require(bool b,const char* why){if(!b)throw std::runtime_error(why);}
static uint64_t little(const uint8_t* p,unsigned n){uint64_t v=0;for(unsigned i=0;i<n;++i)v|=uint64_t(p[i])<<(i*8);return v;}
static void put(std::vector<uint8_t>& out,uint64_t v,unsigned n){for(unsigned i=0;i<n;++i)out.push_back(uint8_t(v>>(i*8)));}
int main() {
    try {
        Json input;std::cin>>input;const auto& native=input.at("config");const size_t count=native.at("packets").size();
        std::set<uint32_t> captured;for(size_t i=0;i<count;++i)captured.insert(uint32_t(i));
        const auto config=NVEncFilmGrainNativeConfig::parse(native,captured);
        const unsigned w=config.engine.at("width"),h=config.engine.at("height"),depth=config.engine.at("depth");
        const auto report=std::filesystem::u8path(input.at("report").get<std::string>());
        require(report.is_absolute() && !std::filesystem::exists(report),"new absolute report required");
        const auto retention=fgsdiagnostic::PreEncodeRetentionPlan::parse(input,count);
        NVEncFilmGrainNativeProbe<uint64_t> probe(config,report,w,h,depth,retention);
        const auto path=std::filesystem::u8path(input.at("ivf").get<std::string>());const auto size=std::filesystem::file_size(path);
        require(size>=32 && size<=256u*1024*1024,"IVF byte budget");std::vector<uint8_t> original(size);std::ifstream file(path,std::ios::binary);file.read(reinterpret_cast<char*>(original.data()),size);require(bool(file),"IVF read failed");
        require(std::equal(original.begin(),original.begin()+4,"DKIF") && little(original.data()+4,2)==0 && little(original.data()+6,2)==32
            && std::equal(original.begin()+8,original.begin()+12,"AV01"),"invalid IVF header");
        struct Packet {int64_t pts;size_t offset,bytes;};std::vector<Packet> packets;
        for(size_t at=32;at<original.size();) {
            require(original.size()-at>=12,"truncated IVF header");const auto bytes=little(original.data()+at,4),pts=little(original.data()+at+4,8);at+=12;
            require(bytes>0 && bytes<=original.size()-at && pts<=INT64_MAX,"invalid IVF payload");packets.push_back({int64_t(pts),at,size_t(bytes)});at+=bytes;require(packets.size()<=16,"IVF packet budget");
        }
        require(packets.size()==count && input.at("captures").is_array() && input.at("captures").size()<=count,"native capture count differs");
        std::vector<uint8_t> output(original.begin(),original.begin()+32);Json releases=Json::array();
        auto sourceMemory=std::make_shared<fgsdiagnostic::SourceMemory>(512ull*1024*1024);
        for(size_t i=0;i<input.at("captures").size();++i) {
            const auto path=std::filesystem::u8path(input.at("captures").at(i).get<std::string>());const size_t expected=size_t(w)*h*3/2*(depth==10?2:1);
            require(std::filesystem::file_size(path)==expected,"native capture bytes differ");std::vector<uint8_t> raw(expected);std::ifstream file(path,std::ios::binary);file.read(reinterpret_cast<char*>(raw.data()),raw.size());require(bool(file),"capture read failed");
            const auto before=raw;const auto pts=config.packets.packets[i].pts;
            std::shared_ptr<fgsdiagnostic::NativeSourceFrame> source;
            std::array<std::vector<uint16_t>,3> saved;
            if(config.memorySource() && input.contains("source_planes")) {
                std::optional<fgsdiagnostic::PreEncodeRetentionDecision> decision;
                if(input.contains("retention_decisions")) {
                    const auto& d=input.at("retention_decisions").at(i);decision.emplace();
                    decision->requested=d.at("requested").get<std::array<float,3>>();
                    decision->effective=d.at("effective").get<std::array<float,3>>();
                    decision->reasonMask=d.at("reason_mask").get<uint32_t>();
                    decision->preservedComponents=d.at("preserved_components").get<uint32_t>();
                }
                source=std::make_shared<fgsdiagnostic::NativeSourceFrame>(sourceMemory,i,int(i),pts,1,24,w,h,depth,decision);
                for(unsigned c=0;c<3;++c) {
                    const auto path=std::filesystem::u8path(input.at("source_planes").at(i).at(c).get<std::string>());
                    auto& values=source->planes[c];require(std::filesystem::file_size(path)==values.size()*2,"memory source plane bytes differ");
                    std::ifstream file(path,std::ios::binary);file.read(reinterpret_cast<char*>(values.data()),values.size()*2);require(bool(file),"memory source read failed");
                }
                if(retention.sourceChroma() && !retention.sourceAt(i) && input.contains("pre_encode_planes")) {
                    std::array<std::vector<uint16_t>,3> candidate;
                    std::array<FgsNativePlane,3> views{};
                    for(unsigned c=1;c<3;++c)if(retention.sourceChroma()&(1u<<c)) {
                        const auto path=std::filesystem::u8path(input.at("pre_encode_planes").at(i).at(c).get<std::string>());
                        auto& values=candidate[c];values.resize(size_t(w)*h/4);
                        require(std::filesystem::file_size(path)==values.size()*2,"pre-encode copied chroma plane bytes differ");
                        std::ifstream file(path,std::ios::binary);file.read(reinterpret_cast<char*>(values.data()),values.size()*2);
                        require(bool(file) && values==source->planes[c],"pre-encode copied chroma pixels differ");
                        views[c]={values.data(),values.size(),w/2};
                    }
                    if(retention.copiedChroma()) {
                        source->copiedChroma=fgsmodel::film_grain_measure_constant_chroma(views,w,h,depth,retention.copiedChroma());
                        source->requireCopiedChroma(retention.copiedChroma());
                    }
                    if(retention.preservedChroma()) {
                        require(fgsmodel::film_grain_preserved_chroma_range(views,w,h,depth,retention.preservedChroma()),
                            "pre-encode preserved chroma outside decoder range");
                        source->preservedChroma=retention.preservedChroma();
                        source->requirePreservedChroma(retention.preservedChroma());
                    }
                }
                saved=source->planes;
            }
            probe.reconstruction(i,pts,raw.data(),raw.size(),source.get());require(before==raw,"native adapter modified captured input");
            if(source)require(source->planes==saved,"native adapter modified original source");
            const auto& p=packets[i];const auto released=probe.receive(i,original.data()+p.offset,p.bytes,i,pts);
            for(const auto& item:released) {
                require(item.ordinal==item.token,"metadata token changed");put(output,item.bytes.size(),4);put(output,uint64_t(packets[item.ordinal].pts),8);output.insert(output.end(),item.bytes.begin(),item.bytes.end());releases.push_back({{"received",i},{"packet",item.ordinal}});
            }
        }
        probe.finish();
        const auto destination=std::filesystem::u8path(input.at("output").get<std::string>());require(destination.is_absolute() && !std::filesystem::exists(destination),"new absolute output required");
        std::ofstream out(destination,std::ios::binary);out.write(reinterpret_cast<const char*>(output.data()),output.size());out.flush();require(bool(out),"output write failed");
        std::cout<<Json({{"complete",true},{"releases",releases},{"bytes",output.size()},{"report",report.u8string()}}).dump()<<'\n';return 0;
    }catch(const std::exception& e){std::cout<<Json({{"complete",false},{"error",e.what()}}).dump()<<'\n';return 1;}
}
