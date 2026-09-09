#!/usr/bin/env node
'use strict';

// Offline post-encode replay using an explicitly pinned Tdarr plugin snapshot.
// Run in an isolated container with original media and admitted video read-only.
// Only scratch outputs are created; replacement and notification plugins are absent.
const assert = require('node:assert/strict');
const cp = require('node:child_process');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

function sha(file) {
    return new Promise((resolve, reject) => {
        const hash = crypto.createHash('sha256');
        const stream = fs.createReadStream(file);
        stream.on('data', chunk => hash.update(chunk));
        stream.on('error', reject);
        stream.on('end', () => resolve(hash.digest('hex')));
    });
}

function identity(file) {
    const s = fs.statSync(file, {bigint: true});
    assert(s.isFile(), 'Expected a regular input file');
    return ['dev', 'ino', 'size', 'mtimeNs', 'ctimeNs'].map(k => String(s[k])).join(':');
}

function videoOnly(probe) {
    const streams = probe.streams || [];
    assert.equal(streams.length, 1, 'Admission must refer to a video-only file');
    assert.equal(streams[0].codec_type, 'video');
    assert.equal(streams[0].codec_name, 'av1');
    return streams[0];
}

function compareVideoPackets(reference, candidate, expectedFrames) {
    assert(Number.isSafeInteger(expectedFrames) && expectedFrames > 0, 'Invalid expected frame count');
    for (const value of [reference.hash, candidate.hash]) {
        assert(/^[a-f0-9]{64}$/.test(value || ''), 'Missing video payload hash');
    }
    assert.equal(reference.hash, candidate.hash, 'Final mux changed admitted video payload');
    const a = reference.timeline, b = candidate.timeline;
    assert.equal(a.count, expectedFrames, 'Incomplete admitted video timeline');
    assert.equal(b.count, expectedFrames, 'Incomplete final video timeline');
    assert.equal(a.missing, 0, 'Admitted video has missing timestamps');
    assert.equal(b.missing, 0, 'Final video has missing timestamps');
    assert.equal(a.timestamps.length, expectedFrames);
    assert.equal(b.timestamps.length, expectedFrames);
    const shift = b.timestamps[0] - a.timestamps[0];
    // A new Opus track can shift the Matroska origin by its decoder pre-skip.
    // Permit only a small common shift; the production validator additionally
    // verifies the source-relative alignment of every retained track.
    assert(Math.abs(shift) <= 0.010 + 1e-9, 'Excessive final video origin shift');
    for (let i = 0; i < expectedFrames; i++) {
        assert(Math.abs(b.timestamps[i] - a.timestamps[i] - shift) <= 0.001 + 1e-9,
            `Final mux changed video timestamp at frame ${i}`);
    }
    assert(Math.abs(b.duration - a.duration) <= 0.001 + 1e-9,
        'Final mux changed video duration');
    return {payload_sha256: reference.hash, frames: expectedFrames,
        common_timestamp_shift_seconds: shift, passed: true};
}

function fixturePlan(policy, source, streams, name, originalLanguage, policyConfig) {
    assert(/^[a-z]{3}$/.test(originalLanguage), 'Explicit fixture original language required');
    // buildPlan expects the node path, and translates Arr's host metadata path.
    // Passing the host path as both silently selects the preservation fallback.
    const metadata = [{path: source, app: 'offline-fixture', id: name,
        title: name, original_language: originalLanguage}];
    const plan = policy.buildPlan(policy.hostPathToNode(source), streams, metadata, policyConfig);
    assert.equal(plan.preserveAudio, false, `Fixture did not resolve audio policy: ${plan.reasons}`);
    assert.equal(plan.preserveSubtitles, false, 'Fixture did not resolve subtitle policy');
    assert.deepEqual(plan.originalLanguages, [originalLanguage]);
    return plan;
}

function checkStreamExpectations(probe, expected) {
    assert(expected && Array.isArray(expected.audio) && Array.isArray(expected.subtitles),
        'Explicit fixture track expectations required');
    const actual = {
        audio: probe.streams.filter(s => s.codec_type === 'audio').map(s => ({
            codec: s.codec_name, channels: s.channels, language: (s.tags || {}).language || 'und',
            default: Number((s.disposition || {}).default || 0)})),
        subtitles: probe.streams.filter(s => s.codec_type === 'subtitle').map(s => ({
            codec: s.codec_name, language: (s.tags || {}).language || 'und'})),
        chapters: (probe.chapters || []).length,
    };
    assert.deepEqual(actual, expected, 'Final tracks differ from independent fixture expectations');
    return {...actual, passed: true};
}

