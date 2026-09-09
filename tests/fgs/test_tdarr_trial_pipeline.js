'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {checkReceipt, checkStreamExpectations, compareVideoPackets, fixturePlan, replay, verifyPlugins, videoOnly}
    = require('./tdarr_trial_pipeline.js');

function packetProof() {
    return {hash: 'a'.repeat(64), timeline: {count: 3, missing: 0,
        timestamps: [0, 0.042, 0.083], duration: 0.125}};
}

test('final remux accepts only a small common origin shift with identical video payload', () => {
    const a = packetProof(), b = structuredClone(a);
    b.timeline.timestamps = b.timeline.timestamps.map(t => t + 0.007);
    assert.equal(compareVideoPackets(a, b, 3).passed, true);
    b.hash = 'b'.repeat(64);
    assert.throws(() => compareVideoPackets(a, b, 3), /payload/);
});

test('missing frames, uneven timing, excessive shifts and changed duration are rejected', () => {
    for (const edit of [
        b => b.timeline.count--,
        b => b.timeline.missing++,
        b => b.timeline.timestamps.pop(),
        b => b.timeline.timestamps[1] += 0.020,
        b => { b.timeline.timestamps = b.timeline.timestamps.map(t => t + 0.250); },
        b => b.timeline.duration += 0.050,
        b => { delete b.hash; },
        b => b.timeline.timestamps[1] = NaN,
    ]) {
        const a = packetProof(), b = structuredClone(a); edit(b);
        assert.throws(() => compareVideoPackets(a, b, 3));
    }
});

test('fixture metadata uses the node path and cannot silently enter preservation mode', () => {
    const policy = {
        hostPathToNode: p => p.replace('/host/', '/node/'),
        buildPlan: (file, streams, metadata) => {
            const matched = file === '/node/source.mkv' && metadata[0].path === '/host/source.mkv';
            return {preserveAudio: !matched, preserveSubtitles: !matched,
                originalLanguages: matched ? ['eng'] : [], reasons: ['unresolved fixture']};
        },
    };
    assert.equal(fixturePlan(policy, '/host/source.mkv', [], 'fixture', 'eng', {}).preserveAudio, false);
    assert.throws(() => fixturePlan({...policy, hostPathToNode: p => p},
        '/host/source.mkv', [], 'fixture', 'eng', {}), /did not resolve/);
});

test('explicit track expectations catch missing Opus, wrong defaults and missing subtitle filtering', () => {
    const probe = {streams: [
        {codec_type: 'audio', codec_name: 'opus', channels: 2, tags: {language: 'eng'}, disposition: {default: 1}},
        {codec_type: 'audio', codec_name: 'eac3', channels: 6, tags: {language: 'eng'}, disposition: {default: 0}},
        {codec_type: 'subtitle', codec_name: 'subrip', tags: {language: 'dan'}},
    ], chapters: [{}, {}]};
    const expected = {audio: [{codec: 'opus', channels: 2, language: 'eng', default: 1},
        {codec: 'eac3', channels: 6, language: 'eng', default: 0}],
    subtitles: [{codec: 'subrip', language: 'dan'}], chapters: 2};
    assert.equal(checkStreamExpectations(probe, expected).passed, true);
    for (const change of [
        p => p.streams.shift(),
        p => p.streams[1].disposition.default = 1,
        p => p.streams.push({codec_type: 'subtitle', codec_name: 'subrip', tags: {language: 'fra'}}),
        p => p.chapters.pop(),
    ]) {
        const wrong = structuredClone(probe); change(wrong);
        assert.throws(() => checkStreamExpectations(wrong, expected), /fixture expectations/);
    }
});

test('admitted video may carry Dolby Vision metadata but cannot conceal extra tracks', () => {
    const v = {codec_type: 'video', codec_name: 'av1', side_data_list: [{}]};
    assert.equal(videoOnly({streams: [v]}), v);
    assert.throws(() => videoOnly({streams: [v, {codec_type: 'audio'}]}));
    assert.throws(() => videoOnly({streams: [{...v, codec_name: 'hevc'}]}));
});

