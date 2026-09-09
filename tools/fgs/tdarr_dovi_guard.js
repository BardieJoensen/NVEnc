'use strict';

// A small post-encode check for the demonstrated P7-to-AV1 conversion failure.
// Full metadata correspondence remains an offline development check.
const assert = require('node:assert/strict');
const cp = require('node:child_process');
const fs = require('node:fs');

function identity(file) {
    const s = fs.statSync(file, {bigint: true});
    assert(s.isFile(), 'Expected a regular output file');
    return ['dev', 'ino', 'size', 'mtimeNs', 'ctimeNs'].map(k => String(s[k])).join(':');
}
function probe(file, args) {
    return JSON.parse(cp.execFileSync('/usr/local/bin/ffprobe',
        ['-v', 'error', ...args, '-of', 'json', file],
        {timeout: 120000, maxBuffer: 16 * 1024**2}));
}
function checkConfiguration(streams) {
    const primary = streams.filter(s => s.codec_type === 'video' && !(s.disposition || {}).attached_pic);
    assert.equal(primary.length, 1, 'Expected exactly one primary video');
    const video = primary[0];
    const conf = (video.side_data_list || []).filter(s => s.side_data_type === 'DOVI configuration record');
    if (!conf.length) return {hasDovi: false, video};
    assert.equal(conf.length, 1, 'Duplicate Dolby Vision configuration');
    assert.equal(video.codec_name, 'av1', 'Fidelity candidate must use AV1');
    for (const [key, expected] of Object.entries({dv_profile: 10, rpu_present_flag: 1,
        el_present_flag: 0, bl_present_flag: 1})) {
        assert.equal(conf[0][key], expected, `Invalid single-layer Dolby Vision ${key}`);
    }
    assert([0, 1, 2, 4].includes(conf[0].dv_bl_signal_compatibility_id), 'Unsupported AV1 Dolby Vision compatibility');
    return {hasDovi: true, video};
}
function checkFrames(frames) {
    assert(Array.isArray(frames) && frames.length > 0, 'No displayed frames for Dolby Vision check');
    for (const frame of frames) {
        const metadata = (frame.side_data_list || []).filter(s => s.side_data_type === 'Dolby Vision Metadata');
        assert.equal(metadata.length, 1, 'Missing or duplicate decoded Dolby Vision metadata');
        const m = metadata[0];
        assert.equal(m.disable_residual_flag, 1, 'Unconverted enhancement-layer residual in AV1 metadata');
        assert.equal(m.el_spatial_resampling_filter_flag, 0, 'Unconverted enhancement-layer resampling in AV1 metadata');
        // FFprobe exposes the absent-NLQ enum as -1 on current builds; older
        // exporters may omit it. Zero means linear deadzone, not "absent".
        assert(!Object.hasOwn(m, 'nlq_method_idc') || m.nlq_method_idc === -1,
            'Unconverted dual-layer mapping in AV1 metadata');
    }
    return frames.length;
}
async function plugin(args) {
    const output = args.inputFileObj._id, before = identity(output), start = Date.now();
    const {hasDovi, video} = checkConfiguration(probe(output, ['-show_streams']).streams);
    let frames = 0;
    if (hasDovi) {
        const sample = probe(output, ['-threads', '2', '-select_streams', String(video.index),
            '-read_intervals', '%+#16', '-show_frames', '-show_entries', 'frame=side_data_list']);
        frames = checkFrames(sample.frames);
    }
    assert.equal(identity(output), before, 'Output changed during Dolby Vision check');
    args.variables.user = args.variables.user || {};
    args.variables.user.fidelityDoviCheck = {passed: true, has_dovi: hasDovi,
        sampled_frames: frames, seconds: (Date.now() - start) / 1000,
        scope: 'Initial decoded RPU normalization and container signaling; not full-file HDR correspondence'};
    args.jobLog(`[fidelity-dovi] ${hasDovi ? `${frames} initial frames have normalized single-layer metadata`
        : 'No Dolby Vision configuration'}; ${(Date.now() - start) / 1000}s`);
    return {outputFileObj: args.inputFileObj, outputNumber: 1, variables: args.variables};
}

exports.details = () => ({name: 'Check AV1 Dolby Vision Normalization',
    description: 'Catch unconverted dual-layer RPU metadata before accepting a Dolby Vision AV1 candidate.',
    style: {borderColor: '#a8e6cf'}, tags: 'video', isStartPlugin: false, pType: '',
    requiresVersion: '2.11.01', sidebarPosition: -1, icon: 'faCheck', inputs: [],
    outputs: [{number: 1, tooltip: 'Normalization check passed; continue final validation'}]});
exports.plugin = plugin;
exports._test = {checkConfiguration, checkFrames};
