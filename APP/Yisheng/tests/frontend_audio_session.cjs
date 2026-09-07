const assert = require("node:assert/strict");
const { enqueueLatest, recognitionPlan, MicrophoneSegmenter } = require("../static/audio-session.js");

const previous = { _sessionId: 1, audio_source: "system", _sequence: 1, _endedAt: 8,
  language: "en", language_probability: .95, target_language: "zh", original: "We need to" };
const next = { sessionId: 1, audioSource: "system", sequence: 2, startedAt: 7.4,
  continuation: true, language: "auto", target: "zh" };
assert.deepEqual(recognitionPlan(previous, next), { language: "en", context: "We need to" });
for (const changes of [
  { sessionId: 2 }, { audioSource: "microphone" }, { sequence: 3 }, { startedAt: 25 },
  { continuation: false }, { target: "ja" },
]) assert.equal(recognitionPlan(previous, { ...next, ...changes }).context, "");
assert.equal(recognitionPlan({ ...previous, language_probability: .2 }, next).language, "auto");
assert.equal(recognitionPlan({ ...previous, original: "x".repeat(181) }, next).context, "");
const queue = [];
assert.equal(enqueueLatest(queue, 1), 0);
assert.equal(enqueueLatest(queue, 2), 0);
assert.equal(enqueueLatest(queue, 3), 1);
assert.deepEqual(queue, [2, 3]);

const rate = 16000;
const signal = (seconds, volume = .1) => new Float32Array(Math.round(rate * seconds)).fill(volume);
let mic = new MicrophoneSegmenter(rate);
assert.deepEqual(mic.push(signal(20, 0)), []);
assert.equal(mic.finish(), null);
assert.ok(mic.frames <= rate * .2);
assert.deepEqual(mic.push(signal(3)), []);
let output = mic.push(signal(.8, 0));
assert.equal(output.length, 1);
assert.equal(output[0].continuation, false);
assert.ok(output[0].startedAt >= 19.8);
assert.deepEqual(mic.push(signal(1)), []);
output = mic.push(signal(.8, 0));
assert.equal(output.length, 1);
assert.equal(output[0].continuation, false);
assert.equal(output[0].sequence, 2);
mic = new MicrophoneSegmenter(rate, { maxSeconds: 3 });
output = mic.push(signal(4));
assert.equal(output.length, 1);
assert.equal(output[0].continuation, false);
const tail = mic.finish();
assert.equal(tail.continuation, true);
assert.equal(tail.startedAt, 2.4);
assert.equal(mic.finish(), null);
mic = new MicrophoneSegmenter(rate, { maxSeconds: 3 });
assert.equal(mic.push(signal(3)).length, 1);
assert.equal(mic.finish(), null);
mic = new MicrophoneSegmenter(rate);
mic.push(signal(.3));
assert.ok(mic.finish());
console.log("Frontend sentence, overlap, bounded queue, language and session tests passed");
