/* Read-only H264 QP_Y state export. Skipped MB QP is state, not proof that
 * residual quantization executed. No encoder is changed. */
#include <stdio.h>
#include <stdlib.h>
#include <libavformat/avformat.h>
#include <libavcodec/avcodec.h>
#include <libavutil/frame.h>
#include <libavutil/video_enc_params.h>
static void require(int ok, const char *why) {
    if (!ok) { fprintf(stderr, "QP export failed: %s\n", why); exit(1); }
}
static void emit(AVFrame *r, FILE *out, int fi) {
    require(fi < 336 && r->width == 1920 && r->height == 1080 && r->format == AV_PIX_FMT_YUV420P, "frame geometry/format/count");
    AVFrameSideData *sd = av_frame_get_side_data(r, AV_FRAME_DATA_VIDEO_ENC_PARAMS);
    require(sd && sd->size >= sizeof(AVVideoEncParams), "missing parameter side data");
    AVVideoEncParams *e = (AVVideoEncParams *)sd->data;
    require(e->type == AV_VIDEO_ENC_PARAMS_H264 && e->nb_blocks == 8160, "H264 block population");
    require(e->block_size >= sizeof(AVVideoBlockParams) && e->blocks_offset <= sd->size &&
            e->nb_blocks <= (sd->size - e->blocks_offset) / e->block_size, "side data bounds");
    for (unsigned i = 0; i < e->nb_blocks; i++) {
        AVVideoBlockParams *b = av_video_enc_params_block(e, i);
        require(b->w == 16 && b->h == 16 && b->src_x >= 0 && b->src_x < 1920 &&
                b->src_y >= 0 && b->src_y < 1088 && b->src_x % 16 == 0 && b->src_y % 16 == 0, "MB geometry");
        int q = e->qp + b->delta_qp;
        require(q >= 0 && q <= 51, "8-bit QP_Y range");
        fprintf(out, "%d,%lld,%d,%d,%d,%d,%d,%d,%d,%d,%u\n", fi, (long long)r->pts,
                e->qp, b->delta_qp, b->src_x, b->src_y, b->w, b->h, q, e->type, e->nb_blocks);
    }
    require(!ferror(out), "write error");
}
static void receive(AVCodecContext *ctx, AVFrame *frame, FILE *out, int *count, int flushing) {
    for (;;) {
        int ret = avcodec_receive_frame(ctx, frame);
        if (ret == AVERROR_EOF) { require(flushing, "unexpected EOF before flush"); return; }
        if (ret == AVERROR(EAGAIN)) { require(!flushing, "EAGAIN after flush"); return; }
        require(ret == 0, "receive frame");
        emit(frame, out, (*count)++); av_frame_unref(frame);
    }
}
int main(int argc, char **argv) {
    require(argc == 3, "usage: exporter INPUT OUTPUT.csv");
    av_log_set_level(AV_LOG_WARNING);
    AVFormatContext *fmt = NULL;
    require(avformat_open_input(&fmt, argv[1], NULL, NULL) == 0 && avformat_find_stream_info(fmt, NULL) >= 0, "open input");
    int si = av_find_best_stream(fmt, AVMEDIA_TYPE_VIDEO, -1, -1, NULL, 0);
    require(si >= 0 && fmt->streams[si]->codecpar->codec_id == AV_CODEC_ID_H264, "H264 video stream");
    const AVCodec *codec = avcodec_find_decoder(AV_CODEC_ID_H264);
    AVCodecContext *ctx = avcodec_alloc_context3(codec);
    require(ctx && avcodec_parameters_to_context(ctx, fmt->streams[si]->codecpar) == 0, "decoder parameters");
    ctx->thread_count = 2; ctx->export_side_data |= AV_CODEC_EXPORT_DATA_VIDEO_ENC_PARAMS;
    require(avcodec_open2(ctx, codec, NULL) == 0, "open decoder");
    FILE *out = fopen(argv[2], "wx"); require(out != NULL, "fresh output");
    fprintf(out, "frame,pts,qp,delta_qp,src_x,src_y,w,h,effective_qp,type,nb_blocks\n");
    AVPacket *pkt = av_packet_alloc(); AVFrame *frame = av_frame_alloc();
    require(pkt && frame, "packet/frame allocation");
    int count = 0, ret;
    while ((ret = av_read_frame(fmt, pkt)) >= 0) {
        if (pkt->stream_index == si) {
            /* Previous receive drains to EAGAIN; fail instead of dropping a
             * packet if send-side EAGAIN unexpectedly occurs. */
            require(avcodec_send_packet(ctx, pkt) == 0, "send packet");
            receive(ctx, frame, out, &count, 0);
        }
        av_packet_unref(pkt);
    }
    require(ret == AVERROR_EOF, "demux EOF");
    require(avcodec_send_packet(ctx, NULL) == 0, "send flush");
    receive(ctx, frame, out, &count, 1);
    require(count == 336 && !ferror(out), "complete decoded population");
    require(fclose(out) == 0, "close output");
    fprintf(stderr, "decoded_frames=%d frames_with_side_data=%d missing=0 libavcodec=%u libavutil=%u\n", count, count, avcodec_version(), avutil_version());
    av_frame_free(&frame); av_packet_free(&pkt); avcodec_free_context(&ctx); avformat_close_input(&fmt);
    return 0;
}
