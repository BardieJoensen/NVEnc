'use strict';
const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const crypto = require('node:crypto');
const {plugin} = require('../../tools/fgs/tdarr_stage_review.js');
const {identity} = require('../../tools/fgs/tdarr_video_bytes.js');

function fixture(t) {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'fgs-stage-'));
    t.after(() => fs.rmSync(root, {recursive: true, force: true}));
    const original = path.join(root, 'source.mkv'), output = path.join(root, 'output.mkv');
    fs.writeFileSync(original, 'original input bytes'); fs.writeFileSync(output, 'accepted candidate bytes');
    return {originalLibraryFile: {_id: original}, inputFileObj: {_id: output},
        inputs: {outputDirectory: path.join(root, 'review')}, jobLog: () => {},
        variables: {user: {videoAlreadyEncoded: '1', fidelityDoviCheck: {passed: true},
            fidelityBudget: {source_identity: identity(original), reference_sha256: 'a'.repeat(64)},
            fidelityBudgetDecision: {decision: 'within_budget', output_path: output, output_identity: identity(output)}}}};
}
test('accepted review output survives cache removal while Tdarr ends on the original', async t => {
    const args = fixture(t), result = await plugin(args), receipt = result.variables.user.fidelityReviewArtifact;
    assert.equal(result.outputFileObj, args.originalLibraryFile);
    assert.equal(result.variables.user.fidelityTrialAccepted, true);
    assert.equal(fs.readFileSync(args.originalLibraryFile._id, 'utf8'), 'original input bytes');
    fs.unlinkSync(args.inputFileObj._id);
    assert.equal(fs.readFileSync(receipt.candidate, 'utf8'), 'accepted candidate bytes');
    assert.equal(receipt.candidate_sha256, crypto.createHash('sha256').update('accepted candidate bytes').digest('hex'));
    assert.equal(receipt.library_replacement, false);
    assert.equal(receipt.copy_verified, true);
    assert.deepEqual(JSON.parse(fs.readFileSync(path.join(path.dirname(receipt.candidate), 'receipt.json'))), receipt);
});
test('independent accepted runs never overwrite earlier review artifacts', async t => {
    const args = fixture(t), first = (await plugin(args)).variables.user.fidelityReviewArtifact.candidate;
    const second = (await plugin(args)).variables.user.fidelityReviewArtifact.candidate;
    assert.notEqual(first, second);
    assert.equal(fs.readFileSync(first, 'utf8'), 'accepted candidate bytes');
});
test('rejected or changed media cannot be staged as an accepted candidate', async t => {
    for (const change of ['budget', 'candidate', 'source']) {
        const args = fixture(t);
        if (change === 'budget') args.variables.user.fidelityBudgetDecision.decision = 'keep_source';
        else fs.appendFileSync(change === 'source' ? args.originalLibraryFile._id : args.inputFileObj._id, 'changed');
        await assert.rejects(plugin(args));
        assert(!fs.existsSync(args.inputs.outputDirectory));
    }
});
test('ordinary review records source-relative savings without claiming an old-encoder budget', async t => {
    const args = fixture(t), user = args.variables.user;
    args.inputs.acceptancePolicy = 'source-size';
    delete user.fidelityBudget;
    delete user.fidelityBudgetDecision;
    user.policySizeMeasurement = {accepted: true, source: args.originalLibraryFile._id,
        source_identity: identity(args.originalLibraryFile._id), output_path: args.inputFileObj._id,
        output_identity: identity(args.inputFileObj._id), ratio: .8, maximum_ratio: .95};
    const receipt = (await plugin(args)).variables.user.fidelityReviewArtifact;
    assert.equal(receipt.acceptance_policy, 'source-size');
    assert.equal(receipt.video_budget.decision, 'within_source_size_policy');
    assert.equal(receipt.reference_sha256, undefined);
    for (const change of [{accepted: false}, {ratio: 1.3}, {source: '/another-source'}, {output_identity: 'changed'}]) {
        const altered = structuredClone({...args, jobLog: undefined});
        altered.jobLog = () => {};
        Object.assign(altered.variables.user.policySizeMeasurement, change);
        await assert.rejects(plugin(altered));
    }
});
