// Native sequence fitting/selection and actual packet output in one process.
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include "engine.h"
#include "NVEncFilmGrainModelBuffer.h"
using namespace fgsdiagnostic;
using namespace fgsmodel;
namespace {
void require(bool b,const char* why){if(!b)throw std::runtime_error(why);}
uint64_t little(const uint8_t* p,unsigned count){uint64_t v=0;for(unsigned i=0;i<count;++i)v|=uint64_t(p[i])<<(8*i);return v;}
void put(std::vector<uint8_t>& out,uint64_t value,unsigned count){for(unsigned i=0;i<count;++i)out.push_back(uint8_t(value>>(8*i)));}
struct Packet {int64_t pts;std::vector<uint8_t> bytes;};
struct Stream {std::array<uint8_t,32> header;std::vector<Packet> packets;};
Stream readStream(const std::filesystem::path& path) {
    std::ifstream file(path,std::ios::binary);Stream stream;file.read(reinterpret_cast<char*>(stream.header.data()),32);
    require(bool(file) && std::equal(stream.header.begin(),stream.header.begin()+4,"DKIF")
        && little(stream.header.data()+4,2)==0 && little(stream.header.data()+6,2)==32
        && std::equal(stream.header.begin()+8,stream.header.begin()+12,"AV01"),"invalid IVF header");
    while(file.peek()!=EOF) {
        std::array<uint8_t,12> record{};file.read(reinterpret_cast<char*>(record.data()),12);require(bool(file),"truncated IVF record");
        const auto bytes=little(record.data(),4),pts=little(record.data()+4,8);require(bytes>0 && bytes<=32u*1024*1024 && pts<=INT64_MAX,"invalid IVF packet");
        Packet packet{int64_t(pts),std::vector<uint8_t>(size_t(bytes))};file.read(reinterpret_cast<char*>(packet.bytes.data()),bytes);require(bool(file),"truncated IVF payload");stream.packets.push_back(std::move(packet));require(stream.packets.size()<=16,"packet budget");
    }
    return stream;
}
}
int main() {
    std::unique_ptr<NativeSequenceEngine> engine;
    std::unique_ptr<FilmGrainModelBuffer<uint64_t>> writer;
    Json result={{"complete",false}};
    try {
        Json input;std::cin>>input;const auto& frames=input.at("frames");
        NativeSequenceEngine::Config config;
        config.width=input.at("width");config.height=input.at("height");config.depth=input.at("depth");config.matrix=input.at("matrix");config.frames=input.at("frame_count");
        config.shift=input.value("shift",6u);config.grainShift=input.value("grain_shift",0u);config.maxNativeBytes=input.value("max_native_bytes",512ull*1024*1024);
        if(input.contains("seed_ordinal_offset")) {
            const auto& offset=input.at("seed_ordinal_offset");
            require(offset.is_number_integer() && offset>=0 && offset<=15,"invalid seed ordinal offset");
            config.seedOrdinalOffset=offset.get<unsigned>();
        }
        if(input.contains("copied_chroma_mask")) {
            const auto& m=input.at("copied_chroma_mask");
            require(m.is_number_integer() && m>=0 && m<=6,"invalid copied chroma mask");config.copiedChroma=m.get<unsigned>();
        }
        if(input.contains("preserved_chroma_mask")) {
            const auto& m=input.at("preserved_chroma_mask");
            require(m.is_number_integer() && m>=0 && m<=6,"invalid preserved chroma mask");config.preservedChroma=m.get<unsigned>();
        }
        const auto spatial=input.value("spatial_policy",std::string("frame_window"));
        require(spatial=="frame_window" || spatial=="full_picture" || spatial=="full_picture_means" || spatial=="frame_window_means","unsupported spatial policy");
        config.spatialPolicy=spatial=="frame_window_means"?FilmGrainMomentSpatialPolicy::FrameWindowMeans
            :spatial=="full_picture_means"?FilmGrainMomentSpatialPolicy::FullPictureMeans
            :spatial=="full_picture"?FilmGrainMomentSpatialPolicy::FullPicture:FilmGrainMomentSpatialPolicy::FrameWindow;
        const auto seeds=input.at("training_seeds").get<std::vector<unsigned>>();for(auto seed:seeds){require(seed<=65535,"seed range");config.trainingSeeds.push_back(uint16_t(seed));}
        require(frames.is_array() && frames.size()<=16,"input frame budget");
        const auto rawDirectory=std::filesystem::u8path(input.at("raw_directory").get<std::string>());
        require(rawDirectory.is_absolute() && std::filesystem::create_directory(rawDirectory),"new absolute raw directory required");
        engine=std::make_unique<NativeSequenceEngine>(config,[&](uint64_t ordinal,unsigned seed,const NativeSequenceEngine::Pictures& planes) {
            const auto path=rawDirectory/(std::to_string(ordinal)+"-"+std::to_string(seed)+".raw");
            require(!std::filesystem::exists(path),"candidate raw exists");std::ofstream file(path,std::ios::binary);
            for(const auto& p:planes)file.write(reinterpret_cast<const char*>(p.data),p.samples*2);
            file.flush();require(bool(file),"candidate witness write failed");
        });
        Stream stream;std::vector<uint8_t> output;
        if(input.contains("ivf")) {
            stream=readStream(input.at("ivf").get<std::string>());
            require(stream.packets.size()==config.frames && little(stream.header.data()+12,2)==config.width
                && little(stream.header.data()+14,2)==config.height,"IVF frame/layout count mismatch");
            writer=std::make_unique<FilmGrainModelBuffer<uint64_t>>(input.at("library").get<std::string>(),config.frames,32,
                input.value("max_pending_packets",64u),input.value("max_pending_bytes",256ull*1024*1024));
            output.assign(stream.header.begin(),stream.header.end());
        }
        const auto start=std::chrono::steady_clock::now();Json releases=Json::array();
        for(size_t i=0;i<frames.size();++i) {
            const auto& frame=frames[i];std::array<std::array<std::vector<uint16_t>,3>,2> data;
            std::array<NativeSequenceEngine::Pictures,2> planes{};
            for(unsigned kind=0;kind<2;++kind)for(unsigned c=0;c<3;++c) {
                const unsigned w=c?config.width/2:config.width,h=c?config.height/2:config.height;const size_t count=size_t(w)*h;
                const auto path=std::filesystem::u8path(frame.at(kind?"base":"source").at(c).get<std::string>());require(std::filesystem::file_size(path)==count*2,"native plane byte count differs");
                auto& a=data[kind][c];a.resize(count);std::ifstream file(path,std::ios::binary);file.read(reinterpret_cast<char*>(a.data()),count*2);require(bool(file),"native plane read failed");planes[kind][c]={a.data(),count,w};
            }
            const auto before=data;
            const auto ordinal=frame.at("ordinal").get<uint64_t>();const auto pts=frame.at("pts").get<int64_t>();
            engine->push(ordinal,pts,frame.at("segment"),planes[0],planes[1]);
            require(before==data,"engine modified caller native inputs");
            if(writer) {
                const auto& packet=stream.packets.at(i);require(packet.pts==pts,"native picture/IVF PTS mismatch");
                const auto provider=[&](const FilmGrainPictureBinding& binding) {
                    if(!engine->ready(binding.inputOrdinal))return FilmGrainModelDecision{};
                    return FilmGrainModelDecision{FilmGrainModelReadiness::Replace,engine->selectedModel(binding.inputOrdinal)};
                };
                const auto released=writer->push(i,packet.bytes.data(),packet.bytes.size(),i,pts,provider);
                for(const auto& p:released) {
                    require(p.ordinal==p.token,"packet identity changed");
                    put(output,p.bytes.size(),4);put(output,uint64_t(stream.packets.at(p.ordinal).pts),8);output.insert(output.end(),p.bytes.begin(),p.bytes.end());
                    releases.push_back({{"received",i},{"packet",p.ordinal}});
                }
            }
        }
        engine->finish();
        if(writer) {
            writer->finish();const auto path=std::filesystem::u8path(input.at("output").get<std::string>());
            require(path.is_absolute() && !std::filesystem::exists(path),"new absolute output required");
            std::ofstream file(path,std::ios::binary);file.write(reinterpret_cast<const char*>(output.data()),output.size());file.flush();require(bool(file),"IVF output write failed");
            result["writer"]=writer->report();result["releases"]=releases;
        }
        result["engine"]=engine->report();result["complete"]=true;result["seconds"]=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
        std::cout<<result.dump()<<'\n';return 0;
    }catch(const std::exception& e) {
        if(engine)result["engine"]=engine->report();
        if(writer)result["writer"]=writer->report();
        result["error"]=e.what();
        std::cout<<result.dump()<<'\n';std::cerr<<e.what()<<'\n';return 1;
    }
}