async function verifyPlugins(config) {
    assert.equal(await sha(config.plugin_snapshot), config.plugin_snapshot_sha256,
        'Plugin snapshot manifest changed');
    const snapshot = JSON.parse(fs.readFileSync(config.plugin_snapshot, 'utf8'));
    const root = path.resolve(config.plugins_root);
    const entries = Object.entries(snapshot.plugin_hashes);
    assert(entries.length > 0, 'Empty plugin snapshot');
    for (const [relative, expected] of entries) {
        const file = path.resolve(root, relative);
        assert(file.startsWith(root + path.sep), 'Plugin path outside snapshot');
        assert.equal(await sha(file), expected, `Plugin snapshot changed: ${relative}`);
    }
    assert.equal(await sha(config.audio_policy_config), config.audio_policy_sha256,
        'Audio policy configuration changed');
    return {snapshot_sha256: config.plugin_snapshot_sha256, files: entries.length,
        audio_policy_sha256: config.audio_policy_sha256, passed: true};
}

function checkReceipt(receipt, comparison, expectedBuild) {
    assert.equal(receipt.schema, 'fgs_trial_admission_v1');
    assert.equal(receipt.decision, 'stage_candidate', 'Candidate did not pass size admission');
    assert.equal(receipt.library_replacement, false);
    assert.equal(receipt.candidate_binary_sha256, expectedBuild);
    assert.equal(comparison.complete, true, 'Incomplete video comparison');
    assert(!comparison.error);
    assert.equal(comparison.candidate_sha256, expectedBuild);
    const cases = comparison.manifest.cases.filter(c => c.name === receipt.case);
    assert.equal(cases.length, 1);
    const rows = comparison.runs.filter(r => r.case === receipt.case && r.arm === 'new-auto-a');
    assert.equal(rows.length, 1);
    assert.equal(cases[0].source, receipt.source);
    assert.equal(cases[0].sha256, receipt.source_sha256);
    assert.equal(rows[0].sha256, receipt.staged_sha256);
    assert.equal(rows[0].bytes, receipt.candidate_bytes);
    assert.equal(rows[0].frames, cases[0].frames);
    assert(rows[0].bytes <= receipt.maximum_candidate_bytes, 'Candidate exceeds recorded budget');
    assert.equal(rows[0].scan.complete, true);
    assert.equal(rows[0].scan.verdict, 'stable');
    assert.equal(rows[0].scan.criterion, 'synthesis_texture_v1');
    assert.equal(rows[0].scan.errors, 0);
    assert.equal(rows[0].scan.packets, rows[0].frames);
    assert.deepEqual(Object.keys(rows[0].decoded_sha256).sort(), ['0', '1']);
    return {sourceCase: cases[0], candidate: rows[0]};
}

