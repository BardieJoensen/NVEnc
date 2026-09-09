'use strict';

// Tdarr LocalFlowPlugin: prepare before encoding, check after the final mux.
// The reference is a complete measured encode of the same source. This plugin
// never estimates that size from samples or changes the encoder's quality.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const videoBytes = require('./tdarr_video_bytes.js');

const SCHEMA = 'fgs_tdarr_budget_reference_v1';
const hashText = value => crypto.createHash('sha256').update(value).digest('hex');
const validHash = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const nodePath = value => value.replace(/^\/media\/merged-storage\/media\//, '/media/');
const sourcePaths = row => [row.source_path, ...(row.source_aliases || [])].map(nodePath);
function identity(file) {
    const stat = fs.statSync(file, {bigint: true});
    assert(stat.isFile(), 'Expected regular media or encoder file');
    return ['dev', 'ino', 'size', 'mtimeNs', 'ctimeNs'].map(k => String(stat[k])).join(':');
}
function shaFile(file) {
    return new Promise((resolve, reject) => {
        const hash = crypto.createHash('sha256'), input = fs.createReadStream(file);
        input.on('data', data => hash.update(data));
        input.on('end', () => resolve(hash.digest('hex')));
        input.on('error', reject);
    });
}
function byteBudget(bytes, percent) {
    assert(Number.isSafeInteger(bytes) && bytes > 0, 'Invalid measured video bytes');
    assert(typeof percent === 'string' && /^\d+(?:\.\d{1,4})?$/.test(percent), 'Invalid extra percent');
    const parts = percent.split('.'), scale = 10n ** BigInt((parts[1] || '').length);
    const extra = BigInt(parts.join(''));
    assert(extra <= 100n * scale, 'Extra percent must be in 0..100');
    const limit = BigInt(bytes) * (100n * scale + extra) / (100n * scale);
    assert(limit <= BigInt(Number.MAX_SAFE_INTEGER), 'Video budget exceeds exact integer range');
    return Number(limit);
}
function loadReference(file) {
    const raw = fs.readFileSync(file), manifest = JSON.parse(raw);
    assert.equal(manifest.schema, SCHEMA, 'Unsupported reference schema');
    assert(validHash(manifest.candidate_sha256), 'Missing candidate build identity');
    assert(Array.isArray(manifest.references) && manifest.references.length > 0, 'Empty measured reference');
    const paths = new Set();
    for (const row of manifest.references) {
        assert(typeof row.source_path === 'string' && row.source_path.startsWith('/'), 'Invalid source path');
        assert(row.source_aliases === undefined || Array.isArray(row.source_aliases), 'Invalid source aliases');
        for (const name of [row.source_path, ...(row.source_aliases || [])]) {
            assert(typeof name === 'string' && name.startsWith('/'), 'Invalid source alias');
            assert(!paths.has(nodePath(name)), 'Ambiguous measured source');
            paths.add(nodePath(name));
        }
        assert(validHash(row.source_sha256) && validHash(row.baseline_sha256)
            && validHash(row.comparison_sha256), 'Missing measured evidence identity');
        assert(Number.isSafeInteger(row.source_bytes) && row.source_bytes > 0, 'Invalid source bytes');
        assert(Number.isSafeInteger(row.frames) && row.frames > 0, 'Invalid measured frame count');
        assert(Number.isFinite(row.qvbr) && row.qvbr >= 0 && row.qvbr <= 51, 'Invalid measured QVBR');
        byteBudget(row.baseline_video_bytes, manifest.maximum_extra_percent);
    }
    return {manifest, sha256: hashText(raw)};
}
function measureVideo(file) {
    const info = videoBytes.inspect(file);
    assert.equal(info.video.codec_name, 'av1', 'Budget applies to an AV1 output');
    return videoBytes.measure(file, info);
}

exports.details = () => ({name: 'Measured Fidelity Trial Budget',
    description: 'Require a matching complete baseline before encoding, then enforce its video byte budget. Rejection keeps the source.',
    style: {borderColor: '#a8e6cf'}, tags: 'video', isStartPlugin: false, pType: '',
    requiresVersion: '2.11.01', sidebarPosition: -1, icon: 'faBalanceScale',
    inputs: [
        {label: 'Phase', name: 'phase', type: 'string', defaultValue: 'prepare', inputUI: {type: 'dropdown', options: ['select', 'prepare', 'check']}},
        {label: 'Measured reference manifest', name: 'referenceManifest', type: 'string', defaultValue: '', inputUI: {type: 'text'}},
    ], outputs: [{number: 1, tooltip: 'Measured trial accepted'}, {number: 2, tooltip: 'Keep source; no candidate promotion'}],
});

function createPlugin(io = {identity, shaFile, loadReference, measureVideo, stat: fs.statSync}) {
    return async args => {
        args.variables = args.variables || {};
        args.variables.user = args.variables.user || {};
        const user = args.variables.user, source = args.originalLibraryFile._id;
        const result = (accepted, decision) => {
            user.fidelityBudgetDecision = decision;
            args.jobLog(`[fidelity-budget] ${decision.reason}`);
            return {outputFileObj: accepted ? args.inputFileObj : args.originalLibraryFile,
                outputNumber: accepted ? 1 : 2, variables: args.variables};
        };
        const loaded = io.loadReference(args.inputs.referenceManifest);
        // Explicit aliases let an identical copied/imported source reuse a
        // measured baseline. Every alias still needs the complete source hash;
        // title similarity, size alone and automatic library searches never match.
        const reference = loaded.manifest.references.find(row => sourcePaths(row).includes(nodePath(source)));
        if (args.inputs.phase === 'select') {
            delete user.fidelityBudget;
            return result(Boolean(reference), {decision: reference ? 'selected' : 'keep_source',
                reason: reference ? 'Listed measured trial source; preparation is still required'
                    : 'No complete matching baseline; candidate flow skipped'});
        }
        if (args.inputs.phase === 'prepare') {
            delete user.fidelityBudget;
            if (!reference) return result(false, {decision: 'keep_source', reason: 'No complete matching baseline; candidate encoding skipped'});
            assert.equal(Number(user.qvbr), reference.qvbr, 'Quality setting differs from measured baseline');
            assert.equal(io.stat(source).size, reference.source_bytes, 'Measured source size changed');
            const before = io.identity(source), encoder = '/usr/bin/nvencc', encoderBefore = io.identity(encoder);
            const [sourceHash, encoderHash] = await Promise.all([io.shaFile(source), io.shaFile(encoder)]);
            assert.equal(sourceHash, reference.source_sha256, 'Measured source content changed');
            assert.equal(encoderHash, loaded.manifest.candidate_sha256, 'Unexpected candidate encoder');
            assert.equal(io.identity(source), before, 'Source changed during preparation');
            assert.equal(io.identity(encoder), encoderBefore, 'Encoder changed during preparation');
            user.fidelityBudget = {schema: SCHEMA, source, source_identity: before,
                encoder_identity: encoderBefore, reference_sha256: loaded.sha256,
                frames: reference.frames, baseline_video_bytes: reference.baseline_video_bytes,
                maximum_video_bytes: byteBudget(reference.baseline_video_bytes, loaded.manifest.maximum_extra_percent)};
            return result(true, {decision: 'prepared', reason: 'Source and candidate match the measured trial; final byte check required'});
        }
        assert.equal(args.inputs.phase, 'check', 'Unknown measured budget phase');
        const prepared = user.fidelityBudget;
        assert(prepared && prepared.schema === SCHEMA && prepared.source === source, 'Missing preparation for this source');
        assert.equal(prepared.reference_sha256, loaded.sha256, 'Measured reference changed during encoding');
        assert(reference, 'Measured source is absent from the reference');
        assert.equal(Number(user.qvbr), reference.qvbr, 'Quality setting changed during encoding');
        assert.equal(prepared.frames, reference.frames, 'Prepared frame count changed');
        assert.equal(prepared.baseline_video_bytes, reference.baseline_video_bytes, 'Prepared baseline changed');
        assert.equal(prepared.maximum_video_bytes,
            byteBudget(reference.baseline_video_bytes, loaded.manifest.maximum_extra_percent), 'Prepared budget changed');
        assert.equal(io.identity(source), prepared.source_identity, 'Source changed during encoding');
        assert.equal(io.identity('/usr/bin/nvencc'), prepared.encoder_identity, 'Encoder changed during encoding');
        const output = args.inputFileObj._id;
        assert.notEqual(output, source, 'Expected a fresh candidate output');
        const before = io.identity(output), started = Date.now();
        const measured = await io.measureVideo(output);
        assert.equal(io.identity(output), before, 'Candidate changed during byte measurement');
        assert.equal(io.identity(source), prepared.source_identity, 'Source changed during byte measurement');
        assert.equal(io.identity('/usr/bin/nvencc'), prepared.encoder_identity, 'Encoder changed during byte measurement');
        assert(Number.isSafeInteger(measured.bytes) && measured.bytes > 0, 'Invalid candidate video bytes');
        assert.equal(measured.packets, prepared.frames, 'Candidate frame count differs from measured baseline');
        const accepted = measured.bytes <= prepared.maximum_video_bytes;
        return result(accepted, {decision: accepted ? 'within_budget' : 'keep_source',
            reason: accepted ? 'Candidate video is within the complete measured baseline budget'
                : 'Candidate video exceeds the complete measured baseline budget; source retained',
            output_path: output, output_identity: before, video_bytes: measured.bytes,
            baseline_video_bytes: prepared.baseline_video_bytes, maximum_video_bytes: prepared.maximum_video_bytes,
            measurement_seconds: (Date.now() - started) / 1000});
    };
}

exports.plugin = createPlugin();
exports._test = {SCHEMA, byteBudget, createPlugin, identity, loadReference, measureVideo, shaFile};
