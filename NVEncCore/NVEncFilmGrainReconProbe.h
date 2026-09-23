// Explicit NVENC reconstruction capture for compressed-base grain research.
// Disabled by default. Capture-only unless an explicit model output mode is supplied.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include <fstream>
#include <map>
#include <memory>
#include <optional>
#include <vector>
#include "NVEncDevice.h"
#include "CuvidDecode.h"
#include "NVEncFilmGrainReconConfig.h"
#include "NVEncFilmGrainModelProbe.h"
#include "NVEncFilmGrainNativeProbe.h"
#include "NVEncFilmGrainSourceFrame.h"
#include "NVEncUtil.h"

class NVEncFilmGrainReconProbe {
    using Json = nlohmann::json;
    using Path = std::filesystem::path;
    struct Surface {
        void* device = nullptr;
        void* registered = nullptr;
        void* mapped = nullptr;
        size_t pitch = 0;
        int sourceId = -1;
        int64_t pts = 0, duration = 0;
        int timebaseNum = 0, timebaseDen = 0;
        std::shared_ptr<const fgsdiagnostic::NativeSourceFrame> source;
    };
    NVGPUInfo* m_dev;
    NVEncFilmGrainReconConfig m_config;
    unsigned m_width, m_height, m_depth;
    uint64_t m_frameBytes, m_allocated = 0;
    std::map<uint32_t,Surface> m_pending;
    std::set<uint32_t> m_captured;
    bool m_failed = false, m_finished = false;
    uint64_t m_submitted = 0, m_received = 0, m_peakAllocated = 0;
    uint64_t m_sources = 0, m_peakSourceBytes = 0;
    std::unique_ptr<NVEncFilmGrainModelProbe<std::shared_ptr<RGYBitstream>>> m_modelOutput;
    std::unique_ptr<NVEncFilmGrainNativeProbe<std::shared_ptr<RGYBitstream>>> m_nativeOutput;

    static void cudaCheck(cudaError_t e) {
        if (e != cudaSuccess) throw std::runtime_error(cudaGetErrorString(e));
    }
    static void nvCheck(NVENCSTATUS e) {
        if (e != NV_ENC_SUCCESS) throw std::runtime_error("NVENC reconstruction API error " + std::to_string(int(e)));
    }
    static void jsonFile(const Path& path, const Json& value) {
        auto temp = path; temp += ".tmp";
        { std::ofstream out(temp); out << value.dump(2) << '\n'; out.flush();
          if (!out) throw std::runtime_error("reconstruction JSON write failed"); }
        std::filesystem::rename(temp,path);
    }
    void status(const std::string& error = {}) {
        jsonFile(m_config.directory/"status.json", {{"complete",m_finished && !m_failed && m_captured==m_config.frames},
            {"requested_frames",m_config.frames},{"captured_frames",m_captured},
            {"failed",m_failed},{"error",error},{"native_bytes",m_frameBytes*m_captured.size()},
            {"submitted",m_submitted},{"received",m_received},{"peak_device_bytes",m_peakAllocated},
            {"source_frames",m_sources},{"source_bytes",uint64_t(m_width)*m_height*3*m_sources},{"peak_source_bytes",m_peakSourceBytes}});
    }
    void release(Surface& s) noexcept {
        // The owner must keep the encoder/context alive until this probe closes.
        if (s.mapped) m_dev->encoder()->NvEncUnmapInputResource(s.mapped);
        if (s.registered) m_dev->encoder()->NvEncUnregisterResource(s.registered);
        if (s.device) { cudaFree(s.device); m_allocated -= s.pitch*(m_height*3/2); }
        s = {};
    }
public:
    NVEncFilmGrainReconProbe(NVGPUInfo* dev,const Path& manifest,unsigned width,unsigned height,unsigned depth)
        : m_dev(dev),m_width(width),m_height(height),m_depth(depth),m_frameBytes(0) {
        if (!dev || !dev->encoder() || std::filesystem::file_size(manifest)>65536)
            throw std::runtime_error("invalid reconstruction probe manifest or encoder");
        std::ifstream file(manifest); Json j; file>>j;
        m_config=NVEncFilmGrainReconConfig::parse(j);
        m_frameBytes=m_config.requireLayout(width,height,depth);
        std::optional<NVEncFilmGrainModelConfig> modelConfig;
        std::optional<NVEncFilmGrainNativeConfig> nativeConfig;
        if(j.contains("model_output") && j.contains("native_model_output"))
            throw std::runtime_error("choose one explicit model output diagnostic");
        if(j.contains("model_output"))modelConfig=NVEncFilmGrainModelConfig::parse(j.at("model_output"),m_config.frames);
        if(j.contains("native_model_output")) {
            nativeConfig=NVEncFilmGrainNativeConfig::parse(j.at("native_model_output"),m_config.frames);
            nativeConfig->requireLayout(width,height,depth);
            if(nativeConfig->memorySource()!=m_config.captureSource)
                throw std::runtime_error("native memory mode requires source capture; file mode uses its supplied sources");
        }
        if (!std::filesystem::create_directory(m_config.directory))
            throw std::runtime_error("reconstruction probe requires a new output directory");
        jsonFile(m_config.directory/"manifest.json",j); status();
        if(modelConfig)m_modelOutput=std::make_unique<NVEncFilmGrainModelProbe<std::shared_ptr<RGYBitstream>>>(std::move(*modelConfig),m_config.directory/"model-output.json");
        if(nativeConfig)m_nativeOutput=std::make_unique<NVEncFilmGrainNativeProbe<std::shared_ptr<RGYBitstream>>>(std::move(*nativeConfig),m_config.directory/"native-model-output.json",width,height,depth);
    }
    ~NVEncFilmGrainReconProbe() {
        NVEncCtxAutoLock(context(m_dev->vidCtxLock()));
        for (auto& p : m_pending) release(p.second);
    }
    NVEncFilmGrainReconProbe(const NVEncFilmGrainReconProbe&)=delete;
    NVEncFilmGrainReconProbe& operator=(const NVEncFilmGrainReconProbe&)=delete;

