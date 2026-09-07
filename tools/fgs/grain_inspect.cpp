// Read-only RGB-display approximation after range/gamut clipping. Nearest chroma sampling.
// Subtract each patch mean before measuring texture amplitude; uniform color shifts are not ripple.
// Scores order visual inspection and never constitute a damage verdict.
// Apply decoder grain to the same decoded picture and measure native patches.
// MIT license, as NVEncFilmGrainModel.h.
#include <dav1d/dav1d.h>
extern "C" {
#include <libavformat/avformat.h>
}
#include <cmath>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
static void checked(int result, const char *operation) {
    if (result < 0) throw std::runtime_error(std::string(operation) + ": " + std::to_string(result));
}
#include <algorithm>
#include <array>
#include <chrono>

struct Metrics {
    double rms = 0, max_patch_rms = 0, correlation = 0, score = 0;
    int dx = 0, dy = 0;
    std::array<double, 12> acf{};
};

template <typename Pixel>
static std::array<float, 3> display_values(const Dav1dPicture& p, int x, int y) {
    const float scale = 1.0f / (1 << (p.p.bpc - 8));
    const auto* yy = static_cast<const Pixel*>(p.data[0]);
    const auto* uu = static_cast<const Pixel*>(p.data[1]);
    const auto* vv = static_cast<const Pixel*>(p.data[2]);
    const auto ys = p.stride[0] / sizeof(Pixel), cs = p.stride[1] / sizeof(Pixel);
    const bool full = p.seq_hdr->color_range;
    const float luma = (yy[y*ys+x]*scale-(full ? 0.0f : 16.0f)) * (full ? 1.0f : 255.0f/219.0f);
    const float cb = (uu[(y/2)*cs+x/2]*scale-128.0f) * (full ? 1.0f : 255.0f/224.0f);
    const float cr = (vv[(y/2)*cs+x/2]*scale-128.0f) * (full ? 1.0f : 255.0f/224.0f);
    const bool sd = p.seq_hdr->mtrx == 5 || p.seq_hdr->mtrx == 6;
    const float kr = sd ? .299f : .2126f, kb = sd ? .114f : .0722f, kg = 1-kr-kb;
    const float red = std::nearbyint(std::clamp(luma + 2*(1-kr)*cr, 0.0f, 255.0f));
    const float blue = std::nearbyint(std::clamp(luma + 2*(1-kb)*cb, 0.0f, 255.0f));
    const float green = std::nearbyint(std::clamp(luma - 2*kb*(1-kb)/kg*cb - 2*kr*(1-kr)/kg*cr, 0.0f, 255.0f));
    return {.2126f*red + .7152f*green + .0722f*blue, red, blue};
}

