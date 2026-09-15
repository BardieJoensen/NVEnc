'use strict';

// Run against a staged or installed LocalFlowPlugins tree, including its usual
// sibling FlowHelpers. Real media controls are recorded in the linked report.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const root = process.env.TDARR_LOCAL_PLUGINS_ROOT;
if (!root) throw new Error('Set TDARR_LOCAL_PLUGINS_ROOT to the plugin tree under test');
const policy = require(path.join(root, 'audio/resolveAudioPolicy/1.0.0/policy.js'));
const subtitles = require(path.join(root, 'audio/applySubtitlePolicy/1.0.0/index.js'));
const validator = require(path.join(root, 'video/validateTranscodeOutput/1.0.0/index.js'))._test;
const sub = (index, language, disposition = {}) => ({
    index, codec_type: 'subtitle', codec_name: 'hdmv_pgs_subtitle',
    tags: { language, title: 'Subtitle' }, disposition, outputArgs: [], removed: false,
});
const argsFor = (streams, preserveSubtitles = false) => ({
    inputFileObj: { _id: '/test.mkv' }, jobLog: () => {},
    variables: {
        user: { audioPolicy: { version: policy.VERSION, preserveSubtitles, originalLanguages: ['eng'] } },
        ffmpegCommand: { streams, shouldProcess: false },
    },
});
const signatures = streams => validator.outputSubtitleSignature({ streams });

test('unselected subtitles cannot acquire a default through FFmpeg auto-selection', () => {
    const streams = [sub(3, 'eng'), sub(4, 'dan')];
    const args = argsFor(streams, true);
    subtitles.plugin(args);
    assert.deepEqual(streams.map(s => s.outputArgs), [
        ['-disposition:{outputIndex}', '-default'],
        ['-disposition:{outputIndex}', '-default'],
    ]);
    assert.equal(args.variables.ffmpegCommand.shouldProcess, false,
        'restating metadata must not turn an otherwise unnecessary remux into work');
});

test('existing defaults and other flags survive subtitle pruning and audio insertion', () => {
    const dropped = sub(3, 'spa');
    const forced = sub(4, 'spa', { forced: 1, hearing_impaired: 1 });
    const preferred = sub(5, 'dan', { default: 1, original: 1 });
    const alreadyRemoved = { ...sub(6, 'eng'), removed: true };
    const streams = [{ index: 0, codec_type: 'video' }, dropped, forced, preferred, alreadyRemoved];
    subtitles.plugin(argsFor(streams));
    assert.equal(dropped.removed, true);
    assert.deepEqual(dropped.outputArgs, []);
    assert.deepEqual(alreadyRemoved.outputArgs, []);
    assert.equal(forced.removed, false);
    assert.deepEqual(forced.disposition, { forced: 1, hearing_impaired: 1 });
    assert.deepEqual(preferred.disposition, { default: 1, original: 1 });
    const kept = streams.filter(s => s.codec_type === 'subtitle' && !s.removed);
    assert.deepEqual(kept.map((s, i) => s.outputArgs.map(a => a.replace('{outputIndex}', String(i + 3)))), [
        ['-disposition:3', '-default'], ['-disposition:4', '+default'],
    ]);
});

test('Matroska language aliases compare equally for subtitles, audio and video', () => {
    for (const [a, b] of [['deu', 'ger'], ['fra', 'fre'], ['zho', 'chi'], ['ces', 'cze'], ['nld', 'dut']]) {
        const left = sub(1, a), right = sub(1, b);
        assert.deepEqual(signatures([left]), signatures([right]));
        assert.deepEqual(validator.audioStreamSignature(left), validator.audioStreamSignature(right));
        assert.deepEqual(validator.videoSemanticSignature(left), validator.videoSemanticSignature(right));
    }
});

test('distinct languages, lost tracks, and changed subtitle semantics remain unequal', () => {
    const source = sub(1, 'deu', { default: 0, forced: 1, hearing_impaired: 1 });
    for (const changed of [
        { ...source, tags: { ...source.tags, language: 'dan' } },
        { ...source, tags: { ...source.tags, title: 'Wrong title' } },
        { ...source, disposition: { ...source.disposition, default: 1 } },
        { ...source, disposition: { ...source.disposition, forced: 0 } },
        { ...source, disposition: { ...source.disposition, hearing_impaired: 0 } },
        { ...source, codec_name: 'subrip' },
    ]) assert.notDeepEqual(signatures([source]), signatures([changed]));
    assert.notDeepEqual(signatures([source]), signatures([]));
    assert.notDeepEqual(signatures([sub(1, 'cmn')]), signatures([sub(1, 'yue')]));
});
