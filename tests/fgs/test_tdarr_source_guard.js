'use strict';
const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const crypto = require('node:crypto');
const {run} = require('../../tools/fgs/tdarr_source_guard.js')._test;
const {identity} = require('../../tools/fgs/tdarr_video_bytes.js');

function fixture(t) {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'fgs-source-guard-'));
    t.after(() => fs.rmSync(root, {recursive: true, force: true}));
    const original = path.join(root, 'source.mkv'), output = path.join(root, 'candidate.mkv');
    const encoder = path.join(root, 'nvencc');
    fs.writeFileSync(original, 'original media'); fs.writeFileSync(output, 'candidate media');
    fs.writeFileSync(encoder, 'qualified encoder');
    const args = {originalLibraryFile: {_id: original}, inputFileObj: {_id: output},
        inputs: {phase: 'prepare', expectedEncoderSha256: crypto.createHash('sha256').update('qualified encoder').digest('hex')},
        variables: {user: {}}, jobLog: () => {}};
    function size() {
        args.variables.user.policySizeMeasurement = {accepted: true, maximum_ratio: .95,
            source: original, source_identity: identity(original), output_path: output,
            output_identity: identity(output)};
    }
    return {args, encoder, original, output, size};
}

test('qualified build and unchanged source pass preparation, size check and completion', async t => {
    const f = fixture(t);
    assert.equal((await run(f.args, f.encoder)).outputNumber, 1);
    // Tdarr serializes job variables between plugins.
    f.args.variables = JSON.parse(JSON.stringify(f.args.variables));
    f.size(); f.args.inputs.phase = 'check';
    const result = await run(f.args, f.encoder);
    assert.equal(result.outputNumber, 1);
    assert.equal(result.outputFileObj, f.args.inputFileObj);
    assert.equal(result.variables.user.sourceSavingsGuard.checked, true);
    assert.equal(fs.readFileSync(f.original, 'utf8'), 'original media');
    assert.equal((await run(f.args, f.encoder)).outputNumber, 2, 'A completion cannot be replayed');
});

test('wrong build, missing build, invalid configuration or absent preparation retain the source', async t => {
    for (const change of ['wrong-build', 'missing-build', 'bad-hash', 'bad-phase', 'no-preparation']) {
        const f = fixture(t);
        if (change === 'wrong-build') fs.writeFileSync(f.encoder, 'another encoder');
        if (change === 'missing-build') fs.unlinkSync(f.encoder);
        if (change === 'bad-hash') f.args.inputs.expectedEncoderSha256 = '';
        if (change === 'bad-phase') f.args.inputs.phase = 'typo';
        if (change === 'no-preparation') f.args.inputs.phase = 'check';
        const result = await run(f.args, f.encoder);
        assert.equal(result.outputNumber, 2, change);
        assert.equal(result.outputFileObj, f.args.originalLibraryFile);
        assert.equal(result.variables.user.sourceSavingsGuard.failed, true);
    }
});

test('source edits and replacement during an encode cannot use a later size measurement to pass', async t => {
    for (const change of ['append', 'same-size', 'replacement']) {
        const f = fixture(t);
        assert.equal((await run(f.args, f.encoder)).outputNumber, 1);
        if (change === 'append') fs.appendFileSync(f.original, ' extra');
        if (change === 'same-size') {
            fs.writeFileSync(f.original, 'modified media');
            fs.utimesSync(f.original, 1000, 1000);
        }
        if (change === 'replacement') {
            fs.renameSync(f.original, f.original + '.old');
            fs.writeFileSync(f.original, 'original media');
        }
        const afterChange = fs.readFileSync(f.original);
        f.size(); f.args.inputs.phase = 'check';
        assert.equal((await run(f.args, f.encoder)).outputNumber, 2, change);
        assert.deepEqual(fs.readFileSync(f.original), afterChange, 'Guard must not undo or replace external source changes');
    }
});

test('encoder, candidate, admission and job-state changes are rejected', async t => {
    for (const change of ['encoder', 'candidate', 'configured-build', 'source-path',
        'missing-size', 'rejected-size', 'relaxed-size', 'wrong-size-source', 'wrong-size-output', 'stale-size-identity']) {
        const f = fixture(t);
        assert.equal((await run(f.args, f.encoder)).outputNumber, 1);
        f.size(); f.args.inputs.phase = 'check';
        const size = f.args.variables.user.policySizeMeasurement;
        if (change === 'encoder') { fs.writeFileSync(f.encoder, 'qualified encoder'); fs.utimesSync(f.encoder, 1000, 1000); }
        if (change === 'candidate') fs.appendFileSync(f.output, ' extra');
        if (change === 'configured-build') f.args.inputs.expectedEncoderSha256 = 'f'.repeat(64);
        if (change === 'source-path') f.args.originalLibraryFile._id = f.output;
        if (change === 'missing-size') delete f.args.variables.user.policySizeMeasurement;
        if (change === 'rejected-size') size.accepted = false;
        if (change === 'relaxed-size') size.maximum_ratio = 1.2;
        if (change === 'wrong-size-source') size.source = f.output;
        if (change === 'wrong-size-output') size.output_path = f.original;
        if (change === 'stale-size-identity') size.source_identity = 'old';
        assert.equal((await run(f.args, f.encoder)).outputNumber, 2, change);
    }
});
