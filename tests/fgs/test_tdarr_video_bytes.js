'use strict';
const test = require('node:test'), assert = require('node:assert/strict');
const bytes = require('../../tools/fgs/tdarr_video_bytes.js');
const size = require('../../tools/fgs/tdarr_source_size.js')._test;

test('byte-only optimization is confined to the exercised Matroska codecs', () => {
    for (const codec of ['h264', 'hevc', 'av1']) {
        const command = bytes.packetArguments('/media/fixture.mkv', {video: {index: 2, codec_name: codec}, format: 'matroska,webm'});
        assert(command.unparsed);
        assert(command.arguments.includes('+noparse+nofillin'));
        assert.equal(command.arguments[command.arguments.indexOf('-select_streams') + 1], '2');
        assert(!command.arguments.includes('-show_frames'));
    }
    for (const [format, codec] of [['mpegts', 'h264'], ['h264', 'h264'], ['mov,mp4,m4a,3gp,3g2,mj2', 'hevc'], ['matroska,webm', 'mpeg2video']]) {
        const command = bytes.packetArguments('/media/fixture', {video: {index: 0, codec_name: codec}, format});
        assert(!command.unparsed);
        assert(!command.arguments.includes('-fflags'));
    }
});
test('attachments cannot replace the primary video and ambiguous video is refused', () => {
    const video = {index: 2, codec_type: 'video', codec_name: 'hevc'};
    assert.equal(bytes.primary({streams: [{index: 0, codec_type: 'video', codec_name: 'mjpeg', disposition: {attached_pic: 1}}, video]}), video);
    assert.throws(() => bytes.primary({streams: [video, {...video, index: 3}]}));
});
test('missing, malformed and overflowing packet bytes cannot become a savings pass', () => {
    const total = {bytes: 0, packets: 0};
    bytes.addPacket(total, '123,packet side data');
    bytes.addPacket(total, '456');
    bytes.addPacket(total, '');
    assert.deepEqual(total, {bytes: 579, packets: 2});
    for (const text of ['N/A', '0', '-1', '1.2', '1e3', '9007199254740992']) assert.throws(() => bytes.addPacket({bytes: 0, packets: 0}, text));
    assert.throws(() => bytes.addPacket({bytes: Number.MAX_SAFE_INTEGER, packets: 1}, '1'));
});
test('pruning large audio cannot conceal video growth in source-relative savings', () => {
    assert.equal(size.sizeRatio(1400, 1000, 1200).ratio, 1400/1200);
    assert(size.sizeRatio(1400, 1000, 1200).ratio > .95);
    assert.equal(size.sizeRatio(900, 1000, 800).ratio, 900/1100);
    for (const values of [[100, 100, 200], [100, NaN, 50], [0, 100, 50]]) assert.throws(() => size.sizeRatio(...values));
});