async function replay(configPath) {
    const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
    const directory = path.resolve(config.output_dir);
    const scratch = path.resolve(config.scratch_root);
    assert(directory.startsWith(scratch + path.sep), 'Output must be under the supplied scratch root');
    assert(!fs.existsSync(directory), 'Use a fresh output directory');
    fs.mkdirSync(directory, {recursive: true});
    const logPath = path.join(directory, 'pipeline.log');
    const log = text => fs.appendFileSync(logPath, String(text) + '\n');
    const reportPath = path.join(directory, 'report.json');
    const report = {complete: false, started_at: Date.now() / 1000, phases: [],
        config_path: path.resolve(configPath), config_sha256: await sha(configPath),
        harness_sha256: await sha(__filename), library_replacement: false,
        scope: 'Post-encode replay; video is reused only from completed size admission'};
    const save = () => {
        fs.writeFileSync(reportPath + '.tmp', JSON.stringify(report, null, 2) + '\n');
        fs.renameSync(reportPath + '.tmp', reportPath);
    };
    const phase = async (name, action) => {
        log('START ' + name);
        const start = Date.now();
        const value = await action();
        const seconds = (Date.now() - start) / 1000;
        report.phases.push({name, seconds}); save();
        log(`COMPLETE ${name}: ${seconds.toFixed(3)}s`);
        return value;
    };
    const probe = file => JSON.parse(cp.execFileSync('/usr/local/bin/ffprobe',
        ['-v', 'error', '-show_data_hash', 'sha256', '-show_streams', '-show_format',
            '-show_chapters', '-of', 'json', file], {maxBuffer: 64 * 1024**2, timeout: 120000}));
    const command = (exe, argv, name, allowed = [0]) => {
        const file = path.join(directory, name + '.log');
        const fd = fs.openSync(file, 'wx');
        try {
            const run = cp.spawnSync(exe, argv, {stdio: ['ignore', fd, fd], timeout: 5400000});
            assert(!run.error, `${name}: ${run.error && run.error.message}`);
            assert(allowed.includes(run.status), `${name} exited ${run.status}; inspect ${file}`);
            return {executable: exe, arguments: argv, log: file, returncode: run.status};
        } finally { fs.closeSync(fd); }
    };
    save();
    try {
        const receipt = JSON.parse(fs.readFileSync(config.admission, 'utf8'));
        const comparison = JSON.parse(fs.readFileSync(receipt.report, 'utf8'));
        const {sourceCase, candidate} = checkReceipt(receipt, comparison, config.expected_candidate_sha256);
        const source = receipt.source, video = receipt.staged_output;
        assert(!source.startsWith(scratch + path.sep) && !video.startsWith(directory + path.sep));
        const before = {[source]: identity(source), [video]: identity(video),
            [receipt.report]: identity(receipt.report), [config.admission]: identity(config.admission)};
        await phase('verify admitted source and video', async () => {
            const values = await Promise.all([sha(source), sha(video), sha(receipt.report)]);
            assert.deepEqual(values, [receipt.source_sha256, receipt.staged_sha256, receipt.report_sha256]);
            assert.equal(fs.statSync(video).size, receipt.candidate_bytes);
            for (const [file, signature] of Object.entries(before)) assert.equal(identity(file), signature);
        });
        report.admission = {path: config.admission, sha256: await sha(config.admission)};
        report.source = {path: source, sha256: receipt.source_sha256, identity: before[source]};
        report.admitted_video = {path: video, sha256: receipt.staged_sha256,
            bytes: candidate.bytes, frames: candidate.frames};
        const sourceProbe = probe(source), videoProbe = probe(video);
        const admittedStream = videoOnly(videoProbe);
        const sourceVideo = sourceProbe.streams.find(s => s.codec_type === 'video'
            && !(s.disposition || {}).attached_pic);
        assert(sourceVideo, 'Missing source video');
        const hdr = ['smpte2084', 'arib-std-b67'].includes(sourceVideo.color_transfer)
            || (sourceVideo.side_data_list || []).some(s => s.side_data_type === 'DOVI configuration record');
        if (hdr) {
            assert(config.hdr_comparison, 'HDR replay requires a completed source metadata comparison');
            const metadata = JSON.parse(fs.readFileSync(config.hdr_comparison, 'utf8'));
            assert.equal(metadata.passed, true);
            assert.equal(metadata.frames, candidate.frames);
            assert.equal(metadata.different_frames, 0);
            assert.deepEqual(metadata.stream_failures, []);
            assert.deepEqual(metadata.source_sha256, [receipt.source_sha256, receipt.staged_sha256]);
            report.hdr_comparison = {path: config.hdr_comparison, sha256: await sha(config.hdr_comparison)};
        }
        const plugins = path.resolve(config.plugins_root);
        report.plugin_snapshot = await phase('verify pinned production plugins', () => verifyPlugins(config));
        const requirePlugin = relative => require(path.join(plugins, 'FlowPlugins', relative, '1.0.0/index.js'));
        const policy = require(path.join(plugins,
            'FlowPlugins/LocalFlowPlugins/audio/resolveAudioPolicy/1.0.0/policy.js'));
        const policyConfig = JSON.parse(fs.readFileSync(config.audio_policy_config, 'utf8'));
        // The fixture's documented language substitutes only for the Arr lookup.
        // Selection and output generation use the actual frozen-policy plugins.
        const audioPlan = fixturePlan(policy, source, sourceProbe.streams, sourceCase.name,
            config.original_language, policyConfig);
        report.audio_policy = audioPlan;
        const mixed = path.join(directory, 'combined-input.mkv');
        report.initial_mux = await phase('combine admitted video with source tracks', () => command('mkvmerge',
            ['-o', mixed, '--disable-track-statistics-tags', '-A', '-S', '-M', '--no-chapters', video,
                '-D', '-M', '--no-chapters', '--no-global-tags', source], 'combine', [0, 1]));
        let working = mixed;
        const args = {originalLibraryFile: {_id: source, ffProbeData: sourceProbe},
            inputFileObj: {_id: working, ffProbeData: probe(working)}, inputs: {},
            variables: {user: {audioPolicy: audioPlan}}, workDir: path.join(directory, 'plugin-work'),
            deps: {fsextra: {ensureDirSync: p => fs.mkdirSync(p, {recursive: true})}},
            ffmpegPath: '/usr/local/bin/ffmpeg', jobLog: log, updateWorker: () => {},
            logOutcome: () => {}, logFullCliOutput: false};
        requirePlugin('CommunityFlowPlugins/ffmpegCommand/ffmpegCommandStart').plugin(args);
        // The active NVEncC path has already encoded the video at this point.
        // Cover/data removal precedes the same frozen audio/subtitle policy.
        for (const stream of args.variables.ffmpegCommand.streams) {
            if (stream.codec_type === 'data' || (stream.codec_type === 'video'
                && ['png', 'mjpeg', 'bmp', 'gif'].includes(stream.codec_name))) stream.removed = true;
        }
        requirePlugin('LocalFlowPlugins/audio/keepPrimaryAudioOnly').plugin(args);
        requirePlugin('LocalFlowPlugins/audio/applySubtitlePolicy').plugin(args);
        requirePlugin('LocalFlowPlugins/audio/addOpusCompatTrack').plugin(args);
        const execute = requirePlugin('CommunityFlowPlugins/ffmpegCommand/ffmpegCommandExecute');
        const applied = await phase('execute production stream policy and Opus', () => execute.plugin(args));
        working = applied.outputFileObj._id;
        args.inputFileObj = {_id: working, ffProbeData: probe(working)};
        const reattached = await phase('reattach authoritative source extras', () =>
            requirePlugin('LocalFlowPlugins/video/reattachAttachments').plugin(args));
        working = reattached.outputFileObj._id;
        args.inputFileObj = {_id: working, ffProbeData: probe(working)};
        report.stream_expectations = checkStreamExpectations(args.inputFileObj.ffProbeData,
            config.expected_streams);
        const validator = requirePlugin('LocalFlowPlugins/video/validateTranscodeOutput');
        const outputStream = validator._test.primaryVideoInfo(args.inputFileObj.ffProbeData).stream;
        assert(outputStream && outputStream.codec_name === 'av1');
        const proof = await phase('prove final video is the admitted encode', () => {
            const read = (file, index) => {
                const value = validator._test.probeTimelineAndHashes(file, [index], [index]);
                return {hash: value.hashes[String(index)], timeline: value.timelines[String(index)]};
            };
            const value = compareVideoPackets(read(video, admittedStream.index),
                read(working, outputStream.index), candidate.frames);
            for (const key of ['extradata_hash', 'width', 'height', 'pix_fmt', 'color_range',
                'color_space', 'color_transfer', 'color_primaries', 'sample_aspect_ratio']) {
                assert.deepEqual(outputStream[key], admittedStream[key], `Final mux changed video ${key}`);
            }
            return value;
        });
        report.video_copy_proof = proof;
        args.inputs = {maxPercent: hdr ? '120' : '95'};
        const sized = await phase('production source-relative size decision', () =>
            requirePlugin('LocalFlowPlugins/video/policySizeGate').plugin(args));
        report.production_size = args.variables.user.policySizeMeasurement;
        report.production_size.output_number = sized.outputNumber;
        assert.equal(sized.outputNumber, 1, 'Production size policy keeps the source');
        args.inputs = {expectAv1: 'true', auditVisualProvenance: 'true'};
        await phase('complete production final validator', () => validator.plugin(args));
        for (const [file, signature] of Object.entries(before)) assert.equal(identity(file), signature,
            'Evidence changed during final replay');
        report.output = {path: working, bytes: fs.statSync(working).size, sha256: await sha(working)};
        report.output_probe = args.inputFileObj.ffProbeData;
        report.complete = true;
        report.decision = 'ready_for_pilot_review';
        report.finished_at = Date.now() / 1000;
        save();
        process.stdout.write(JSON.stringify({complete: true, output: working,
            seconds: report.finished_at - report.started_at}) + '\n');
        return report;
    } catch (error) {
        report.error = String(error.message || error);
        report.decision = 'keep_source';
        report.failed_at = Date.now() / 1000;
        save();
        throw error;
    }
}

module.exports = {checkReceipt, checkStreamExpectations, compareVideoPackets, fixturePlan,
    identity, replay, verifyPlugins, videoOnly};
if (require.main === module) {
    assert.equal(process.argv.length, 3, 'usage: tdarr_trial_pipeline.js CONFIG.json');
    replay(process.argv[2]).catch(error => {
        process.stderr.write(String(error.message || error) + '\n');
        process.exitCode = 1;
    });
}
