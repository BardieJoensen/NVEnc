// Exact source association for an explicit finite pre-encode plan. Hashes
// establish content identity, never source eligibility or picture quality.
#pragma once
#include <climits>
#include <string>
#include "NVEncFilmGrainSourceFrame.h"

namespace fgsdiagnostic {
class PreEncodeSourceBinding {
    struct Row {int sourceId;int64_t pts;std::array<std::string,3> sha256;};
    std::vector<Row> rows_;
    unsigned width_=0,height_=0,depth_=0;
    int tbNum_=0,tbDen_=0;
    static int64_t integer(const nlohmann::json& j,int64_t low,int64_t high) {
        if(!j.is_number_integer() || j<low || j>high)
            throw std::runtime_error("source binding integer is invalid");
        return j.get<int64_t>();
    }
public:
    static PreEncodeSourceBinding parse(const nlohmann::json& manifest,size_t count) {
        PreEncodeSourceBinding b;
        if(!manifest.contains("pre_encode_source_binding"))return b;
        const auto& j=manifest.at("pre_encode_source_binding");
        if(!j.is_object() || integer(j.at("schema"),1,1)!=1 || count<8 || count>16)
            throw std::runtime_error("source binding requires schema 1 and 8..16 inputs");
        b.width_=unsigned(integer(j.at("width"),64,4096));
        b.height_=unsigned(integer(j.at("height"),64,2160));
        b.depth_=unsigned(integer(j.at("depth"),8,10));
        NativeSourceFrame::nativeBytes(b.width_,b.height_,b.depth_);
        const auto& tb=j.at("timebase");
        if(!tb.is_array() || tb.size()!=2)throw std::runtime_error("source binding timebase is invalid");
        b.tbNum_=int(integer(tb[0],1,INT_MAX));b.tbDen_=int(integer(tb[1],1,INT_MAX));
        const auto& rows=j.at("frames");
        if(!rows.is_array() || rows.size()!=count)throw std::runtime_error("source binding input count differs");
        for(size_t i=0;i<count;++i) {
            const auto& row=rows[i];
            if(!row.is_object() || integer(row.at("ordinal"),0,15)!=int64_t(i))
                throw std::runtime_error("source binding ordinal differs");
            Row r{int(integer(row.at("source_id"),0,INT_MAX)),integer(row.at("pts"),INT64_MIN+1,INT64_MAX),{}};
            if(i && (r.sourceId!=int64_t(b.rows_.back().sourceId)+1 || r.pts<=b.rows_.back().pts))
                throw std::runtime_error("source binding input sequence differs");
            const auto& hashes=row.at("plane_sha256");
            if(!hashes.is_array() || hashes.size()!=3)throw std::runtime_error("source binding requires three plane hashes");
            for(unsigned c=0;c<3;++c) {
                r.sha256[c]=hashes[c].get<std::string>();
                if(r.sha256[c].size()!=64 || r.sha256[c].find_first_not_of("0123456789abcdef")!=std::string::npos)
                    throw std::runtime_error("source binding plane hash is invalid");
            }
            b.rows_.push_back(std::move(r));
        }
        return b;
    }
    bool enabled() const {return !rows_.empty();}
    template<class Digest>
    void require(const NativeSourceFrame& f,Digest digest) const {
        if(!enabled())return;
        if(f.ordinal>=rows_.size())throw std::runtime_error("source binding ordinal outside plan");
        const auto& row=rows_[f.ordinal];
        f.requireIdentity(f.ordinal,row.sourceId,row.pts,tbNum_,tbDen_,width_,height_,depth_);
        for(unsigned c=0;c<3;++c)if(digest(f.planes[c],depth_)!=row.sha256[c])
            throw std::runtime_error("pre-encode source content differs from retention evidence");
    }
};
}
