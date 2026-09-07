const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
function element() {
  return { value: "", options: [], children: [], dataset: {}, style: {},
    classList: { add() {}, remove() {}, toggle() {} }, setAttribute() {}, scrollIntoView() {},
    append(child) { this.children.push(child); }, querySelectorAll() { return []; },
    get innerHTML() { return this._html || this.textContent || ""; },
    set innerHTML(value) { this._html = value; } };
}
const nodes = new Map();
const overlay = [];
const sandbox = { console, Date, setTimeout, clearTimeout, Blob,
  localStorage: { getItem() { return null; }, setItem() {} },
  document: { querySelector(key) { if (!nodes.has(key)) nodes.set(key, element()); return nodes.get(key); },
    querySelectorAll() { return []; }, createElement: element },
  window: { YishengAudioSession: require("../static/audio-session.js"),
    pywebview: { api: { update_overlay: async data => overlay.push(data) } } } };
vm.createContext(sandbox);
const source = fs.readFileSync(path.join(__dirname, "../static/app.js"), "utf8");
// Run the real pipeline functions, with only browser startup and DOM replaced.
vm.runInContext(source.split('elements.recordButton.addEventListener("click"')[0] +
  "\n globalThis.pipeline = {state, elements, appendSegment, processQueue, stopRecording, startRecording};", sandbox);
const p = sandbox.pipeline;
const base = { original: "Wait for me.", translation: "等我。", continued: false, language: "en",
  target_language: "zh", language_probability: .95, audio_source: "system", model: "base",
  device: "cpu", translation_ready: true, latency_ms: 100, _sessionId: 1, _sequence: 1, _endedAt: 8 };
p.appendSegment({ ...base });
p.appendSegment({ ...base, _sequence: 2 });
assert.equal(p.state.segments.length, 2, "a legitimate repeated sentence must remain visible");
assert.equal(p.state.segments[1].translation, "等我。");
assert.deepEqual(overlay.map(x => x.replace_latest), [false, false]);
p.appendSegment({ ...base, original: "Wait for me. I am coming.", continued: true, _sequence: 3 });
assert.equal(p.state.segments.length, 2);
assert.equal(overlay.at(-1).replace_latest, true);

(async () => {
  const requests = [];
  sandbox.mockApi = async (url) => {
    requests.push(url);
    if (url.startsWith("/api/transcribe")) return { ...base, original: "Move to cover.", translation: "找掩体。" };
    return {};
  };
  vm.runInContext("api = mockApi; toast = () => {};", sandbox);
  p.state.recording = true;
  p.state.queue.push({ blob: new Blob(), duration: 3, language: "auto", target: "zh",
    sessionId: 2, audioSource: "system", sequence: 1, startedAt: 0, endedAt: 3, continuation: true });
  await p.processQueue();
  assert.ok(requests[0].includes("language=auto"));
  assert.ok(requests[0].endsWith("context="), "new sessions cannot inherit stale context");
  // Simulate a flushed tail returned after stop, followed by queue exhaustion.
  p.state.captureMode = "system";
  p.state.sessionId = 2;
  p.state.captureLanguage = "en";
  p.state.captureTarget = "zh";
  p.state.lastSystemSequence = 1;
  let polls = 0;
  sandbox.fetch = async () => ++polls === 1 ? {
    ok: true, status: 200, headers: { get: key => ({
      "X-Audio-Duration": "1", "X-Audio-Sequence": "2", "X-Audio-Continuation": "0",
      "X-Audio-Started-At": "4", "X-Audio-Ended-At": "5" })[key] || "0" },
    blob: async () => new Blob(),
  } : { status: 204 };
  await p.stopRecording();
  while (p.state.processing) await new Promise(resolve => setImmediate(resolve));
  assert.equal(polls, 2, "stop must drain the final backend sentence");
  const tailIndex = requests.findLastIndex(url => url.startsWith("/api/transcribe"));
  const releaseIndex = requests.lastIndexOf("/api/engine/release");
  assert.ok(releaseIndex > tailIndex, "models may only unload after the tail was processed");
  assert.equal(p.state.stopping, false);
  assert.equal(p.state.segments.at(-1)._sequence, 2);
  console.log("Real frontend pipeline: repetition, overlay revisions, session isolation and stop-tail drain passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
