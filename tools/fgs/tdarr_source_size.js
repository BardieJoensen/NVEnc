'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const videoBytes = require('./tdarr_video_bytes.js');

function sizeRatio(outputBytes, originalVideoBytes, outputVideoBytes) {
    assert([outputBytes, originalVideoBytes, outputVideoBytes].every(n => Number.isSafeInteger(n) && n > 0)
        && outputVideoBytes <= outputBytes, 'Invalid video byte measurement');
    const baselineBytes = outputBytes - outputVideoBytes + originalVideoBytes;
    assert(Number.isSafeInteger(baselineBytes), 'Size baseline exceeds exact integer range');
    return {baselineBytes, outputBytes, originalVideoBytes, outputVideoBytes, ratio: outputBytes / baselineBytes};
}
async function plugin(args) {
    const original = args.originalLibraryFile._id, output = args.inputFileObj._id;
    assert.notEqual(original, output, 'Working output is the source');
    const max = Number(args.inputs.maxPercent || 95) / 100;
    assert([.95, 1.2].includes(max), 'Unsupported size threshold');
    const before = [videoBytes.identity(original), videoBytes.identity(output)];
    const started = Date.now();
    const [a, b] = await Promise.all([videoBytes.measure(original), videoBytes.measure(output)]);
    const measurement = sizeRatio(fs.statSync(output).size, a.bytes, b.bytes);
    assert(a.bytes <= fs.statSync(original).size, 'Source video exceeds source file bytes');
    assert.deepEqual([videoBytes.identity(original), videoBytes.identity(output)], before,
        'Media changed during size measurement');
    args.variables.user = args.variables.user || {};
    const accepted = measurement.ratio > .05 && measurement.ratio <= max;
    args.variables.user.policySizeMeasurement = {...measurement, accepted,
        source: original, source_identity: before[0], output_path: output, output_identity: before[1],
        maximum_ratio: max, seconds: (Date.now() - started) / 1000,
        source_mode: a.mode, output_mode: b.mode};
    args.jobLog(`[policy-size] ${(100 * measurement.ratio).toFixed(2)}% of retained-stream baseline; maximum ${100 * max}%: ${accepted ? 'accept' : 'retain source video'}`);
    return {outputFileObj: args.inputFileObj, outputNumber: accepted ? 1 : 2, variables: args.variables};
}
exports.details = () => ({name: 'Compare Savings With Identical Retained Audio',
    description: 'Count primary video bytes; audio pruning cannot mask video growth. Existing 95%/120% acceptance rules apply.',
    style: {borderColor: '#a8e6cf'}, tags: 'video', isStartPlugin: false, pType: '', requiresVersion: '2.11.01',
    sidebarPosition: -1, icon: 'faBalanceScale',
    inputs: [{label: 'Maximum output percent', name: 'maxPercent', type: 'string', defaultValue: '95', inputUI: {type: 'text'}}],
    outputs: [{number: 1, tooltip: 'Saving accepted'}, {number: 2, tooltip: 'Keep source video'}]});
exports.plugin = plugin;
exports._test = {sizeRatio};
