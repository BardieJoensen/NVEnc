'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {_test: {SCHEMA, byteBudget, createPlugin, loadReference}} = require('../../tools/fgs/tdarr_size_budget.js');

function fixture() {
    const source = '/media/show.mkv', output = '/scratch/candidate.mkv';
    const loaded = {sha256: 'manifest-hash', manifest: {schema: SCHEMA,
        candidate_sha256: 'b'.repeat(64), maximum_extra_percent: '10', references: [{
            source_path: '/media/merged-storage/media/show.mkv', source_sha256: 'a'.repeat(64),
            source_bytes: 5000, frames: 24, qvbr: 30, baseline_video_bytes: 1000,
        }]}};
    const state = {sourceIdentity: 'source-unchanged', encoderIdentity: 'encoder-unchanged',
        outputIdentity: 'candidate-unchanged', sourceHash: 'a'.repeat(64), encoderHash: 'b'.repeat(64),
        bytes: 1100, packets: 24, measurements: 0, hashes: 0};
    const io = {loadReference: () => loaded,
        identity: file => file === source ? state.sourceIdentity
            : file === '/usr/bin/nvencc' ? state.encoderIdentity : state.outputIdentity,
        stat: () => ({size: 5000}), shaFile: async file => {
            state.hashes++; return file === source ? state.sourceHash : state.encoderHash;
        }, measureVideo: async () => {
            state.measurements++; return {bytes: state.bytes, packets: state.packets};
        }};
    const args = {originalLibraryFile: {_id: source}, inputFileObj: {_id: source},
        inputs: {phase: 'prepare', referenceManifest: '/evidence/reference.json'},
        variables: {user: {qvbr: 30}}, jobLog: () => {}};
    const plugin = createPlugin(io);
    const check = () => { args.inputs.phase = 'check'; args.inputFileObj = {_id: output}; return plugin(args); };
    return {args, check, io, loaded, plugin, state};
}

test('measured byte budget uses exact decimal arithmetic and floors fractional bytes', () => {
    assert.equal(byteBudget(101, '10'), 111);
    assert.equal(byteBudget(10001, '0.1'), 10011);
    assert.equal(byteBudget(1000, '0'), 1000);
    for (const value of ['-1', '101', 'NaN', 'Infinity', '1e1', '', '0.00001']) {
        assert.throws(() => byteBudget(1000, value));
    }
    assert.throws(() => byteBudget(Number.MAX_SAFE_INTEGER, '100'));
    assert.throws(() => byteBudget(0, '10'));
});

test('matched source/build prepares then accepts the exact video byte limit', async () => {
    const f = fixture();
    assert.equal((await f.plugin(f.args)).outputNumber, 1);
    assert.equal(f.state.measurements, 0);
    assert.equal(f.state.hashes, 2);
    const output = await f.check();
    assert.equal(output.outputNumber, 1);
    assert.equal(output.outputFileObj._id, '/scratch/candidate.mkv');
    assert.equal(output.variables.user.fidelityBudgetDecision.video_bytes, 1100);
});

test('early selection does no hashing and cannot substitute for preparation', async () => {
    const f = fixture(); f.args.inputs.phase = 'select';
    assert.equal((await f.plugin(f.args)).outputNumber, 1);
    assert.equal(f.state.hashes, 0);
    await assert.rejects(f.check(), /Missing preparation/);
    f.args.inputs.phase = 'select'; f.loaded.manifest.references[0].source_path = '/media/other.mkv';
    assert.equal((await f.plugin(f.args)).outputNumber, 2);
    assert.equal(f.state.hashes, 0);
});

test('one byte over budget returns the source, regardless of audio savings', async () => {
    const f = fixture(); await f.plugin(f.args); f.state.bytes = 1101;
    // A source-relative size gate may accept; it cannot override this cap.
    f.args.variables.user.policySizeMeasurement = {ratio: 0.10, outputBytes: 1200};
    const output = await f.check();
    assert.equal(output.outputNumber, 2);
    assert.equal(output.outputFileObj, f.args.originalLibraryFile);
    assert.equal(output.variables.user.fidelityBudgetDecision.decision, 'keep_source');
    assert.equal(f.args.variables.user.qvbr, 30);
});

test('unlisted sources skip encoding without hashing or inventing a baseline', async () => {
    const f = fixture(); f.loaded.manifest.references[0].source_path = '/media/other.mkv';
    const output = await f.plugin(f.args);
    assert.equal(output.outputNumber, 2);
    assert.equal(output.outputFileObj, f.args.originalLibraryFile);
    assert.equal(f.state.hashes, 0);
    assert.equal(f.state.measurements, 0);
    assert.equal(f.args.variables.user.fidelityBudget, undefined);
});

test('explicit copied-source aliases still require identical full source content', async () => {
    const f = fixture(), row = f.loaded.manifest.references[0];
    row.source_path = '/media/retained-source.mkv';
    row.source_aliases = [f.args.originalLibraryFile._id];
    assert.equal((await f.plugin(f.args)).outputNumber, 1);
    assert.equal((await f.check()).outputNumber, 1);
    f.args.inputs.phase = 'prepare'; f.state.sourceHash = 'c'.repeat(64);
    await assert.rejects(f.plugin(f.args), /Measured source content changed/);
});

test('manifest loader rejects ambiguous aliases and incomplete measured evidence', t => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'fgs-budget-test-'));
    t.after(() => fs.rmSync(dir, {recursive: true, force: true}));
    const file = path.join(dir, 'manifest.json'), f = fixture();
    const manifest = f.loaded.manifest, row = manifest.references[0];
    row.baseline_sha256 = 'c'.repeat(64); row.comparison_sha256 = 'd'.repeat(64);
    const load = () => { fs.writeFileSync(file, JSON.stringify(manifest)); return loadReference(file); };
    assert.equal(load().manifest.references.length, 1);
    row.source_aliases = ['/media/copied-source.mkv'];
    assert.equal(load().manifest.references[0].source_aliases.length, 1);
    row.source_aliases = ['/media/show.mkv'];
    assert.throws(load, /Ambiguous/);
    row.source_aliases = ['relative.mkv'];
    assert.throws(load, /Invalid source alias/);
    delete row.source_aliases; delete row.baseline_sha256;
    assert.throws(load, /Missing measured evidence/);
});

test('preparation rejects a different source, encoder or quality setting', async () => {
    for (const change of [f => f.state.sourceHash = 'c'.repeat(64),
        f => f.state.encoderHash = 'c'.repeat(64), f => f.args.variables.user.qvbr = 31]) {
        const f = fixture(); change(f); await assert.rejects(f.plugin(f.args));
        assert.equal(f.args.variables.user.fidelityBudget, undefined);
    }
});

test('final check rejects missing preparation, changed references and incomplete video', async () => {
    await assert.rejects(fixture().check(), /Missing preparation/);
    for (const change of [
        f => f.loaded.sha256 = 'changed', f => f.state.sourceIdentity = 'changed',
        f => f.state.encoderIdentity = 'changed', f => f.state.packets--,
        f => f.args.variables.user.fidelityBudget.maximum_video_bytes++,
        f => f.args.variables.user.qvbr++, f => f.state.bytes = NaN,
    ]) {
        const f = fixture(); await f.plugin(f.args); change(f); await assert.rejects(f.check());
    }
});

test('a source changing during final measurement cannot be promoted', async () => {
    const f = fixture(); await f.plugin(f.args);
    f.io.measureVideo = async () => {
        f.state.sourceIdentity = 'replaced during measurement'; return {bytes: 1000, packets: 24};
    };
    await assert.rejects(f.check(), /Source changed during byte measurement/);
});