template <typename Pixel>
static std::array<Metrics, 3> measure(const Dav1dPicture& off, const Dav1dPicture& on) {
    constexpr int side = 48;
    constexpr int offsets[][2] = {{1,0},{0,1},{1,1},{-1,1},{2,0},{0,2},{2,2},{-2,2},{3,0},{0,3},{3,3},{-3,3}};
    std::array<std::array<double, 12>, 3> cross{}, left{}, right{};
    const int width = off.p.w, height = off.p.h;
    std::array<double, 3> total{};
    std::array<Metrics, 3> result{};
    for (int py = 1; py <= 3; ++py) for (int px = 1; px <= 3; ++px) {
        const int x0 = std::clamp(width * px / 4 - side / 2, 0, width - side);
        const int y0 = std::clamp(height * py / 4 - side / 2, 0, height - side);
        float delta[3][side][side];
        std::array<double, 3> sum{}, square{};
        // Convert each source/output pixel once for all three measurements.
        for (int y = 0; y < side; ++y) for (int x = 0; x < side; ++x) {
            const auto displayed = display_values<Pixel>(on, x0+x, y0+y);
            const auto base = display_values<Pixel>(off, x0+x, y0+y);
            for (int channel = 0; channel < 3; ++channel) {
                const float v = displayed[channel] - base[channel];
                delta[channel][y][x] = v; sum[channel] += v; square[channel] += v*v;
            }
        }
        for (int channel = 0; channel < 3; ++channel) {
            const float mean = sum[channel] / (side*side);
            const double variance_sum = std::max(0.0, square[channel] - sum[channel]*sum[channel]/(side*side));
            result[channel].max_patch_rms = std::max(result[channel].max_patch_rms, std::sqrt(variance_sum / (side*side)));
            total[channel] += variance_sum;
            double centered[side][side], squares[side][side];
            for (int y = 0; y < side; ++y) for (int x = 0; x < side; ++x) {
                // Preserve the original float subtraction before promotion.
                centered[y][x] = delta[channel][y][x] - mean;
                squares[y][x] = centered[y][x] * centered[y][x];
            }
            double l = 0;
            for (int y = 3; y < side-3; ++y) for (int x = 3; x < side-3; ++x)
                l += squares[y][x];
            for (int k = 0; k < 12; ++k) {
                const int dx = offsets[k][0], dy = offsets[k][1];
                double c = 0, r = 0;
                for (int y = 3; y < side-3; ++y) for (int x = 3; x < side-3; ++x) {
                    c += centered[y][x] * centered[y+dy][x+dx];
                    r += squares[y+dy][x+dx];
                }
                cross[channel][k] += c; left[channel][k] += l; right[channel][k] += r;
            }
        }
    }
    for (int channel = 0; channel < 3; ++channel) {
        auto& m = result[channel];
        m.rms = std::sqrt(total[channel] / (9*side*side));
        for (int k = 0; k < 12; ++k) {
            const double corr = left[channel][k]*right[channel][k] > 0
                ? cross[channel][k]/std::sqrt(left[channel][k]*right[channel][k]) : 0;
            m.acf[k] = corr;
            if (std::abs(corr) > std::abs(m.correlation)) {
                m.correlation = corr; m.dx = offsets[k][0]; m.dy = offsets[k][1];
            }
        }
        m.score = m.rms * std::abs(m.correlation);
    }
    return result;
}