    // Encoded input ordinal identifies the requested surface. Its output must
    // carry that same ordinal AND timestamp after NVENC's picture reordering.
    void submit(NV_ENC_PIC_PARAMS& p,int sourceId,int tbNum,int tbDen,
        std::shared_ptr<const fgsdiagnostic::NativeSourceFrame> source = {}) {
        if (m_failed || m_finished) throw std::runtime_error("reconstruction probe is not accepting inputs");
        // NVENC reorders reconstructed output buffers. Sparse output pointers
        // can alias another picture in an AV1 hidden-frame group; supply a
        // distinct live surface for EVERY input, but download requested ones only.
        if (p.frameIdx!=m_submitted || m_pending.count(p.frameIdx) || sourceId<0 || tbNum<=0 || tbDen<=0)
            throw std::runtime_error("duplicate or invalid reconstruction input identity");
        auto& s=m_pending[p.frameIdx];s.sourceId=sourceId;s.pts=int64_t(p.inputTimeStamp);
        s.duration=int64_t(p.inputDuration);s.timebaseNum=tbNum;s.timebaseDen=tbDen;
        if(m_config.captureSource && m_config.frames.count(p.frameIdx)) {
            if(!source)throw std::runtime_error("requested original source is missing");
            source->requireIdentity(p.frameIdx,sourceId,s.pts,tbNum,tbDen,m_width,m_height,m_depth);
            if(bool(source->retention)!=m_config.preEncodeRetention
                || (source->retention && source->retention->requested!=m_config.retention))
                throw std::runtime_error("pre-encode retention decision differs between filter and reconstruction");
            m_peakSourceBytes=std::max(m_peakSourceBytes,source->peakBytes());
            if(m_peakSourceBytes>m_config.maxSourceBytes)throw std::runtime_error("source budget differs between filter and reconstruction");
            s.source=std::move(source);
        } else if(source)throw std::runtime_error("unexpected original source attachment");
        const auto format=m_depth==10?NV_ENC_BUFFER_FORMAT_YUV420_10BIT:NV_ENC_BUFFER_FORMAT_NV12;
        if (p.inputWidth!=m_width || p.inputHeight!=m_height || p.bufferFmt!=format)
            throw std::runtime_error("reconstruction input layout changed");
        NVEncCtxAutoLock(context(m_dev->vidCtxLock()));
        const size_t rowBytes=m_width*(m_depth==10?2:1);
        cudaCheck(cudaMallocPitch(&s.device,&s.pitch,rowBytes,m_height*3/2));
        m_allocated+=s.pitch*(m_height*3/2);
        m_peakAllocated=std::max(m_peakAllocated,m_allocated);
        if (m_allocated>m_config.maxDeviceBytes || s.pitch>UINT32_MAX)
            throw std::runtime_error("reconstruction device allocation budget exceeded");
        nvCheck(m_dev->encoder()->NvEncRegisterResource(NV_ENC_INPUT_RESOURCE_TYPE_CUDADEVICEPTR,
            s.device,m_width,m_height,static_cast<uint32_t>(s.pitch),format,&s.registered,NV_ENC_OUTPUT_RECON));
        nvCheck(m_dev->encoder()->NvEncMapInputResource(s.registered,&s.mapped));
        p.outputReconBuffer=s.mapped;p.encodePicFlags|=NV_ENC_PIC_FLAG_OUTPUT_RECON_FRAME;
        ++m_submitted;
    }
    void receive(uint32_t frameId,int64_t pts,uint32_t displayId) {
        if (m_failed) throw std::runtime_error("reconstruction probe already failed");
        const auto found=m_pending.find(frameId);
        if (found==m_pending.end() || found->second.pts!=pts)
            throw std::runtime_error("reconstruction output identity differs from input");
        if(modelOutputEnabled() && frameId!=m_received)throw std::runtime_error("model trial reconstruction arrival order changed");
        auto& s=found->second;
        NVEncCtxAutoLock(context(m_dev->vidCtxLock()));
        // NVIDIA requires unmapping before CUDA reads reconstructed surfaces.
        nvCheck(m_dev->encoder()->NvEncUnmapInputResource(s.mapped));s.mapped=nullptr;
        ++m_received;
        if (!m_config.frames.count(frameId)) {
            release(s);m_pending.erase(found);return;
        }
        std::vector<uint8_t> host(m_frameBytes);const size_t rowBytes=m_width*(m_depth==10?2:1);
        cudaCheck(cudaMemcpy2D(host.data(),rowBytes,s.device,s.pitch,rowBytes,m_height*3/2,cudaMemcpyDeviceToHost));
        if(m_nativeOutput)m_nativeOutput->reconstruction(frameId,pts,host.data(),host.size(),s.source.get());
        const auto stem="frame-"+std::to_string(frameId);const auto raw=m_config.directory/(stem+".raw");
        if(s.source) {
            Json planes=Json::array();
            for(unsigned c=0;c<3;++c) {
                const auto path=m_config.directory/(stem+"-source-"+std::to_string(c)+".raw");
                const auto& values=s.source->planes[c];std::ofstream out(path,std::ios::binary);
                out.write(reinterpret_cast<const char*>(values.data()),values.size()*2);out.flush();
                if(!out)throw std::runtime_error("original source write failed");
                planes.push_back({{"path",path.u8string()},{"samples",values.size()}});
            }
            Json original={{"complete",true},{"frame_id",frameId},{"source_frame_id",s.sourceId},
                {"pts",pts},{"timebase",{s.timebaseNum,s.timebaseDen}},{"width",m_width},{"height",m_height},{"depth",m_depth},
                {"format","planar_native_uint16"},{"planes",planes}};
            if(s.source->retention)original["pre_encode_retention"]=fgsdiagnostic::preEncodeRetentionEvidence(*s.source->retention);
            jsonFile(m_config.directory/(stem+"-source.json"),original);
            ++m_sources;
        }
        { std::ofstream out(raw,std::ios::binary);out.write(reinterpret_cast<const char*>(host.data()),host.size());out.flush();
          if (!out) throw std::runtime_error("reconstruction native write failed"); }
        jsonFile(m_config.directory/(stem+".json"),{{"complete",true},{"frame_id",frameId},{"source_frame_id",s.sourceId},
            {"receive_ordinal",m_received-1},
            {"pts",pts},{"api_display_id",displayId},{"duration",s.duration},{"timebase",{s.timebaseNum,s.timebaseDen}},
            {"width",m_width},{"height",m_height},{"depth",m_depth},{"shift",m_depth==10?6:0},
            {"format",m_depth==10?"p010":"nv12"},{"pitch",rowBytes},{"device_pitch",s.pitch},{"bytes",host.size()},{"raw",raw.u8string()}});
        release(s);m_pending.erase(found);m_captured.insert(frameId);status();
    }
    void finish() {
        if (m_failed || !m_pending.empty() || m_captured!=m_config.frames || m_received!=m_submitted
            || (m_config.captureSource && m_sources!=m_config.frames.size()))
            throw std::runtime_error("reconstruction capture did not complete every requested frame");
        if(m_modelOutput)m_modelOutput->finish();
        if(m_nativeOutput)m_nativeOutput->finish();
        m_finished=true;status();
    }
    bool modelOutputEnabled() const {return bool(m_modelOutput) || bool(m_nativeOutput);}
    bool sourceCaptureEnabled() const {return m_config.captureSource;}
    std::vector<std::shared_ptr<RGYBitstream>> filterOutput(std::shared_ptr<RGYBitstream> packet) {
        if(!modelOutputEnabled() || !packet || packet->frameIdx()<0 || uint64_t(packet->frameIdx())+1!=m_received)
            throw std::runtime_error("model trial packet lacks matching reconstruction");
        // RGYListRef's shared pointers refer back to the pipeline's pool. A
        // pending failure may outlive that pool at teardown. Transfer the POD's
        // complete ownership into a separately allocated token before buffering;
        // leave the pool entry empty, including its side-data ownership.
        auto owned=std::shared_ptr<RGYBitstream>(new RGYBitstream(RGYBitstreamInit()),
            [](RGYBitstream* p){p->clear();delete p;});
        *owned=*packet;*packet=RGYBitstreamInit();
        auto output=m_nativeOutput?m_nativeOutput->receive(owned,owned->data(),owned->size(),uint64_t(owned->frameIdx()),owned->pts())
            :m_modelOutput->receive(owned,owned->data(),owned->size(),uint64_t(owned->frameIdx()),owned->pts());
        std::vector<std::shared_ptr<RGYBitstream>> released;
        for(auto& item:output) {
            // Payload-only copy preserves PTS/DTS, duration, frame index, flags,
            // picture type and every other bitstream field in the original token.
            if(item.token->copy(item.bytes.data(),item.bytes.size())!=RGY_ERR_NONE)
                throw std::runtime_error("model trial payload allocation failed");
            released.push_back(std::move(item.token));
        }
        return released;
    }
    void fail(const std::string& error) noexcept {
        if(m_modelOutput)m_modelOutput->fail(error);
        if(m_nativeOutput)m_nativeOutput->fail(error);
        m_failed=true;try { status(error); } catch (...) {}
    }
};
