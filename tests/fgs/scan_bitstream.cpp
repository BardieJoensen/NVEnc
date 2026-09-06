// Inspect signalled grain models without decoding video pixels.
// Links against FFmpeg (trace_headers BSF) and the CPU-only stability guard.
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <chrono>
#include <array>
#include <set>
#include <string>
extern "C" {
#include <libavformat/avformat.h>
#include <libavcodec/bsf.h>
#include <libavutil/log.h>
}
#include "NVEncFilmGrainStability.h"
#include "av1_scan_packet.h"

namespace {
struct Model {
    std::array<std::array<uint8_t, 24>, 3> coeff;
    std::array<int, 3> points{};
    std::array<int, 3> maxScaling{};
    std::array<int, 3> lumaCoupling{};
    unsigned lag = 0, shift = 6;
    bool fromLuma = false;
    Model() { for (auto& c : coeff) c.fill(128); }
};
Model current, bad;
std::set<std::string> checked;
int grainPresent = -1, unsafePlane = -1, errors = 0;
int64_t packetPts = AV_NOPTS_VALUE, badPts = AV_NOPTS_VALUE, packets = 0, models = 0;
AVRational timeBase{1, 1000};
char firstError[300]{};
bool stabilityOnly = false;

void checkModel() {
    if (unsafePlane >= 0) return;
    const bool chromaActive[2] = {
        current.fromLuma ? current.maxScaling[0] > 0 : current.maxScaling[1] > 0,
        current.fromLuma ? current.maxScaling[0] > 0 : current.maxScaling[2] > 0};
    for (int plane = 0; plane < 3; ++plane) {
        if (!current.points[plane] && !(plane && current.fromLuma)) continue;
        if (plane == 0) {
            if (!current.maxScaling[0] && !(chromaActive[0] && current.lumaCoupling[1])
                && !(chromaActive[1] && current.lumaCoupling[2])) continue;
        } else if (!chromaActive[plane - 1]) continue;
        const auto& c = current.coeff[plane];
        std::string key(reinterpret_cast<const char *>(c.data()), c.size());
        key.push_back(static_cast<char>(current.lag));
        key.push_back(static_cast<char>(current.shift));
        if (!checked.insert(key).second) continue;
        ++models;
        const bool accepted = stabilityOnly
            ? fgsmodel::film_grain_ar_stable(c.data(), current.lag, current.shift)
            : fgsmodel::film_grain_ar_synthesis_safe(c.data(), current.lag, current.shift);
        if (!accepted) {
            unsafePlane = plane; badPts = packetPts; bad = current; return;
        }
    }
}

void logCallback(void *, int level, const char *fmt, va_list ap) {
    char line[2048];
    vsnprintf(line, sizeof(line), fmt, ap);
    if (level <= AV_LOG_ERROR) {
        ++errors;
        if (!firstError[0]) snprintf(firstError, sizeof(firstError), "%.280s", line);
    }
    const char *eq = strrchr(line, '=');
    if (!eq) return;
    unsigned bit;
    char field[100];
    if (sscanf(line, "%u %99s", &bit, field) != 2) return;
    const int value = static_cast<int>(strtol(eq + 1, nullptr, 10));
    if (!strcmp(field, "film_grain_params_present")) grainPresent = value;
    else if (!strcmp(field, "apply_grain")) current = Model();
    else if (!strcmp(field, "num_y_points")) current.points[0] = value;
    else if (!strcmp(field, "num_cb_points")) current.points[1] = value;
    else if (!strcmp(field, "num_cr_points")) current.points[2] = value;
    else if (!strcmp(field, "chroma_scaling_from_luma")) current.fromLuma = value;
    else if (!strcmp(field, "ar_coeff_lag")) current.lag = value;
    else if (!strcmp(field, "ar_coeff_shift_minus_6")) current.shift = value + 6;
    else if (!strcmp(field, "clip_to_restricted_range")) checkModel();
    else {
        int index = -1;
        const int spatial = 2 * current.lag * (current.lag + 1);
        if (sscanf(field, "point_y_scaling[%d]", &index) == 1) current.maxScaling[0] = std::max(current.maxScaling[0], value);
        else if (sscanf(field, "point_cb_scaling[%d]", &index) == 1) current.maxScaling[1] = std::max(current.maxScaling[1], value);
        else if (sscanf(field, "point_cr_scaling[%d]", &index) == 1) current.maxScaling[2] = std::max(current.maxScaling[2], value);
        else if (sscanf(field, "ar_coeffs_y_plus_128[%d]", &index) == 1 && index >= 0 && index < spatial) current.coeff[0][index] = value;
        else if (sscanf(field, "ar_coeffs_cb_plus_128[%d]", &index) == 1 && index >= 0 && index <= spatial) {
            if (index == spatial) current.lumaCoupling[1] = value - 128;
            else current.coeff[1][index] = value;
        } else if (sscanf(field, "ar_coeffs_cr_plus_128[%d]", &index) == 1 && index >= 0 && index <= spatial) {
            if (index == spatial) current.lumaCoupling[2] = value - 128;
            else current.coeff[2][index] = value;
        }
    }
}
}

