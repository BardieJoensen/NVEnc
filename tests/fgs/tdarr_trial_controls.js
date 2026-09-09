#!/usr/bin/env node
'use strict';

// Small, real-container controls for the offline post-encode replay.
// Uses the same isolated runtime and read-only input mounts as the replay.
const assert = require('node:assert/strict');
const cp = require('node:child_process');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {compareVideoPackets, identity, verifyPlugins} = require('./tdarr_trial_pipeline.js');

async function main(configPath, directory, fontPath) {
    const config = JSON.parse(fs.readFileSync(configPath));
    directory = path.resolve(directory);
    assert(directory.startsWith(path.resolve(config.scratch_root) + path.sep));
    fs.mkdirSync(directory, {recursive: false});
    const report = {complete: false, library_replacement: false, commands: [], checks: []};
    const save = () => fs.writeFileSync(path.join(directory, 'report.json'), JSON.stringify(report, null, 2) + '\n');
    const run = (exe, argv, allowed = [0]) => {
        const result = cp.spawnSync(exe, argv, {encoding: 'utf8', timeout: 120000, maxBuffer: 16 * 1024**2});
        report.commands.push({executable: exe, arguments: argv, returncode: result.status,
            stdout: result.stdout, stderr: result.stderr}); save();
        assert(!result.error, String(result.error));
        assert(allowed.includes(result.status), `${exe} exited ${result.status}`);
        return result.stdout;
    };
    try {
        report.snapshot = await verifyPlugins(config);
        const receipt = JSON.parse(fs.readFileSync(config.admission));
        const baseline = path.join(path.dirname(receipt.report), receipt.case, 'old-default-a/output.mkv');
        const inputs = [receipt.staged_output, baseline, fontPath];
        const before = inputs.map(identity);
        const clip = path.join(directory, 'admitted-clip.mkv');
        run('/usr/local/bin/ffmpeg', ['-v', 'error', '-nostdin', '-n', '-i', receipt.staged_output,
            '-map', '0:v:0', '-frames:v', '72', '-c:v', 'copy', '-map_chapters', '-1', clip]);
        const validator = require(path.join(config.plugins_root,
            'FlowPlugins/LocalFlowPlugins/video/validateTranscodeOutput/1.0.0/index.js'));
        const proof = file => {
            const value = validator._test.probeTimelineAndHashes(file, [0], [0]);
            return {hash: value.hashes['0'], timeline: value.timelines['0']};
        };
        const reference = proof(clip), frames = reference.timeline.count;
        for (const [name, delay, accepted] of [['small-origin-shift', 7, true], ['bad-origin-shift', 250, false]]) {
            const target = path.join(directory, name + '.mkv');
            run('mkvmerge', ['-o', target, '--sync', '0:' + delay, clip], [0, 1]);
            const shifted = proof(target);
            assert.equal(shifted.hash, reference.hash, 'Timing control must retain video payload');
            if (accepted) compareVideoPackets(reference, shifted, frames);
            else assert.throws(() => compareVideoPackets(reference, shifted, frames), /origin shift/);
            report.checks.push({name, expected: accepted ? 'accept' : 'reject', passed: true,
                common_shift_seconds: shifted.timeline.timestamps[0] - reference.timeline.timestamps[0]});
        }
        // Two different encodes can have identical opening packets. Use the
        // complete artifacts for this negative, and assert it is really changed.
        const admitted = proof(receipt.staged_output), alternate = proof(baseline);
        assert.notEqual(admitted.hash, alternate.hash, 'Substitution control needs different video');
        assert.throws(() => compareVideoPackets(admitted, alternate, admitted.timeline.count), /video payload/);
        report.checks.push({name: 'substituted-baseline-video', expected: 'reject', passed: true});

        const chapters = path.join(directory, 'chapters.txt');
        fs.writeFileSync(chapters, 'CHAPTER01=00:00:00.000\nCHAPTER01NAME=Opening\nCHAPTER02=00:00:01.000\nCHAPTER02NAME=Second chapter\n');
        const source = path.join(directory, 'source-with-extras.mkv');
        run('mkvmerge', ['-o', source, '--chapters', chapters, '--attachment-mime-type',
            'application/x-truetype-font', '--attachment-name', 'fixture.ttf', '--attach-file', fontPath, clip], [0, 1]);
        const reattach = require(path.join(config.plugins_root,
            'FlowPlugins/LocalFlowPlugins/video/reattachAttachments/1.0.0/index.js'));
        const args = {originalLibraryFile: {_id: source}, inputFileObj: {_id: clip}, inputs: {},
            variables: {user: {attachmentsRemoved: true}}, workDir: path.join(directory, 'reattach'),
            deps: {fsextra: {ensureDirSync: p => fs.mkdirSync(p, {recursive: true})}},
            jobLog: message => fs.appendFileSync(path.join(directory, 'reattach.log'), message + '\n'),
            updateWorker: () => {}, logOutcome: () => {}};
        const output = (await reattach.plugin(args)).outputFileObj._id;
        compareVideoPackets(reference, proof(output), frames);
        const info = JSON.parse(run('mkvmerge', ['-J', output]));
        assert.equal(info.attachments.length, 1);
        const extracted = path.join(directory, 'extracted.ttf');
        run('mkvextract', [output, 'attachments', info.attachments[0].id + ':' + extracted]);
        const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
        assert.equal(sha(extracted), sha(fontPath));
        const chapterProbe = file => JSON.parse(run('/usr/local/bin/ffprobe',
            ['-v', 'error', '-show_chapters', '-of', 'json', file])).chapters;
        const sourceChapters = chapterProbe(source);
        assert.equal(sourceChapters.length, 2);
        assert.deepEqual(chapterProbe(output), sourceChapters);
        report.checks.push({name: 'authoritative-font-and-chapters', expected: 'preserve', passed: true,
            attachment_sha256: sha(extracted), chapters: sourceChapters.length});
        assert.deepEqual(inputs.map(identity), before, 'Control inputs changed');
        report.complete = true; save();
    } catch (error) {
        report.error = String(error.message || error); save(); throw error;
    }
}

if (require.main === module) {
    assert.equal(process.argv.length, 5, 'usage: tdarr_trial_controls.js CONFIG.json OUTPUT_DIR FONT.ttf');
    main(...process.argv.slice(2)).catch(error => {
        process.stderr.write(String(error.stack || error) + '\n'); process.exitCode = 1;
    });
}
