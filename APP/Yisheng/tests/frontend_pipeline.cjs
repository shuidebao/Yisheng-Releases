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
  "\n globalThis.pipeline = {state, elements, appendSegment, processQueue, stopRecording, startRecording, refreshTranslationState, UI_TEXT};", sandbox);
const p = sandbox.pipeline;
const base = { original: "Wait for me.", translation: "等我。", continued: false, language: "en",
  target_language: "zh", language_probability: .95, audio_source: "system", model: "base",
  device: "cpu", translation_ready: true, latency_ms: 100, _sessionId: 1, _sequence: 1, _endedAt: 8 };
p.appendSegment({ ...base });
p.appendSegment({ ...base, _sequence: 2 });
assert.equal(p.state.segments.length, 2, "a legitimate repeated sentence must remain visible");
assert.equal(p.state.segments[1].translation, "等我。");
assert.deepEqual(overlay.map(x => x.original), ["Wait for me.", "Wait for me."]);
assert.deepEqual(overlay.map(x => x.translation), ["等我。", "等我。"]);
p.appendSegment({ ...base, original: "Wait for me. I am coming.", translation: "等我。我马上来。",
  continued: true, _sequence: 3 });
assert.equal(p.state.segments.length, 2);
assert.equal(p.state.segments[0].translation, "等我。", "the earlier main-window sentence must remain unchanged");
assert.equal(p.state.segments[1].translation, "等我。我马上来。", "a continuation revises only the current main-window item");
assert.equal(overlay.at(-1).original, "Wait for me. I am coming.");
assert.equal(overlay.at(-1).translation, "等我。我马上来。");
for (let sequence = 4; sequence <= 6; sequence += 1) {
  const current = { ...base, original: `Sentence ${sequence}.`, translation: `第 ${sequence} 句。`, _sequence: sequence };
  p.appendSegment(current);
  assert.equal(overlay.at(-1).original, current.original);
  assert.equal(overlay.at(-1).translation, current.translation);
}
assert.equal(p.state.segments.length, 5, "removing mini history must not limit the main transcript to one or four sentences");
assert.equal(p.state.segments[0].translation, "等我。");
for (const payload of overlay) {
  assert.deepEqual(Object.keys(payload).sort(), ["meta", "original", "translation"],
    "the mini window receives only current text and metadata, with no rolling-history flags");
}

(async () => {
  const markup = fs.readFileSync(path.join(__dirname, "../static/index.html"), "utf8");
  for (const id of ["languageSelect", "targetLanguageSelect"]) {
    const select = markup.match(new RegExp(`<select id="${id}">([\\s\\S]*?)</select>`))[1];
    assert.match(select, /value="ko" data-i18n="korean"/);
  }
  assert.equal(p.UI_TEXT.zh.korean, "韩语");
  assert.equal(p.UI_TEXT.en.korean, "Korean");
  const languages = ["zh", "ja", "en", "ko"];
  const allPairs = languages.flatMap(from => languages.filter(to => to !== from).map(to => `${from}-${to}`));
  p.state.status = { translation_pairs: allPairs };
  p.elements.languageSelect.value = "auto";
  p.elements.targetLanguageSelect.value = "ko";
  p.refreshTranslationState();
  assert.equal(p.elements.translationStatus.textContent, p.UI_TEXT.zh.translationReady);
  p.elements.targetLanguageSelect.value = "zh";
  p.state.status.translation_pairs = allPairs.filter(pair => pair !== "ko-zh");
  p.refreshTranslationState();
  assert.equal(p.elements.translationStatus.textContent, p.UI_TEXT.zh.translationBroken,
    "auto mode must check the Korean model instead of claiming all languages are ready");
  p.state.status.translation_pairs = allPairs;
  p.appendSegment({ ...base, language: "ko", original: "문을 열지 마세요.", translation: "请不要开门。" });
  assert.equal(overlay.at(-1).original, "문을 열지 마세요.");
  p.appendSegment({ ...base, target_language: "ko", translation: "잠시 기다려 주세요." });
  assert.equal(overlay.at(-1).translation, "잠시 기다려 주세요.");
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
  p.state.queue.push({ blob: new Blob(), duration: 3, language: "ko", target: "zh",
    sessionId: 2, audioSource: "system", sequence: 2, startedAt: 4, endedAt: 7, continuation: false });
  await p.processQueue();
  assert.ok(requests.at(-1).includes("language=ko&target=zh"));
  p.state.queue.push({ blob: new Blob(), duration: 3, language: "zh", target: "ko",
    sessionId: 2, audioSource: "system", sequence: 3, startedAt: 8, endedAt: 11, continuation: false });
  await p.processQueue();
  assert.ok(requests.at(-1).includes("language=zh&target=ko"));
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
  console.log("Real frontend pipeline: main history, current-only mini subtitles, session isolation and stop-tail drain passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
