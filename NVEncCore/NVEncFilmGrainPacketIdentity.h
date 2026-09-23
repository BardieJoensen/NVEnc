// Bounded identity/buffering prerequisite for experimental reconstructed-base
// models. No source eligibility, picture-quality or encoder output call sites.
// MIT license, as NVEncFilmGrainModel.h.
#pragma once
#include <algorithm>
#include <array>
#include <cstdint>
#include <deque>
#include <limits>
#include <vector>

namespace fgsmodel {
struct FilmGrainPacketHeader {
    uint64_t coded = 0;
    unsigned hint = 0, hintBits = 0, refresh = 0;
    bool existing = false, show = false, showable = false;
};
struct FilmGrainPictureBinding {
    uint64_t coded = 0, inputOrdinal = 0;
    unsigned hint = 0;
    bool valid = false;
};
enum class FilmGrainPacketIdentityReason {
    None, Failed, Input, Clock, Display, Hint, CodedOrder, Reference,
    AmbiguousPicture, Future, Buffer, Incomplete
};
struct FilmGrainPacketIdentityResult {
    bool valid = false;
    FilmGrainPacketIdentityReason reason = FilmGrainPacketIdentityReason::None;
    std::vector<FilmGrainPictureBinding> pictures;
    std::vector<uint64_t> readyPackets;
    uint64_t latestInput = 0, pendingBytes = 0, peakBytes = 0;
    size_t pendingPackets = 0, peakPackets = 0;
};

// The caller must independently bind each packet's one displayed picture to
// its received NVENC encoded-input ordinal/PTS. These ordinals refer to the
// pictures submitted after filtering, not original-file frame IDs. This helper does not infer
// that association from a counter or a grain seed. It also requires a qualified
// forward-reference bound smaller than half the order-hint modulus. Otherwise
// wrapping hints alone cannot identify an arbitrarily distant source picture.
//
// A repeated display of an already displayed coded picture is unsupported by
// this one-source/one-model prototype: reject instead of relabelling its source.
// Every reconstruction must arrive in contiguous encoded-input order; missing or
// reordered availability cannot release pending packets using only a maximum.
class FilmGrainPacketIdentity {
    struct Pending { uint64_t packet, lastInput, bytes; };
    std::array<FilmGrainPictureBinding,8> m_references{};
    std::deque<Pending> m_pending;
    uint64_t m_nextInput = 0, m_nextCoded = 0, m_bytes = 0, m_peakBytes = 0;
    size_t m_peakPackets = 0;
    int64_t m_lastPts = 0;
    unsigned m_forward;
    size_t m_packetLimit;
    uint64_t m_byteLimit;
    bool m_failed = false, m_finished = false;

    FilmGrainPacketIdentityResult reject(FilmGrainPacketIdentityReason why) {
        m_failed = true; FilmGrainPacketIdentityResult r; r.reason = why; return r;
    }
public:
    explicit FilmGrainPacketIdentity(unsigned forward = 32, size_t packets = 64,
                                    uint64_t bytes = 256ull*1024*1024)
        : m_forward(forward), m_packetLimit(packets), m_byteLimit(bytes) {
        if (!forward || forward > 63 || !packets || packets > 64
            || !bytes || bytes > 256ull*1024*1024) m_failed = true;
    }

    FilmGrainPacketIdentityResult observe(uint64_t receivedInput, int64_t pts,
        uint64_t bytes, const std::vector<FilmGrainPacketHeader>& headers) {
        using Reason = FilmGrainPacketIdentityReason;
        if (m_failed || m_finished) return reject(Reason::Failed);
        if (receivedInput != m_nextInput || receivedInput > uint64_t(INT64_MAX)-64
            || !bytes || bytes > 32ull*1024*1024 || headers.empty() || headers.size()>4096)
            return reject(Reason::Input);
        if (pts == INT64_MIN || (m_nextInput && pts <= m_lastPts)) return reject(Reason::Clock);
        const FilmGrainPacketHeader* displayed = nullptr;
        for (const auto& h : headers) if (h.existing || h.show) {
            if (displayed) return reject(Reason::Display);
            displayed = &h;
        }
        if (!displayed) return reject(Reason::Display);
        if (!displayed->hintBits || displayed->hintBits>8) return reject(Reason::Hint);
        const unsigned modulus = 1u<<displayed->hintBits;
        if (m_forward >= modulus/2 || displayed->hint>=modulus) return reject(Reason::Hint);
        auto refs = m_references; uint64_t nextCoded = m_nextCoded;
        FilmGrainPacketIdentityResult result; result.latestInput = receivedInput;
        for (const auto& h : headers) {
            if (h.hintBits != displayed->hintBits || h.hint>=modulus || h.refresh>255)
                return reject(Reason::Hint);
            const unsigned wrapped = (h.hint + modulus - displayed->hint)%modulus;
            if (wrapped == modulus/2) return reject(Reason::AmbiguousPicture);
            const int delta = wrapped < modulus/2 ? int(wrapped) : int(wrapped)-int(modulus);
            if (delta < 0 || unsigned(delta)>m_forward) return reject(Reason::Future);
            FilmGrainPictureBinding binding{h.coded,receivedInput+unsigned(delta),h.hint,true};
            if (h.existing) {
                const auto ref = std::find_if(refs.begin(),refs.end(),[&](const auto& p){return p.valid && p.coded==h.coded;});
                if (ref==refs.end()) return reject(Reason::Reference);
                if (ref->inputOrdinal!=binding.inputOrdinal || ref->hint!=h.hint) return reject(Reason::AmbiguousPicture);
            } else {
                if (h.coded != nextCoded++) return reject(Reason::CodedOrder);
                if (!h.show && !h.showable) return reject(Reason::Display);
                if (!h.show && !h.refresh) return reject(Reason::Reference);
                // Distinct coded pictures must not claim the same live source.
                if (std::any_of(refs.begin(),refs.end(),[&](const auto& p){return p.valid && p.inputOrdinal==binding.inputOrdinal && p.coded!=binding.coded;}))
                    return reject(Reason::AmbiguousPicture);
            }
            for (unsigned ref=0;ref<8;++ref) if (h.refresh&(1u<<ref)) refs[ref]=binding;
            result.latestInput=std::max(result.latestInput,binding.inputOrdinal);
            result.pictures.push_back(binding);
        }
        if (m_pending.size()>=m_packetLimit || bytes>m_byteLimit-m_bytes) return reject(Reason::Buffer);
        m_references=refs;m_nextCoded=nextCoded;m_lastPts=pts;++m_nextInput;
        m_pending.push_back({receivedInput,result.latestInput,bytes});m_bytes+=bytes;
        m_peakBytes=std::max(m_peakBytes,m_bytes);m_peakPackets=std::max(m_peakPackets,m_pending.size());
        while (!m_pending.empty() && m_pending.front().lastInput<=receivedInput) {
            result.readyPackets.push_back(m_pending.front().packet);m_bytes-=m_pending.front().bytes;m_pending.pop_front();
        }
        result.valid=true;result.pendingBytes=m_bytes;result.peakBytes=m_peakBytes;
        result.pendingPackets=m_pending.size();result.peakPackets=m_peakPackets;
        return result;
    }
    bool finish() {
        if (m_failed) return false;
        if (m_finished) return true;
        if (!m_nextInput || !m_nextCoded || !m_pending.empty()) {m_failed=true;return false;}
        m_finished=true;return true;
    }
};
} // namespace fgsmodel
