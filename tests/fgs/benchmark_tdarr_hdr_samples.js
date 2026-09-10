#!/usr/bin/env node
'use strict';
// Offline only: exercise the installed validator's exact HDR sampling function
// with default versus four decoder threads. No flow or plugin file is changed.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const child = require('node:child_process');

const [output, ...sources] = process.argv.slice(2);
assert(output && sources.length, 'usage: benchmark_tdarr_hdr_samples.js NEW_OUTPUT_DIRECTORY SOURCE...');
fs.mkdirSync(output);
const pluginPath = '/app/Tdarr_Node/assets/app/plugins/FlowPlugins/LocalFlowPlugins/video/validateTranscodeOutput/1.0.0/index.js';
const ffprobe = '/usr/local/bin/ffprobe';
const validator = require(pluginPath)._test;
const digest = data => crypto.createHash('sha256').update(data).digest('hex');
const identity = file => {
    const s = fs.statSync(file, {bigint: true});
    return [s.dev, s.ino, s.size, s.mtimeNs, s.ctimeNs].map(String).join(':');
};
const originalExec = child.execFileSync;
const report = {complete: false, started_at: new Date().toISOString(),
    plugin_sha256: digest(fs.readFileSync(pluginPath)),
    ffprobe_sha256: digest(fs.readFileSync(ffprobe)),
    configuration: 'Offline ABBA; exact installed sampling function; only decoder thread option differs',
    sources: []};
const save = () => {
    fs.writeFileSync(path.join(output, 'report.tmp'), JSON.stringify(report, null, 2) + '\n');
    fs.renameSync(path.join(output, 'report.tmp'), path.join(output, 'report.json'));
};
save();
try {
    for (const source of sources) {
        const held = identity(source);
        const probe = JSON.parse(originalExec(ffprobe, ['-v', 'error', '-show_format', '-show_streams',
            '-of', 'json', source], {timeout: 30000, maxBuffer: 4 * 1024 * 1024}));
        const duration = validator.durationOf(probe);
        const row = {source, identity: held, duration, intervals: validator.buildIntervals(duration), runs: []};
        report.sources.push(row);
        for (const threads of [null, 4, 4, null]) {
            let observed = null;
            child.execFileSync = (executable, args, options) => {
                assert.equal(executable, ffprobe);
                assert(args.includes('-show_frames') && args.includes('-read_intervals'));
                const actualArgs = threads === null ? args : ['-threads', String(threads), ...args];
                const start = process.hrtime.bigint();
                const raw = originalExec(executable, actualArgs, {...options, timeout: 300000});
                const seconds = Number(process.hrtime.bigint() - start) / 1e9;
                const data = JSON.parse(raw);
                assert(data.frames.length > 0);
                observed = {threads, seconds, argv: actualArgs, frames: data.frames.length,
                    raw_sha256: digest(raw), parsed_sha256: digest(JSON.stringify(data))};
                return raw;
            };
            let result;
            try {
                result = validator.probeFrameMetadata(source, duration, 'v:0');
            } finally {
                child.execFileSync = originalExec;
            }
            assert(observed);
            assert.equal(identity(source), held, 'Input changed during benchmark');
            observed.validator_result = result;
            row.runs.push(observed);
            console.log(JSON.stringify({source, threads, seconds: observed.seconds, frames: observed.frames}));
            save();
        }
        row.exact_sampled_metadata_equal = row.runs.every(run =>
            run.parsed_sha256 === row.runs[0].parsed_sha256 &&
            JSON.stringify(run.validator_result) === JSON.stringify(row.runs[0].validator_result));
        const mean = threads => row.runs.filter(run => run.threads === threads)
            .reduce((sum, run) => sum + run.seconds, 0) / 2;
        row.default_mean_seconds = mean(null);
        row.four_threads_mean_seconds = mean(4);
        row.time_change_percent = 100 * (row.four_threads_mean_seconds / row.default_mean_seconds - 1);
        assert(row.exact_sampled_metadata_equal, 'Thread setting changed sampled metadata; do not adopt');
        save();
    }
    report.complete = true;
    report.passed = true;
    report.finished_at = new Date().toISOString();
} catch (error) {
    report.passed = false;
    report.error = String(error.stack || error);
    throw error;
} finally {
    child.execFileSync = originalExec;
    save();
}
