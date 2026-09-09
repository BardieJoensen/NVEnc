'use strict';
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {identity} = require('./tdarr_video_bytes.js');

function shaFile(file) {
    return new Promise((resolve, reject) => {
        const hash = crypto.createHash('sha256'), input = fs.createReadStream(file);
        input.on('data', data => hash.update(data));
        input.on('end', () => resolve(hash.digest('hex')));
        input.on('error', reject);
    });
}
async function plugin(args) {
    const user = args.variables.user, original = args.originalLibraryFile._id, candidate = args.inputFileObj._id;
    const policy = args.inputs.acceptancePolicy || 'measured';
    assert(['measured', 'source-size'].includes(policy), 'Unknown review acceptance policy');
    let sourceIdentity, decision, referenceHash;
    if (policy === 'measured') {
        assert.equal(user.fidelityBudgetDecision.decision, 'within_budget');
        sourceIdentity = user.fidelityBudget.source_identity;
        decision = user.fidelityBudgetDecision;
        referenceHash = user.fidelityBudget.reference_sha256;
    } else {
        const size = user.policySizeMeasurement;
        assert.equal(size.accepted, true, 'Source-relative saving was not accepted');
        assert.equal(size.source, original, 'Saving belongs to another source');
        assert([.95, 1.2].includes(size.maximum_ratio) && size.ratio > .05
            && size.ratio <= size.maximum_ratio, 'Invalid source-relative admission');
        sourceIdentity = size.source_identity;
        decision = {...size, decision: 'within_source_size_policy',
            scope: 'Existing source-relative savings; no old-encoder size promise'};
    }
    assert.equal(String(user.videoAlreadyEncoded), '1');
    assert.equal(user.fidelityDoviCheck.passed, true);
    assert.notEqual(candidate, original);
    assert.equal(identity(original), sourceIdentity, 'Source changed before review staging');
    assert.equal(candidate, decision.output_path, 'Final candidate path changed');
    const before = identity(candidate);
    assert.equal(before, decision.output_identity, 'Final candidate changed after its size check');
    const root = path.resolve(String(args.inputs.outputDirectory || '/fgs-review'));
    // Deployment supplies a dedicated review volume outside the transcode cache
    // and media libraries. Each job gets a new directory; nothing is overwritten.
    assert(root !== path.dirname(original) && root !== path.dirname(candidate), 'Review folder must be separate from source and cache');
    await fs.promises.mkdir(root, {recursive: true});
    const directory = await fs.promises.mkdtemp(path.join(root, 'candidate-'));
    const staged = path.join(directory, 'candidate.mkv');
    await fs.promises.copyFile(candidate, staged, fs.constants.COPYFILE_EXCL);
    const stagedBefore = identity(staged);
    const [expectedHash, hash] = await Promise.all([shaFile(candidate), shaFile(staged)]);
    assert.equal(hash, expectedHash, 'Review copy differs from the accepted candidate');
    assert.equal(identity(staged), stagedBefore, 'Staged file changed while hashing');
    assert.equal(identity(candidate), before, 'Candidate changed during review staging');
    assert.equal(identity(original), sourceIdentity, 'Source changed during review staging');
    assert.equal(fs.statSync(staged).size, fs.statSync(candidate).size, 'Incomplete review copy');
    const receipt = {schema: 'fgs_tdarr_review_v1', source: original,
        source_identity: sourceIdentity, acceptance_policy: policy,
        candidate: staged, candidate_sha256: hash, candidate_bytes: fs.statSync(staged).size,
        reference_sha256: referenceHash,
        video_budget: decision, dovi_check: user.fidelityDoviCheck,
        acceptance: 'Reached review terminal after successful final validator; source retained',
        copy_verified: true, library_replacement: false};
    await fs.promises.writeFile(path.join(directory, 'receipt.json'), JSON.stringify(receipt, null, 2) + '\n', {flag: 'wx'});
    user.fidelityTrialAccepted = true;
    user.fidelityReviewArtifact = receipt;
    args.jobLog('[fidelity-pilot] Candidate staged for review: ' + staged + '; original retained');
    // Tdarr forbids ending a flow with its working file still in transcode
    // cache. The independent review artifact persists after normal cache cleanup.
    return {outputFileObj: args.originalLibraryFile, outputNumber: 1, variables: args.variables};
}
exports.details = () => ({name: 'Stage Fidelity Candidate for Review',
    description: 'Save a verified candidate and receipt outside the transcode cache, then retain the original library file.',
    style: {borderColor: '#a8e6cf'}, tags: 'video', isStartPlugin: false, pType: '', requiresVersion: '2.11.01',
    sidebarPosition: -1, icon: 'faCheck',
    inputs: [{label: 'Dedicated review directory', name: 'outputDirectory', type: 'string', defaultValue: '/fgs-review', inputUI: {type: 'text'}},
        {label: 'Acceptance policy', name: 'acceptancePolicy', type: 'string', defaultValue: 'measured',
            inputUI: {type: 'dropdown', options: ['measured', 'source-size']}}],
    outputs: [{number: 1, tooltip: 'Candidate saved for review; original retained'}]});
exports.plugin = plugin;
