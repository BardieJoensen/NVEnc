'use strict';

// Byte accounting only. Never use these demux options for timing, metadata
// correspondence, decoded-frame checks or picture-quality validation.
const assert = require('node:assert/strict');
const cp = require('node:child_process');
const fs = require('node:fs');
const readline = require('node:readline');

function identity(file) {
    const stat = fs.statSync(file, {bigint: true});
    assert(stat.isFile(), 'Expected a regular file');
    return ['dev', 'ino', 'size', 'mtimeNs', 'ctimeNs'].map(k => String(stat[k])).join(':');
}
function primary(probe) {
    const videos = probe.streams.filter(s => s.codec_type === 'video' && !(s.disposition || {}).attached_pic
        && !['png', 'mjpeg', 'bmp', 'gif'].includes(s.codec_name));
    assert.equal(videos.length, 1, 'Expected one primary video');
    assert(Number.isSafeInteger(videos[0].index) && videos[0].index >= 0, 'Invalid video stream index');
    return videos[0];
}
function inspect(file) {
    const result = cp.spawnSync('/usr/local/bin/ffprobe', ['-v', 'error', '-show_streams',
        '-show_format', '-of', 'json', file], {timeout: 120000, maxBuffer: 16 * 1024**2, encoding: 'utf8'});
    if (result.error || result.status !== 0 || result.stderr.trim()) {
        throw new Error('Video inspection failed: ' + (result.error || result.stderr || result.status));
    }
    const probe = JSON.parse(result.stdout);
    return {video: primary(probe), format: probe.format.format_name};
}
function packetArguments(file, {video, format}) {
    // Complete Matroska blocks gave identical primary-video bytes and packet
    // counts with both paths on the real H.264, HEVC and AV1 regression corpus.
    // Keep parsers for other containers/codecs, including transport streams.
    const unparsed = String(format).split(',').includes('matroska')
        && ['h264', 'hevc', 'av1'].includes(video.codec_name);
    return {unparsed, arguments: ['-v', 'error', ...(unparsed ? ['-fflags', '+noparse+nofillin'] : []),
        '-select_streams', String(video.index), '-show_packets', '-show_entries', 'packet=size',
        '-of', 'csv=p=0', file]};
}
function addPacket(total, line) {
    if (!line.trim()) return;
    const first = line.split(',')[0];
    assert(/^\d+$/.test(first), 'Invalid video packet size');
    const size = Number(first);
    assert(Number.isSafeInteger(size) && size > 0, 'Invalid video packet size');
    total.bytes += size;
    total.packets++;
    assert(Number.isSafeInteger(total.bytes) && Number.isSafeInteger(total.packets), 'Video measurement exceeds exact integer range');
}
function measure(file, info = inspect(file)) {
    const command = packetArguments(file, info);
    return new Promise((resolve, reject) => {
        const total = {bytes: 0, packets: 0}, child = cp.spawn('/usr/local/bin/ffprobe', command.arguments,
            {stdio: ['ignore', 'pipe', 'pipe']});
        let stderr = '', parseError;
        const timer = setTimeout(() => child.kill('SIGKILL'), 1800000);
        const lines = readline.createInterface({input: child.stdout});
        lines.on('line', line => {
            try { addPacket(total, line); }
            catch (error) { parseError = error; child.kill('SIGKILL'); }
        });
        child.stderr.on('data', data => { stderr = (stderr + data).slice(-4096); });
        child.on('error', error => { clearTimeout(timer); reject(error); });
        child.on('close', code => {
            clearTimeout(timer);
            if (code !== 0 || stderr.trim() || parseError || !total.packets) {
                reject(new Error('Video byte measurement failed: ' + (parseError || stderr || code)));
            } else resolve({...total, mode: command.unparsed ? 'matroska_blocks' : 'parsed_packets'});
        });
    });
}

module.exports = {identity, inspect, measure, primary, packetArguments, addPacket};
