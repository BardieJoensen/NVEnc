'use strict';

// Execute the generated review graph with the pinned real plugin modules.
// This supplies a fixture scanner and graph dispatcher, not the Tdarr scheduler.
// Run in an isolated container with the source mounted read-only.
const assert = require('node:assert/strict');
const cp = require('node:child_process');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

function catalog(root) {
    const found = new Map();
    function walk(dir) {
        for (const entry of fs.readdirSync(dir, {withFileTypes: true})) {
            const file = path.join(dir, entry.name);
            if (entry.isDirectory()) walk(file);
            else if (entry.name === 'index.js') {
                const parts = path.relative(root, file).split(path.sep);
                if (parts.length !== 5 || !parts[0].endsWith('FlowPlugins')) continue;
                const key = [parts[0].replace('FlowPlugins', ''), parts[2], parts[3]].join('/');
                assert(!found.has(key), 'Ambiguous plugin name: ' + key);
                found.set(key, file);
            }
        }
    }
    walk(root);
    return found;
}
function scan(file) {
    const probe = JSON.parse(cp.execFileSync('/usr/local/bin/ffprobe', ['-v', 'error',
        '-show_streams', '-show_format', '-show_chapters', '-of', 'json', file],
    {timeout: 120000, maxBuffer: 32 * 1024**2}));
    const video = probe.streams.find(s => s.codec_type === 'video' && !(s.disposition || {}).attached_pic);
    assert(video, 'Fixture has no primary video');
    return {_id: file, file, ffProbeData: probe, container: path.extname(file).slice(1),
        file_size: fs.statSync(file).size / 1024**2, bit_rate: Number(probe.format.bit_rate || 0),
        video_codec_name: video.codec_name, video_codec: video.codec_name, medium: 'video',
        video_resolution: video.width >= 3840 ? '4KUHD' : video.height >= 1080 ? '1080p'
            : video.height >= 720 ? '720p' : video.height >= 576 ? '576p' : '480p',
        mediaInfo: {track: []}};
}
function render(value, args) {
    if (typeof value !== 'string') return value;
    return value.replace(/\{\{\{(args\.[\w.]+)\}\}\}/g, (_, expression) => {
        let result = {args};
        for (const component of expression.split('.')) result = result?.[component];
        assert(result !== undefined && result !== null, 'Unresolved flow variable: ' + expression);
        return String(result);
    });
}
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');