function receiptPair() {
    const receipt = {schema: 'fgs_trial_admission_v1', decision: 'stage_candidate',
        library_replacement: false, candidate_binary_sha256: 'c'.repeat(64), case: 'fixture',
        source: '/source.mkv', source_sha256: 's'.repeat(64), staged_sha256: 'o'.repeat(64),
        candidate_bytes: 1100, maximum_candidate_bytes: 1100};
    const comparison = {complete: true, candidate_sha256: receipt.candidate_binary_sha256,
        manifest: {cases: [{name: receipt.case, source: receipt.source,
            sha256: receipt.source_sha256, frames: 3}]}, runs: [{case: receipt.case,
            arm: 'new-auto-a', sha256: receipt.staged_sha256, bytes: 1100, frames: 3,
            scan: {complete: true, verdict: 'stable', criterion: 'synthesis_texture_v1',
                errors: 0, packets: 3}, decoded_sha256: {'0': 'base', '1': 'rendered'}}]};
    return {receipt, comparison};
}

test('receipt must bind the exact source, build, output and completed comparison', () => {
    const {receipt, comparison} = receiptPair();
    assert.equal(checkReceipt(receipt, comparison, 'c'.repeat(64)).candidate.bytes, 1100);
    for (const change of [
        p => p.receipt.decision = 'keep_source',
        p => p.receipt.maximum_candidate_bytes = 1099,
        p => p.receipt.source = '/different.mkv',
        p => p.comparison.complete = false,
        p => p.comparison.candidate_sha256 = 'b'.repeat(64),
        p => p.comparison.runs[0].sha256 = 'changed',
        p => p.comparison.runs[0].scan.errors++,
        p => { delete p.comparison.runs[0].decoded_sha256['0']; },
        p => p.comparison.runs.push(structuredClone(p.comparison.runs[0])),
    ]) {
        const pair = receiptPair(); change(pair);
        assert.throws(() => checkReceipt(pair.receipt, pair.comparison, 'c'.repeat(64)));
    }
});

test('plugin and policy drift is rejected before replay', async t => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'fgs-plugin-snapshot-'));
    t.after(() => fs.rmSync(root, {recursive: true, force: true}));
    const write = (name, value) => {
        fs.writeFileSync(path.join(root, name), value);
        return crypto.createHash('sha256').update(value).digest('hex');
    };
    const pluginHash = write('plugin.js', 'original plugin');
    const policyHash = write('audio.json', '{}');
    const manifestHash = write('snapshot.json', JSON.stringify({plugin_hashes: {'plugin.js': pluginHash}}));
    const config = {plugins_root: root, plugin_snapshot: path.join(root, 'snapshot.json'),
        plugin_snapshot_sha256: manifestHash, audio_policy_config: path.join(root, 'audio.json'),
        audio_policy_sha256: policyHash};
    assert.equal((await verifyPlugins(config)).passed, true);
    write('plugin.js', 'changed plugin');
    await assert.rejects(verifyPlugins(config), /Plugin snapshot changed/);
    write('plugin.js', 'original plugin');
    write('audio.json', '{"preferredLanguages":[]}');
    await assert.rejects(verifyPlugins(config), /Audio policy configuration changed/);
    write('audio.json', '{}');
    write('snapshot.json', '{}');
    await assert.rejects(verifyPlugins(config), /manifest changed/);
});

test('replay stops on a keep-source decision without producing media or changing the source', async t => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'fgs-replay-rejection-'));
    t.after(() => fs.rmSync(root, {recursive: true, force: true}));
    const {receipt, comparison} = receiptPair();
    const source = path.join(root, 'source.mkv');
    fs.writeFileSync(source, 'unchanged original');
    Object.assign(receipt, {decision: 'keep_source', source, report: path.join(root, 'comparison.json')});
    fs.writeFileSync(receipt.report, JSON.stringify(comparison));
    const admission = path.join(root, 'decision.json');
    fs.writeFileSync(admission, JSON.stringify(receipt));
    const output = path.join(root, 'output');
    const config = path.join(root, 'config.json');
    fs.writeFileSync(config, JSON.stringify({admission, expected_candidate_sha256: 'c'.repeat(64),
        scratch_root: root, output_dir: output}));
    await assert.rejects(replay(config), /did not pass size admission/);
    const result = JSON.parse(fs.readFileSync(path.join(output, 'report.json')));
    assert.equal(result.complete, false);
    assert.equal(result.decision, 'keep_source');
    assert.equal(result.library_replacement, false);
    assert.deepEqual(fs.readdirSync(output), ['report.json']);
    assert.equal(fs.readFileSync(source, 'utf8'), 'unchanged original');
});
