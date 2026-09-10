'use strict';
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const {identity} = require('./tdarr_video_bytes.js');

const SCHEMA = 'fgs_tdarr_source_guard_v1';
async function shaFile(file) {
    const hash = crypto.createHash('sha256');
    for await (const data of fs.createReadStream(file)) hash.update(data);
    return hash.digest('hex');
}

async function run(args, encoder = '/usr/bin/nvencc') {
    args.variables.user = args.variables.user || {};
    const user = args.variables.user, phase = args.inputs.phase;
    const original = args.originalLibraryFile._id;
    try {
        const expected = args.inputs.expectedEncoderSha256;
        assert(typeof expected === 'string' && /^[a-f0-9]{64}$/.test(expected),
            'A pinned encoder SHA-256 is required');
        if (phase === 'prepare') {
            // Do not reuse preparation from an earlier attempt. Read only the
            // small encoder binary; media is checked by filesystem identity.
            delete user.sourceSavingsGuard;
            const sourceIdentity = identity(original), encoderIdentity = identity(encoder);
            assert.equal(await shaFile(encoder), expected, 'Encoder differs from the qualified build');
            assert.equal(identity(original), sourceIdentity, 'Source changed during preparation');
            assert.equal(identity(encoder), encoderIdentity, 'Encoder changed during preparation');
            user.sourceSavingsGuard = {schema: SCHEMA, source: original, source_identity: sourceIdentity,
                encoder, encoder_identity: encoderIdentity, encoder_sha256: expected,
                prepared_at: new Date().toISOString(), checked: false};
        } else {
            assert.equal(phase, 'check', 'Unknown source guard phase');
            const held = user.sourceSavingsGuard;
            assert(held && held.schema === SCHEMA && held.checked === false,
                'A fresh source/build preparation is required');
            assert.equal(held.source, original, 'Preparation belongs to another source');
            assert.equal(held.encoder, encoder, 'Encoder path changed');
            assert.equal(held.encoder_sha256, expected, 'Configured encoder build changed');
            assert.equal(identity(original), held.source_identity, 'Source changed during the job');
            assert.equal(identity(encoder), held.encoder_identity, 'Encoder changed during the job');
            const size = user.policySizeMeasurement;
            assert(size && size.accepted === true && size.maximum_ratio === .95,
                'Strict source-relative savings must pass first');
            assert.equal(size.source, original, 'Savings belong to another source');
            assert.equal(size.source_identity, held.source_identity, 'Source changed before size measurement');
            assert.equal(size.output_path, args.inputFileObj._id, 'Candidate path changed');
            assert.notEqual(size.output_path, original, 'Candidate is the source');
            assert.equal(identity(size.output_path), size.output_identity, 'Candidate changed after size measurement');
            held.checked = true;
            held.checked_at = new Date().toISOString();
        }
        args.jobLog(`[source-guard] ${phase}: source identity and qualified encoder verified`);
        return {outputFileObj: args.inputFileObj, outputNumber: 1, variables: args.variables};
    } catch (error) {
        // A failed or partially completed attempt cannot leave a reusable pass.
        user.sourceSavingsGuard = {schema: SCHEMA, source: original, checked: false,
            failed: true, phase, reason: String(error.message || error)};
        args.jobLog(`[source-guard] Retain original: ${user.sourceSavingsGuard.reason}`);
        return {outputFileObj: args.originalLibraryFile, outputNumber: 2, variables: args.variables};
    }
}

exports.details = () => ({name: 'Verify Source and Qualified Encoder',
    description: 'Check source and encoder identity across the job without a full source hash pass. Changes retain the original.',
    style: {borderColor: '#a8e6cf'}, tags: 'video', isStartPlugin: false, pType: '', requiresVersion: '2.11.01',
    sidebarPosition: -1, icon: 'faCheck',
    inputs: [{label: 'Phase', name: 'phase', type: 'string', defaultValue: 'prepare',
        inputUI: {type: 'dropdown', options: ['prepare', 'check']}},
    {label: 'Qualified encoder SHA-256', name: 'expectedEncoderSha256', type: 'string', defaultValue: '',
        inputUI: {type: 'text'}}],
    outputs: [{number: 1, tooltip: 'Source and encoder verified'}, {number: 2, tooltip: 'Retain original'}]});
exports.plugin = args => run(args);
exports._test = {run};