async function run(config) {
    const directory = config.output_dir;
    assert(directory.startsWith('/work/'), 'Trial output must be below isolated /work');
    assert(!fs.existsSync(directory), 'Never overwrite an earlier trial');
    fs.mkdirSync(directory, {recursive: true});
    const report = {complete: false, scope: 'Generated review flow, actual pinned plugins and encoder; fixture scanner/dispatcher, no production scheduler or library replacement',
        started_at: Date.now() / 1000, flow_sha256: hash(config.flow), steps: []};
    const save = () => fs.writeFileSync(path.join(directory, 'report.json'), JSON.stringify(report, null, 2) + '\n');
    const log = message => fs.appendFileSync(path.join(directory, 'flow.log'), String(message) + '\n');
    save();
    try {
        assert.equal(report.flow_sha256, config.flow_sha256, 'Flow changed');
        await require(config.replay_helpers).verifyPlugins(config);
        const bundleRoot = path.dirname(config.bundle_plugins);
        const bundle = JSON.parse(fs.readFileSync(path.join(bundleRoot, 'bundle.json')));
        for (const [relative, expected] of Object.entries(bundle.files)) {
            const file = path.resolve(bundleRoot, relative);
            assert(file.startsWith(bundleRoot + path.sep), 'File outside pilot bundle');
            assert.equal(hash(file), expected, 'Pilot bundle changed: ' + relative);
        }
        const flow = JSON.parse(fs.readFileSync(config.flow)), nodes = new Map(flow.flowPlugins.map(n => [n.id, n]));
        const plugins = catalog(path.join(config.plugins_root, 'FlowPlugins'));
        for (const [key, file] of catalog(config.bundle_plugins)) {
            assert(!plugins.has(key), 'Pilot plugin shadows a pinned plugin');
            plugins.set(key, file);
        }
        for (const n of nodes.values()) {
            assert(n.fpEnabled !== false, 'Disabled node in review graph');
            assert(n.pluginName !== 'replaceOriginalFile' && !n.id.startsWith('notify'), 'Mutating node in review graph');
        }
        const routes = new Map();
        for (const edge of flow.flowEdges) {
            const key = edge.source + ':' + edge.sourceHandle;
            assert(!routes.has(key), 'Ambiguous graph edge'); routes.set(key, edge.target);
        }
        const original = scan(config.source);
        const args = {inputFileObj: original, originalLibraryFile: structuredClone(original),
            variables: {user: {}}, inputs: {}, userVariables: {global: {}, library: {}},
            jobLog: log, updateWorker: () => {}, logOutcome: () => {}, logFullCliOutput: true,
            ffmpegPath: '/usr/local/bin/ffmpeg', mkvpropeditPath: '/usr/bin/mkvpropedit',
            deps: {fsextra: require('/app/Tdarr_Node/node_modules/fs-extra'),
                configVars: {config: {serverIP: '127.0.0.1', serverPort: 9, apiKey: ''}},
                axios: async () => { throw new Error('Trial cannot call a production service'); },
                parseArgsStringToArgv: require('/app/Tdarr_Node/node_modules/string-argv').parseArgsStringToArgv}};
        const visited = new Set();
        let current = 'inputFile_001';
        while (current) {
            assert(!visited.has(current), 'Unexpected flow cycle'); visited.add(current);
            const node = nodes.get(current); assert(node, 'Missing graph node');
            const file = plugins.get([node.sourceRepo, node.pluginName, node.version].join('/'));
            assert(file, 'Plugin unavailable: ' + node.pluginName);
            args.workDir = path.join(directory, 'work', current);
            fs.mkdirSync(args.workDir, {recursive: true});
            args.inputs = Object.fromEntries(Object.entries(node.inputsDB || {}).map(([k, v]) => [k, render(v, args)]));
            const input = args.inputFileObj._id, started = Date.now();
            log('START ' + current);
            const response = await require(file).plugin(args);
            assert(response && response.outputFileObj && response.variables, 'Invalid plugin result: ' + current);
            args.variables = response.variables;
            args.inputFileObj = response.outputFileObj._id === input ? response.outputFileObj : scan(response.outputFileObj._id);
            report.steps.push({id: current, plugin_sha256: hash(file), input, output: args.inputFileObj._id,
                output_number: response.outputNumber, seconds: (Date.now() - started) / 1000});
            report.variables = args.variables.user;
            save();
            const next = routes.get(current + ':' + response.outputNumber);
            if (!next) {
                report.terminal = current;
                report.output = args.inputFileObj._id;
            }
            current = next;
        }
        const accepted = report.terminal === 'fidelityAccepted_001';
        assert.equal(args.inputFileObj._id, config.source, 'Review flow must end on its original source');
        if (accepted) {
            const artifact = args.variables.user.fidelityReviewArtifact;
            assert(artifact && artifact.copy_verified && artifact.library_replacement === false,
                'Accepted review needs an independent verified artifact');
            assert(fs.existsSync(artifact.candidate), 'Review artifact is missing');
        }
        assert.equal(accepted, config.expected_accepted, 'Unexpected flow admission');
        report.accepted = accepted;
        report.complete = true;
        report.finished_at = Date.now() / 1000;
        log('FLOW PASS: ' + (accepted ? 'candidate accepted for review' : 'source retained'));
    } catch (error) {
        report.error = String(error.stack || error);
        report.failed_at = Date.now() / 1000;
        throw error;
    } finally {
        save();
    }
    return report;
}

exports._test = {render};
exports.run = run;
if (require.main === module) run(JSON.parse(fs.readFileSync(process.argv[2])))
    .then(() => process.stdout.write('REVIEW FLOW PASS\n'))
    .catch(error => {process.stderr.write(String(error.stack) + '\n'); process.exitCode = 1;});
