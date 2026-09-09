'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const {_test: {checkConfiguration, checkFrames}} = require('../../tools/fgs/tdarr_dovi_guard.js');
const config = () => [{index: 0, codec_type: 'video', codec_name: 'av1', side_data_list: [{
    side_data_type: 'DOVI configuration record', dv_profile: 10, el_present_flag: 0,
    bl_present_flag: 1, rpu_present_flag: 1, dv_bl_signal_compatibility_id: 1,
}]}];
const frame = () => ({side_data_list: [{side_data_type: 'Dolby Vision Metadata',
    disable_residual_flag: 1, el_spatial_resampling_filter_flag: 0, nlq_method_idc: -1}]});

test('SDR needs no decoded Dolby Vision sample; valid profile 10 does', () => {
    assert.equal(checkConfiguration([{codec_type: 'video', codec_name: 'av1'}]).hasDovi, false);
    assert.equal(checkConfiguration(config()).hasDovi, true);
    assert.equal(checkFrames([frame(), frame()]), 2);
    const older = frame(); delete older.side_data_list[0].nlq_method_idc;
    assert.equal(checkFrames([older]), 1);
});
test('the observed unconverted MEL RPU is rejected despite valid profile 10 signaling', () => {
    assert.equal(checkConfiguration(config()).hasDovi, true);
    const f = frame(); Object.assign(f.side_data_list[0], {disable_residual_flag: 0,
        el_spatial_resampling_filter_flag: 1, nlq_method_idc: 0});
    assert.throws(() => checkFrames([f]), /Unconverted/);
});
test('missing decoded metadata, residual mapping and dual-layer signaling cannot pass', () => {
    for (const frames of [[], [{}], [{side_data_list: []}]]) assert.throws(() => checkFrames(frames));
    const f = frame(); f.side_data_list[0].nlq_method_idc = 0;
    assert.throws(() => checkFrames([f]), /dual-layer mapping/);
    const c = config(); c[0].side_data_list[0].el_present_flag = 1;
    assert.throws(() => checkConfiguration(c), /el_present_flag/);
    c[0].side_data_list[0].el_present_flag = 0; c[0].side_data_list[0].dv_bl_signal_compatibility_id = 6;
    assert.throws(() => checkConfiguration(c), /compatibility/);
});
