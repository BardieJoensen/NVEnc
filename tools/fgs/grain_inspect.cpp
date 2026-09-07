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
#include <memory>
#include <limits>
#include <tuple>
#include "picture_measurement.h"

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
        bool correlations=false, extended=false, assume_bt709=false;
        double sample_period=0, peak_nits=1000, sdr_white_nits=100;
        int stream_index=-1; std::string tiles_path;
        const auto number=[](const char* value) {
            size_t used=0; const double n=std::stod(value,&used);
            if(used!=std::strlen(value) || !std::isfinite(n)) throw std::runtime_error("invalid numeric option");
            return n;
        };
        while(argc>1 && std::strncmp(argv[1],"--",2)==0) {
            const std::string option=argv[1];
            if(option=="--correlations") { correlations=true; --argc;++argv; }
            else if(option=="--extended") { extended=true;--argc;++argv; }
            else if(option=="--assume-bt709") { assume_bt709=true;--argc;++argv; }
            else {
                if(argc<3)throw std::runtime_error("missing option value");
                if(option=="--sample-period")sample_period=number(argv[2]);
                else if(option=="--peak-nits")peak_nits=number(argv[2]);
                else if(option=="--sdr-white-nits")sdr_white_nits=number(argv[2]);
                else if(option=="--tiles-csv")tiles_path=argv[2];
                else if(option=="--stream-index") {
                    const double v=number(argv[2]);
                    if(v<0 || v>100000 || v!=std::floor(v))throw std::runtime_error("invalid stream index");
                    stream_index=int(v);
                } else throw std::runtime_error("unknown option: "+option);
                argc-=2;argv+=2;
            }
        }
        if (argc != 3 && argc != 5) throw std::runtime_error("usage: fgs-grain-inspect [--correlations] [--extended --assume-bt709 --sample-period SECONDS --peak-nits N --sdr-white-nits N --tiles-csv PATH] [--stream-index N] FILE OUTPUT_CSV [START STOP]");
        if(sample_period<0 || (!extended && (assume_bt709 || sample_period!=0 || !tiles_path.empty() || peak_nits!=1000 || sdr_white_nits!=100)))
            throw std::runtime_error("display/spatial options require --extended and a nonnegative sample period");
        const double start = argc == 5 ? number(argv[3]) : 0;
        const double stop = argc == 5 ? number(argv[4]) : 1e12;
        if (!std::isfinite(start) || !std::isfinite(stop) || start < 0 || stop <= start)
            throw std::runtime_error("invalid measurement interval");
        if (std::filesystem::exists(argv[2])) throw std::runtime_error("refusing existing output");
        std::ofstream output(argv[2]);
        if (!output) throw std::runtime_error("cannot create output CSV");
        std::ofstream tiles;
        if(!tiles_path.empty()) {
            if(std::filesystem::exists(tiles_path))throw std::runtime_error("refusing existing tiles CSV");
            tiles.open(tiles_path);if(!tiles)throw std::runtime_error("cannot create tiles CSV");
            tiles<<"seconds,x,y,width,height,channel,rms,correlation,score,dx,dy,directional_score\n"<<std::setprecision(9);
        }
        output << "seconds,grain_present";
        if(extended) {
            output<<",tiles,pixels,clipped_base_pixels,clipped_grain_pixels";
            for(const auto* plane:{"luma","red","green","blue"}) {
                for(const auto* field:{"rms","max_tile_rms","peak_score","peak_x","peak_y","correlation","dx","dy","p95_tile_score","p99_tile_score","peak_directional_score","directional_x","directional_y"})output<<','<<plane<<'_'<<field;
                if(correlations)for(int i=0;i<12;++i)output<<','<<plane<<"_acf_"<<i;
            }
        } else for (const auto* plane : {"luma", "red", "blue"}) {
            for (const auto* field : {"rms", "max_patch_rms", "correlation", "score", "dx", "dy"}) output << ',' << plane << '_' << field;
            if (correlations) for (int i = 0; i < 12; ++i) output << ',' << plane << "_acf_" << i;
        }
        output << '\n' << std::setprecision(9);
        av_log_set_level(AV_LOG_ERROR);
        AVFormatContext *format = nullptr;
        checked(avformat_open_input(&format, argv[1], nullptr, nullptr), "open input");
        int video=stream_index;
        if(video<0)for(unsigned i=0;i<format->nb_streams;++i) {
            if(format->streams[i]->codecpar->codec_type!=AVMEDIA_TYPE_VIDEO || (format->streams[i]->disposition&AV_DISPOSITION_ATTACHED_PIC))continue;
            if(video>=0)throw std::runtime_error("multiple video streams; select --stream-index explicitly");
            video=int(i);
        }
        if(video<0 || unsigned(video)>=format->nb_streams || format->streams[video]->codecpar->codec_id!=AV_CODEC_ID_AV1)
            throw std::runtime_error("selected video is not AV1");
        auto *stream = format->streams[video];
        const double tb = av_q2d(stream->time_base);
        if (start > 0) checked(av_seek_frame(format, video, int64_t(std::floor(start/tb)), AVSEEK_FLAG_BACKWARD), "seek");
        Dav1dSettings settings; dav1d_default_settings(&settings);
        settings.n_threads = 4; settings.max_frame_delay = 1; settings.apply_grain = 0;
        settings.frame_size_limit=8192u*4320u;
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
        int decoded = 0, measured = 0; double last = -1, last_displayed=-1, next_sample=start;
        std::unique_ptr<fgs_inspect::DisplayMapper> mapper;
        std::array<int,9> picture_signature{}; bool have_signature=false;
        uint64_t measured_pixels=0,clipped_base=0,clipped_grain=0;
        bool eof = false, fully_drained = false;
        const auto began = std::chrono::steady_clock::now();
        auto progress_at=began;
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
            if (off.m.timestamp == INT64_MIN || (!extended && off.p.layout != DAV1D_PIXEL_LAYOUT_I420)) throw std::runtime_error("unsupported displayed picture");
            if(off.p.w<(extended?8:48) || off.p.h<(extended?8:48))throw std::runtime_error("picture smaller than measurement tile");
            const std::array<int,9> current_signature{off.p.w,off.p.h,off.p.bpc,int(off.p.layout),int(off.seq_hdr->trc),int(off.seq_hdr->mtrx),int(off.seq_hdr->pri),int(off.seq_hdr->color_range),int(off.seq_hdr->chr)};
            if(have_signature && current_signature!=picture_signature)throw std::runtime_error("display metadata or geometry changed within measurement stream");
            picture_signature=current_signature;have_signature=true;
            if(extended && !mapper) {
                fgs_inspect::DisplayConfig config;
                config.transfer=off.seq_hdr->trc;config.matrix=off.seq_hdr->mtrx;config.primaries=off.seq_hdr->pri;
                if(assume_bt709) {
                    if(config.transfer!=2 && config.transfer!=1 && config.transfer!=6)
                        throw std::runtime_error("BT.709 assumption cannot override HDR/other transfer signalling");
                    if(config.matrix!=2 && config.matrix!=1)throw std::runtime_error("BT.709 assumption conflicts with matrix signalling");
                    if(config.primaries!=2 && config.primaries!=1)throw std::runtime_error("BT.709 assumption conflicts with primary signalling");
                    if(config.transfer==2)config.transfer=1;
                    if(config.matrix==2)config.matrix=1;
                    if(config.primaries==2)config.primaries=1;
                }
                config.depth=off.p.bpc;config.full_range=off.seq_hdr->color_range;config.peak_nits=peak_nits;config.sdr_white_nits=sdr_white_nits;
                mapper=std::make_unique<fgs_inspect::DisplayMapper>(config);
            }
            if (!extended && (off.seq_hdr->trc == 16 || off.seq_hdr->trc == 18 || off.seq_hdr->mtrx == 9 || off.seq_hdr->mtrx == 10))
                throw std::runtime_error("HDR/BT2020 requires --extended reference-display mapping");
            const double seconds = off.m.timestamp * tb;
            if(!std::isfinite(seconds) || (decoded>1 && seconds<=last_displayed))throw std::runtime_error("non-increasing displayed timestamp");
            last_displayed=seconds;
            if (seconds >= stop) { dav1d_picture_unref(&off); break; }
            if (seconds + 1e-7 >= next_sample) {
                last = seconds;
                if(sample_period>0)next_sample=start+(std::floor((seconds-start+1e-7)/sample_period)+1)*sample_period;
                const bool present = off.frame_hdr->film_grain.present;
                Dav1dPicture on{};
                if (present) checked(dav1d_apply_grain(decoder, &on, &off), "apply grain");
                output << seconds << ',' << present;
                if(extended) {
                    const auto full=off.p.bpc>8 ? fgs_inspect::measure_full<uint16_t>(off,present?&on:nullptr,*mapper,tiles.is_open()?&tiles:nullptr,seconds)
                                               : fgs_inspect::measure_full<uint8_t>(off,present?&on:nullptr,*mapper,tiles.is_open()?&tiles:nullptr,seconds);
                    measured_pixels+=full.pixels;clipped_base+=full.clipped_base_pixels;clipped_grain+=full.clipped_grain_pixels;
                    output<<','<<full.tiles<<','<<full.pixels<<','<<full.clipped_base_pixels<<','<<full.clipped_grain_pixels;
                    for(const auto& m:full.channels) {
                        output<<','<<m.rms<<','<<m.max_tile_rms<<','<<m.peak_score<<','<<m.peak_x<<','<<m.peak_y<<','<<m.peak.correlation<<','<<m.peak.dx<<','<<m.peak.dy<<','<<m.p95_tile_score<<','<<m.p99_tile_score<<','<<m.peak_directional_score<<','<<m.directional_x<<','<<m.directional_y;
                        if(correlations)for(const auto v:m.peak.acf)output<<','<<v;
                    }
                } else {
                    const auto metrics = !present ? std::array<Metrics, 3>{}
                        : off.p.bpc > 8 ? measure<uint16_t>(off,on) : measure<uint8_t>(off,on);
                    for (const auto& m : metrics) {
                        output << ',' << m.rms << ',' << m.max_patch_rms << ',' << m.correlation << ',' << m.score << ',' << m.dx << ',' << m.dy;
                        if (correlations) for (const auto value : m.acf) output << ',' << value;
                    }
                }
                output << '\n'; ++measured;
                if (present) dav1d_picture_unref(&on);
                if (measured % 2400 == 0 || (extended && std::chrono::duration<double>(std::chrono::steady_clock::now()-progress_at).count()>=5)) {
                    progress_at=std::chrono::steady_clock::now();
                    output.flush();
                    std::cerr << "{\"measured_frames\":" << measured << ",\"seconds\":" << seconds << ",\"elapsed_seconds\":" << std::chrono::duration<double>(std::chrono::steady_clock::now()-began).count() << "}\n";
                }
            }
            dav1d_picture_unref(&off);
        }
        dav1d_data_unref(&data); av_packet_free(&packet); dav1d_close(&decoder); avformat_close_input(&format);
        output.close(); if (!output) throw std::runtime_error("CSV write failed");
        if(tiles.is_open()) { tiles.close();if(!tiles)throw std::runtime_error("tile CSV write failed"); }
        if(!measured)throw std::runtime_error("no displayed frames in requested interval");
        std::cout << "{\"decoder_version\":\"" << dav1d_version() << "\",\"decoded_frames\":" << decoded
                  << ",\"measured_frames\":" << measured << ",\"last_seconds\":" << last << ",\"complete\":" << (fully_drained ? "true" : "false")
                  << ",\"elapsed_seconds\":" << std::chrono::duration<double>(std::chrono::steady_clock::now()-began).count()
                  << ",\"stream_index\":"<<video
                  << ",\"interval_complete\":"<<((fully_drained || last_displayed>=stop)?"true":"false")
                  << ",\"decoded_through_seconds\":"<<last_displayed;
        if(extended) {
            std::cout<<",\"schema\":\"fgs_reference_full_v1\",\"units\":\"PU21_banding_glare\",\"transfer\":\""<<mapper->transfer_name()
                <<"\",\"matrix\":"<<mapper->config.matrix<<",\"primaries\":"<<mapper->config.primaries
                <<",\"peak_nits\":"<<peak_nits<<",\"sdr_white_nits\":"<<sdr_white_nits
                <<",\"assume_bt709_requested\":"<<(assume_bt709?"true":"false")
                <<",\"signalled_transfer\":"<<picture_signature[4]<<",\"signalled_matrix\":"<<picture_signature[5]<<",\"signalled_primaries\":"<<picture_signature[6]
                <<",\"black_nits\":0,\"sample_period_seconds\":"<<sample_period
                <<",\"spatial_coverage_fraction\":1,\"width\":"<<picture_signature[0]<<",\"height\":"<<picture_signature[1]
                <<",\"bit_depth\":"<<picture_signature[2]<<",\"pixel_layout\":"<<picture_signature[3]
                <<",\"full_range\":"<<(mapper->config.full_range?"true":"false")
                <<",\"chroma_position\":"<<picture_signature[8]<<",\"chroma_reconstruction\":\"bilinear; unknown position assumes centered\""
                <<",\"measured_pixels\":"<<measured_pixels<<",\"clipped_base_pixels\":"<<clipped_base<<",\"clipped_grain_pixels\":"<<clipped_grain
                <<",\"dynamic_hdr_mapping_applied\":false,\"scope\":\"All pixels of measured frames on a static reference display. Local texture scores require contextual review.\"";
        }
        std::cout<<"}\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 2; }
}