int main(int argc, char **argv) {
    int selectedVideo = -1;
    while (argc > 2) {
        if (!strcmp(argv[1], "--stability-only")) {
            stabilityOnly = true; --argc; ++argv;
        } else if (argc > 3 && !strcmp(argv[1], "--stream-index")) {
            char *end = nullptr;
            const long index = strtol(argv[2], &end, 10);
            if (!*argv[2] || *end || index < 0 || index > INT32_MAX) return 2;
            selectedVideo = static_cast<int>(index); argc -= 2; argv += 2;
        } else break;
    }
    if (argc != 2) {
        fprintf(stderr, "usage: scan_bitstream [--stability-only] [--stream-index N] FILE\n");
        return 2;
    }
    auto start = std::chrono::steady_clock::now();
    av_log_set_callback(logCallback);
    av_log_set_level(AV_LOG_TRACE);
    AVFormatContext *format = nullptr;
    AVBSFContext *filter = nullptr;
    AVPacket *packet = av_packet_alloc(), *out = av_packet_alloc();
    int status = avformat_open_input(&format, argv[1], nullptr, nullptr);
    int video = -1;
    if (status >= 0) {
        // Matroska codec parameters are available from its track headers.
        for (unsigned i = 0; i < format->nb_streams; ++i) {
            if (selectedVideo >= 0 && i != static_cast<unsigned>(selectedVideo)) continue;
            if (format->streams[i]->codecpar->codec_type == AVMEDIA_TYPE_VIDEO
                && format->streams[i]->codecpar->codec_id == AV_CODEC_ID_AV1) { video = i; break; }
        }
        if (video < 0 || format->streams[video]->codecpar->codec_id != AV_CODEC_ID_AV1) status = AVERROR_INVALIDDATA;
    }
    if (status >= 0) status = av_bsf_alloc(av_bsf_get_by_name("trace_headers"), &filter);
    if (status >= 0) {
        avcodec_parameters_copy(filter->par_in, format->streams[video]->codecpar);
        filter->time_base_in = timeBase = format->streams[video]->time_base;
        status = av_bsf_init(filter);
    }
    bool eof = false;
    unsigned metadataSkipped = 0;
    if (status >= 0) {
        while ((status = av_read_frame(format, packet)) >= 0) {
            if (packet->stream_index != video) { av_packet_unref(packet); continue; }
            packetPts = packet->pts;
            ++packets;
            // Some older encodes have malformed timecode metadata that strict
            // CBS rejects although ordinary decoders ignore it. It cannot
            // contain grain parameters. Strip only this unrelated OBU from
            // our in-memory copy, retaining every sequence/frame header.
            status = av_packet_make_writable(packet);
            if (status < 0) break;
            size_t packetSize = packet->size;
            bool hasSequence = false;
            if (!prepare_av1_scan_packet(packet->data, packetSize, hasSequence, metadataSkipped)) {
                status = AVERROR_INVALIDDATA; break;
            }
            av_shrink_packet(packet, static_cast<int>(packetSize));
            // A sequence that declares no grain cannot signal grain in any
            // frame. Still inspect every packet for a new sequence header.
            if (!packetSize || (grainPresent == 0 && !hasSequence)) {
                av_packet_unref(packet); continue;
            }
            status = av_bsf_send_packet(filter, packet);
            if (status < 0) break;
            while ((status = av_bsf_receive_packet(filter, out)) >= 0) av_packet_unref(out);
            if (status != AVERROR(EAGAIN) && status != AVERROR_EOF) break;
            if (unsafePlane >= 0) break;
        }
        eof = status == AVERROR_EOF;
    }
    const double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
    const char *verdict = unsafePlane >= 0 ? "unsafe_model" : eof && errors == 0 ? "stable" : "error";
    printf("{\"verdict\":\"%s\",\"packets\":%lld,\"unique_plane_models\":%lld,\"grain_present\":%d,\"complete\":%s,\"errors\":%d,\"metadata_obus_skipped\":%u,\"elapsed_seconds\":%.3f", verdict,
        static_cast<long long>(packets), static_cast<long long>(models), grainPresent, eof ? "true" : "false", errors, metadataSkipped, seconds);
    printf(",\"criterion\":\"%s\",\"max_pole_radius\":%.2f",
        stabilityOnly ? "stability" : "synthesis_texture_v1",
        stabilityOnly ? 1.0 : fgsmodel::film_grain_max_synthesis_pole_radius);
    if (unsafePlane >= 0) {
        printf(",\"first_unsafe_seconds\":%.6f,\"plane\":%d,\"lag\":%u,\"shift\":%u,\"coefficients\":[", badPts * av_q2d(timeBase), unsafePlane, bad.lag, bad.shift);
        for (unsigned i = 0; i < 2 * bad.lag * (bad.lag + 1); ++i) printf("%s%d", i ? "," : "", static_cast<int>(bad.coeff[unsafePlane][i]) - 128);
        printf("],\"max_scaling\":[%d,%d,%d],\"luma_coupling\":[%d,%d]", bad.maxScaling[0], bad.maxScaling[1], bad.maxScaling[2], bad.lumaCoupling[1], bad.lumaCoupling[2]);
        if (!stabilityOnly) {
            const bool decay = fgsmodel::film_grain_ar_within_radius(
                bad.coeff[unsafePlane].data(), bad.lag, bad.shift,
                fgsmodel::film_grain_max_synthesis_pole_radius);
            printf(",\"rejection_reason\":\"%s\"", decay ? "periodic_spectrum" : "feedback_decay");
        }
    }
    printf("}\n");
    if (errors || (!eof && unsafePlane < 0)) fprintf(stderr, "scan error %d: %s\n", status, firstError);
    av_packet_free(&packet); av_packet_free(&out); av_bsf_free(&filter); avformat_close_input(&format);
    return unsafePlane >= 0 ? 1 : eof && errors == 0 ? 0 : 2;
}
