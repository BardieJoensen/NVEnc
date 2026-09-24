// Bounded selector-to-input schedule for finite diagnostics. A proposal does
// not grant source eligibility or bypass downstream native/model vetoes.
#pragma once
#include <stdexcept>
#include <utility>
#include "NVEncFilmGrainNativeGrid.h"
#include "NVEncFilmGrainRetentionSelect.h"

namespace fgsmodel {
class FilmGrainRetentionSchedule {
public:
    enum Reason : uint32_t { SelectedSource=1, UnsupportedComponents=2, EpochBoundary=4, ShortModelInterval=8 };
    struct Row {
        FilmGrainRetentionDecision selection;
        std::array<float,3> retain{{1,1,1}};
        uint32_t reasons=0;
        bool source() const {return retain==std::array<float,3>{{1,1,1}};}
    };
private:
    const std::vector<FilmGrainRetentionFrame> frames_;
    std::vector<Row> rows_;
    bool failed_=false,finished_=false;
    void ready() const {
        if(failed_ || finished_)throw std::runtime_error("retention schedule is closed");
    }
    void complete() const {
        if(failed_ || !finished_)throw std::runtime_error("retention schedule is not complete");
    }
public:
    explicit FilmGrainRetentionSchedule(std::vector<FilmGrainRetentionFrame> frames):frames_(std::move(frames)) {
        if(frames_.size()<8 || frames_.size()>16)throw std::runtime_error("retention schedule needs 8..16 complete inputs");
        for(size_t i=0;i<frames_.size();++i) {
            const auto& f=frames_[i];const auto grid=film_grain_native_grid(f.width,f.height);
            if(!f.valid() || !grid.valid || !grid.blocks[1])throw std::runtime_error("retention schedule native identity/layout invalid");
            if(i) {
                const auto& p=frames_[i-1];
                if(p.frameId==INT64_MAX || f.frameId!=p.frameId+1 || f.timestamp<=p.timestamp
                    || f.width!=p.width || f.height!=p.height || f.bitDepth!=p.bitDepth)
                    throw std::runtime_error("retention schedule source sequence differs");
            }
        }
        rows_.reserve(frames_.size());
    }
    // Only the bounded selector creates a decision here. Callbacks receive its
    // exact source identity and fraction; they cannot edit the resulting plan.
    template<class Evaluate,class Joint>
    void push(const FilmGrainRetentionFrame& frame,float lumaRetain,Evaluate evaluate,Joint joint) {
        try {
            ready();const auto ordinal=rows_.size();
            if(ordinal>=frames_.size() || !(frame==frames_[ordinal]))
                throw std::runtime_error("retention schedule received stale or reordered source evidence");
            Row row;row.selection=film_grain_select_retention(frame,lumaRetain,evaluate,joint);
            row.retain=row.selection.selected.retain;
            if(row.selection.sourceFrame)row.reasons|=SelectedSource;
            else if(row.selection.sourceMask)row.reasons|=UnsupportedComponents;
            if(ordinal && frames_[ordinal-1].epoch!=frame.epoch)row.reasons|=EpochBoundary;
            if(row.reasons)row.retain={{1,1,1}};
            rows_.push_back(std::move(row));
        }catch(...){failed_=true;throw;}
    }
    void finish() {
        try {
            ready();if(rows_.size()!=frames_.size())throw std::runtime_error("retention schedule inputs incomplete");
            // The whole finite plan exists before any pixels are encoded.
            // Never pool a short modeled interval with source-preserved rows.
            for(size_t begin=0;begin<rows_.size();) {
                if(rows_[begin].source()) {++begin;continue;}
                size_t end=begin+1;
                while(end<rows_.size() && !rows_[end].source())++end;
                if(end-begin<8)for(size_t i=begin;i<end;++i) {
                    rows_[i].retain={{1,1,1}};rows_[i].reasons|=ShortModelInterval;
                }
                begin=end;
            }
            finished_=true;
        }catch(...){failed_=true;throw;}
    }
    const std::vector<Row>& rows() const {complete();return rows_;}
    std::vector<std::array<float,3>> fractions() const {
        complete();std::vector<std::array<float,3>> result;result.reserve(rows_.size());
        for(const auto& row:rows_)result.push_back(row.retain);
        return result;
    }
};
} // namespace fgsmodel