int main(int argc, char **argv) {
    try {
        const bool correlations = argc > 1 && !std::strcmp(argv[1], "--correlations");
        if (correlations) { --argc; ++argv; }
        if (argc != 3 && argc != 5) throw std::runtime_error("usage: fgs-grain-inspect [--correlations] FILE OUTPUT_CSV [START STOP]");
        const double start = argc == 5 ? std::stod(argv[3]) : 0;
        const double stop = argc == 5 ? std::stod(argv[4]) : 1e12;
        if (!std::isfinite(start) || !std::isfinite(stop) || start < 0 || stop <= start)
            throw std::runtime_error("invalid measurement interval");
        if (std::filesystem::exists(argv[2])) throw std::runtime_error("refusing existing output");
        std::ofstream output(argv[2]);
        if (!output) throw std::runtime_error("cannot create output CSV");
        output << "seconds,grain_present";
        for (const auto* plane : {"luma", "red", "blue"}) {
            for (const auto* field : {"rms", "max_patch_rms", "correlation", "score", "dx", "dy"}) output << ',' << plane << '_' << field;
            if (correlations) for (int i = 0; i < 12; ++i) output << ',' << plane << "_acf_" << i;
        }
        output << '\n' << std::setprecision(9);
        av_log_set_level(AV_LOG_ERROR);
        AVFormatContext *format = nullptr;
        checked(avformat_open_input(&format, argv[1], nullptr, nullptr), "open input");
        int video = -1;
        for (unsigned i = 0; i < format->nb_streams; ++i) if (format->streams[i]->codecpar->codec_type == AVMEDIA_TYPE_VIDEO) { video = i; break; }
        if (video < 0 || format->streams[video]->codecpar->codec_id != AV_CODEC_ID_AV1) throw std::runtime_error("first video is not AV1");
        auto *stream = format->streams[video];
        const double tb = av_q2d(stream->time_base);
        if (start > 0) checked(av_seek_frame(format, video, int64_t(std::floor(start/tb)), AVSEEK_FLAG_BACKWARD), "seek");
        Dav1dSettings settings; dav1d_default_settings(&settings);
        settings.n_threads = 4; settings.max_frame_delay = 1; settings.apply_grain = 0;
        Dav1dContext *decoder = nullptr;
        checked(dav1d_open(&decoder, &settings), "open decoder");
        auto *codec = stream->codecpar;
        if (codec->extradata_size > 4) {
            const int skip = codec->extradata[0] & 0x80 ? 4 : 0;
            Dav1dSequenceHeader sequence{};
            if (!dav1d_parse_sequence_header(&sequence, codec->extradata+skip, codec->extradata_size-skip)) {
                Dav1dData headers{}; auto *bytes = dav1d_data_create(&headers, codec->extradata_size-skip);
                if (!bytes) throw std::runtime_error("header allocation failed");
                std::memcpy(bytes, codec->extradata+skip, codec->extradata_size-skip);
                checked(dav1d_send_data(decoder, &headers), "send sequence header");
            }
        }
        AVPacket *packet = av_packet_alloc(); Dav1dData data{};
        int decoded = 0, measured = 0; double last = -1;
        bool eof = false, fully_drained = false;
        const auto began = std::chrono::steady_clock::now();
        while (true) {
            if (!data.sz && !eof) {
                int status;
                while ((status = av_read_frame(format, packet)) >= 0 && packet->stream_index != video) av_packet_unref(packet);
                if (status == AVERROR_EOF) eof = true;
                else {
                    checked(status, "read packet"); auto *bytes = dav1d_data_create(&data, packet->size);
                    if (!bytes) throw std::runtime_error("packet allocation failed");
                    std::memcpy(bytes, packet->data, packet->size); data.m.timestamp = packet->pts; av_packet_unref(packet);
                }
            }
            if (data.sz) { const int status = dav1d_send_data(decoder, &data); if (status != DAV1D_ERR(EAGAIN)) checked(status, "decode packet"); }
            Dav1dPicture off{}; const int status = dav1d_get_picture(decoder, &off);
            if (status == DAV1D_ERR(EAGAIN)) { if (eof && !data.sz) { fully_drained = true; break; } continue; }
            checked(status, "get picture"); ++decoded;
            if (off.m.timestamp == INT64_MIN || off.p.layout != DAV1D_PIXEL_LAYOUT_I420) throw std::runtime_error("unsupported displayed picture");
            if (off.p.w < 48 || off.p.h < 48)
                throw std::runtime_error("picture is smaller than the 48x48 measurement patch");
            if (off.seq_hdr->trc == 16 || off.seq_hdr->trc == 18 || off.seq_hdr->mtrx == 9 || off.seq_hdr->mtrx == 10)
                throw std::runtime_error("HDR/BT2020 requires separately calibrated display mapping");
            const double seconds = off.m.timestamp * tb;
            if (seconds >= stop) { dav1d_picture_unref(&off); break; }
            if (seconds + 1e-7 >= start) {
                if (seconds <= last) throw std::runtime_error("non-increasing displayed timestamp");
                last = seconds;
                const bool present = off.frame_hdr->film_grain.present;
                Dav1dPicture on{};
                if (present) checked(dav1d_apply_grain(decoder, &on, &off), "apply grain");
                output << seconds << ',' << present;
                const auto metrics = !present ? std::array<Metrics, 3>{}
                    : off.p.bpc > 8 ? measure<uint16_t>(off,on) : measure<uint8_t>(off,on);
                for (const auto& m : metrics) {
                    output << ',' << m.rms << ',' << m.max_patch_rms << ',' << m.correlation << ',' << m.score << ',' << m.dx << ',' << m.dy;
                    if (correlations) for (const auto value : m.acf) output << ',' << value;
                }
                output << '\n'; ++measured;
                if (present) dav1d_picture_unref(&on);
                if (measured % 2400 == 0) {
                    output.flush();
                    std::cerr << "{\"measured_frames\":" << measured << ",\"seconds\":" << seconds << ",\"elapsed_seconds\":" << std::chrono::duration<double>(std::chrono::steady_clock::now()-began).count() << "}\n";
                }
            }
            dav1d_picture_unref(&off);
        }
        dav1d_data_unref(&data); av_packet_free(&packet); dav1d_close(&decoder); avformat_close_input(&format);
        output.close(); if (!output) throw std::runtime_error("CSV write failed");
        std::cout << "{\"decoder_version\":\"" << dav1d_version() << "\",\"decoded_frames\":" << decoded
                  << ",\"measured_frames\":" << measured << ",\"last_seconds\":" << last << ",\"complete\":" << (fully_drained ? "true" : "false")
                  << ",\"elapsed_seconds\":" << std::chrono::duration<double>(std::chrono::steady_clock::now()-began).count() << "}\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 2; }
}
