const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const source = fs.readFileSync(path.join(__dirname, "../static/app.js"), "utf8");
const markup = fs.readFileSync(path.join(__dirname, "../static/index.html"), "utf8");
const escape = value => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
function element() {
  const listeners = new Map();
  return { value: "", checked: false, disabled: false, hidden: false, options: [], children: [], dataset: {}, style: {},
    classList: { add() {}, remove() {}, toggle() {} }, setAttribute() {}, scrollIntoView() {}, remove() {},
    append(child) { this.children.push(child); }, querySelectorAll() { return []; },
    addEventListener(name, listener) { listeners.set(name, listener); },
    emit(name) { return listeners.get(name)?.({ target: this }); },
    get innerHTML() { return this._html ?? escape(this.textContent); }, set innerHTML(value) { this._html = value; } };
}
function status(translation = { mode: "local", revision: 0, base_url: "", model: "", has_api_key: false }) {
  return { translation, translation_pairs: ["en-zh"], version: "test", hardware: { cpu: "test", ram_gb: 8 },
    recommended: {}, engine: { model: "base", requested_device: "cpu" } };
}
function harness() {
  const nodes = new Map(), overlay = [], requests = [], notices = [], writes = [], windowEvents = new Map();
  const storage = new Map([["yisheng-translation", JSON.stringify({ mode: "api", api_key: "old-key" })]]);
  const sandbox = { console, Date, URL, Blob, setTimeout, clearTimeout, requestAnimationFrame: callback => callback(),
    localStorage: { getItem: key => storage.get(key) ?? null, setItem(key, value) { writes.push([key, value]); storage.set(key, value); } },
    document: { documentElement: { dataset: {} }, body: element(), title: "", addEventListener() {},
      querySelector(key) { if (!nodes.has(key)) nodes.set(key, element()); return nodes.get(key); },
      querySelectorAll() { return []; }, createElement: element },
    window: { setTimeout() {}, clearInterval() {}, addEventListener: (name, callback) => windowEvents.set(name, callback),
      YishengAudioSession: require("../static/audio-session.js"),
      pywebview: { api: { update_overlay: async payload => overlay.push(payload), set_ui_language: async () => {} } } } };
  vm.createContext(sandbox);
  // Include actual event bindings; omit only automatic page startup/network IO.
  vm.runInContext(source.split("\ncreateLevelBars();")[0] + `
    globalThis.ui = { state, elements, loadStatus, initializeTranslationDraft, renderTranslationSettings,
      renderTranslationMode, setUiLanguage, translationSettingsPayload, testTranslationConnection,
      saveSettings, startRecording, enqueueAudio, enqueueMicrophoneChunk, processQueue, appendSegment, UI_TEXT };`, sandbox);
  const ui = sandbox.ui;
  let applied = status();
  sandbox.mockApi = async (url, options = {}) => {
    requests.push({ url, options });
    if (url === "/api/status") return applied;
    if (url === "/api/models/whisper/base/status") return { installed: true };
    if (url === "/api/translation/test") return { ok: true, translation: "你好。", latency_ms: 12 };
    if (url === "/api/translation/config") {
      const data = JSON.parse(options.body);
      applied = status({ mode: data.mode, revision: applied.translation.revision + 1,
        base_url: data.mode === "api" ? data.base_url : "", model: data.mode === "api" ? data.model : "",
        has_api_key: data.mode === "api" && (data.api_key === null ? applied.translation.has_api_key : Boolean(data.api_key)) });
      return applied;
    }
    return {};
  };
  sandbox.note = (...args) => notices.push(args);
  vm.runInContext("api = (...args) => mockApi(...args); toast = (...args) => note(...args);", sandbox);
  ui.elements.languageSelect.value = "en";
  ui.elements.targetLanguageSelect.value = "zh";
  ui.elements.audioSourceSelect.value = "system";
  ui.elements.modelSelect.value = "base";
  ui.elements.deviceSelect.value = "cpu";
  return { ...ui, sandbox, nodes, overlay, requests, notices, writes, storage, windowEvents,
    setApplied(value) { applied = value; ui.state.status = value; },
    draft() {
      ui.elements.translationModeSelect.value = "api";
      ui.elements.translationBaseUrl.value = "https://example.test/v1";
      ui.elements.translationApiModel.value = "test-model";
      ui.elements.translationApiKey.value = "dummy-test-key";
      ui.elements.translationConsent.checked = true;
      ui.elements.translationModeSelect.emit("change");
    } };
}
const base = { original: "Wait for me.", translation: "等我。", continued: false, language: "en",
  target_language: "zh", language_probability: .95, audio_source: "system", model: "base", device: "cpu",
  translation_ready: true, latency_ms: 100, translation_mode: "api", _sessionId: 1, _sequence: 1, _endedAt: 8 };
const plain = value => JSON.parse(JSON.stringify(value));
let passed = 0;
async function test(name, callback) { await callback(); passed += 1; console.log(`PASS ${name}`); }

(async () => {
  await test("default offline ignores stale persisted API state; no request before explicit action", async () => {
    const h = harness();
    assert.equal(h.requests.length, 0);
    await h.loadStatus();
    assert.equal(h.elements.translationModeSelect.value, "local");
    assert.equal(h.elements.translationApiKey.value, "");
    assert.equal(h.elements.translationConsent.checked, false);
    assert.equal(h.elements.apiTranslationFields.hidden, true);
    assert.equal(h.elements.translationModeBadge.dataset.mode, "local");
    assert.deepEqual(h.requests.map(item => item.url), ["/api/status"]);
    assert.equal(h.writes.length, 0);
  });
  await test("bilingual UI preserves draft and distinguishes selected from active mode", async () => {
    const h = harness(); await h.loadStatus(); h.draft(); h.renderTranslationSettings();
    const before = plain(h.translationSettingsPayload());
    h.setUiLanguage("en"); h.setUiLanguage("zh");
    assert.deepEqual(plain(h.translationSettingsPayload()), before);
    assert.equal(h.elements.apiTranslationFields.hidden, false);
    assert.equal(h.elements.translationModeBadge.dataset.mode, "local");
    assert.ok(h.writes.every(([key]) => key === "yisheng-ui-language"));
  });
  await test("address or model edits reset key, no-key permission, consent and test result", async () => {
    const h = harness(); await h.loadStatus();
    for (const field of [h.elements.translationBaseUrl, h.elements.translationApiModel]) {
      h.draft(); h.elements.translationNoKey.checked = true; h.state.translationTest = { translation: "old" };
      field.value += "new"; field.emit("input");
      assert.equal(h.elements.translationApiKey.value, "");
      assert.equal(h.elements.translationNoKey.checked, false);
      assert.equal(h.elements.translationConsent.checked, false);
      assert.equal(h.state.translationTest, null);
    }
  });
  await test("test and apply require explicit consent and valid address", async () => {
    const h = harness(); await h.loadStatus(); h.draft(); h.elements.translationConsent.checked = false;
    await h.testTranslationConnection(); await h.saveSettings();
    assert.equal(h.requests.length, 1);
    h.elements.translationConsent.checked = true;
    for (const bad of ["", "http://example.test/v1", "https://user:pass@example.test/v1", "https://example.test/v1?key=secret", "https://example.test/v1#key"]) {
      h.elements.translationBaseUrl.value = bad;
      assert.throws(() => h.translationSettingsPayload());
    }
  });
  await test("test uses dedicated fixed-text endpoint without applying or sending transcript", async () => {
    const h = harness(); await h.loadStatus(); h.draft(); h.state.segments.push({ original: "PRIVATE USER TEXT" });
    await h.testTranslationConnection();
    assert.deepEqual(h.requests.map(item => item.url), ["/api/status", "/api/translation/test"]);
    const data = JSON.parse(h.requests.at(-1).options.body);
    assert.deepEqual(Object.keys(data).sort(), ["api_key", "base_url", "consent", "mode", "model"]);
    assert.ok(!h.requests.at(-1).options.body.includes("PRIVATE USER TEXT"));
    assert.equal(h.state.status.translation.mode, "local");
    assert.equal(h.elements.translationModeBadge.dataset.mode, "local");
    assert.match(h.elements.translationTestResult.textContent, /你好/);
  });
  await test("apply activates API, clears password input and never persists API configuration", async () => {
    const h = harness(); await h.loadStatus(); h.draft(); await h.saveSettings();
    assert.equal(h.state.status.translation.mode, "api");
    assert.equal(h.state.status.translation.revision, 1);
    assert.equal(h.elements.translationModeBadge.dataset.mode, "api");
    assert.equal(h.elements.translationApiKey.value, "");
    assert.equal(h.elements.translationConsent.checked, true);
    assert.deepEqual(h.writes.map(([key]) => key), ["yisheng-engine"]);
    assert.ok(!JSON.stringify(h.writes).includes("dummy-test-key"));
    h.elements.translationModeSelect.value = "local"; h.elements.translationModeSelect.emit("change");
    await h.saveSettings();
    assert.deepEqual(JSON.parse(h.requests.filter(item => item.url === "/api/translation/config").at(-1).options.body), { mode: "local" });
    assert.equal(h.state.status.translation.has_api_key, false);
    assert.equal(h.elements.translationConsent.checked, false);
    assert.equal(h.elements.translationBaseUrl.value, "");
  });
  await test("saved key can only be reused for the same normalized address and model", async () => {
    const h = harness(); await h.loadStatus(); h.draft(); await h.saveSettings();
    assert.equal(h.translationSettingsPayload().api_key, null);
    h.elements.translationBaseUrl.value = "https://EXAMPLE.test:443/v1/chat/completions/";
    assert.equal(h.translationSettingsPayload().api_key, null);
    h.elements.translationBaseUrl.value = "https://other.test/v1";
    assert.throws(() => h.translationSettingsPayload());
    h.elements.translationBaseUrl.value = "https://example.test/v1";
    h.elements.translationApiModel.value = "other-model";
    assert.throws(() => h.translationSettingsPayload());
  });
  await test("empty key needs explicit no-key checkbox and checkbox erases entered key", async () => {
    const h = harness(); await h.loadStatus(); h.draft(); h.elements.translationApiKey.value = "";
    assert.throws(() => h.translationSettingsPayload());
    h.elements.translationApiKey.value = "do-not-send"; h.elements.translationNoKey.checked = true;
    h.elements.translationNoKey.emit("change");
    assert.equal(h.elements.translationApiKey.value, "");
    assert.equal(h.elements.translationApiKey.disabled, true);
    assert.equal(h.translationSettingsPayload().api_key, "");
    h.elements.translationBaseUrl.value = "http://127.0.0.1:8888/v1";
    assert.equal(h.translationSettingsPayload().base_url, "http://127.0.0.1:8888/v1");
  });
  await test("recording, transitions, processing, queue and model release block test/apply", async () => {
    for (const change of [{ recording: true }, { starting: true }, { stopping: true }, { processing: true }, { queue: [{}] }, { releasePromise: Promise.resolve() }, { settingsBusy: true }]) {
      const h = harness(); await h.loadStatus(); h.draft(); Object.assign(h.state, change);
      h.renderTranslationSettings();
      assert.equal(h.elements.translationModeSelect.disabled, true);
      assert.equal(h.elements.testTranslationButton.disabled, true);
      assert.equal(h.elements.saveSettingsButton.disabled, true);
      await h.testTranslationConnection(); await h.saveSettings();
      assert.equal(h.requests.length, 1);
    }
  });
  await test("in-flight test prevents duplicate test, apply and recording start", async () => {
    const h = harness(); await h.loadStatus(); h.draft(); let resolve;
    h.sandbox.mockApi = async (url, options) => { h.requests.push({ url, options }); return new Promise(done => { resolve = done; }); };
    const pending = h.testTranslationConnection();
    assert.equal(h.state.settingsBusy, true); assert.equal(h.elements.recordButton.disabled, true);
    await h.testTranslationConnection(); await h.saveSettings(); await h.startRecording();
    assert.equal(h.requests.length, 2);
    resolve({ ok: true, translation: "你好", latency_ms: 2 }); await pending;
    assert.equal(h.state.settingsBusy, false); assert.equal(h.elements.recordButton.disabled, false);
  });
  await test("in-flight apply prevents duplicate apply, test and recording start", async () => {
    const h = harness(); await h.loadStatus(); h.draft();
    const normalApi = h.sandbox.mockApi;
    let resolve;
    h.sandbox.mockApi = async (url, options) => {
      if (url !== "/api/models/whisper/base/status") return normalApi(url, options);
      h.requests.push({ url, options });
      return new Promise(done => { resolve = done; });
    };
    const pending = h.saveSettings();
    assert.equal(h.state.settingsBusy, true);
    await h.saveSettings(); await h.testTranslationConnection(); await h.startRecording();
    assert.equal(h.requests.length, 2);
    resolve({ installed: true }); await pending;
    assert.equal(h.requests.filter(item => item.url === "/api/translation/config").length, 1);
    assert.equal(h.state.status.translation.mode, "api");
    assert.equal(h.state.settingsBusy, false);
  });
  await test("failed apply reconciles active status but preserves unsubmitted API draft", async () => {
    const h = harness(); await h.loadStatus(); h.draft();
    const normalApi = h.sandbox.mockApi;
    h.sandbox.mockApi = async (url, options) => {
      if (url !== "/api/translation/config") return normalApi(url, options);
      h.requests.push({ url, options });
      throw new Error("API configuration rejected");
    };
    await h.saveSettings();
    assert.equal(h.state.status.translation.mode, "local");
    assert.equal(h.elements.translationModeBadge.dataset.mode, "local");
    assert.equal(h.elements.translationModeSelect.value, "api");
    assert.equal(h.elements.translationApiKey.value, "dummy-test-key");
    assert.equal(h.state.settingsBusy, false);
    assert.ok(h.writes.every(([key]) => key === "yisheng-engine"));
  });
  await test("failed connection leaves local mode intact and renders error literally", async () => {
    const h = harness(); await h.loadStatus(); h.draft();
    h.sandbox.mockApi = async () => { throw new Error("API failure <img src=x onerror=alert(1)>"); };
    await h.testTranslationConnection();
    assert.equal(h.state.status.translation.mode, "local");
    assert.equal(h.state.settingsBusy, false);
    assert.match(h.elements.translationTestResult.innerHTML, /&lt;img/);
    assert.ok(!h.elements.translationTestResult.innerHTML.includes("<img"));
  });
  await test("session snapshots revision; microphone/system chunks keep it after status changes", async () => {
    const h = harness(); await h.loadStatus();
    h.setApplied(status({ mode: "api", revision: 7, base_url: "https://example.test/v1", model: "test", has_api_key: true }));
    vm.runInContext("startSystemAudioCapture = async () => {};", h.sandbox);
    await h.startRecording();
    assert.equal(h.state.captureTranslationRevision, 7);
    h.state.processing = true; h.state.status.translation.revision = 8;
    h.enqueueAudio({ blob: new Blob(), duration: 1, audioSource: "system", sequence: 1 });
    h.enqueueMicrophoneChunk({ samples: new Float32Array(160), duration: .01, sequence: 2 });
    assert.deepEqual(h.state.queue.map(item => item.translationRevision).join(","), "7,7");
    assert.equal(h.state.queue[0].audioSource, "system"); assert.equal(h.state.queue[1].audioSource, "microphone");
    h.sandbox.mockApi = async (url, options) => { h.requests.push({ url, options }); return {}; };
    h.state.processing = false; await h.processQueue();
    while (h.state.processing) await new Promise(resolve => setImmediate(resolve));
    const chunks = h.requests.filter(item => item.url.startsWith("/api/transcribe"));
    assert.equal(chunks.length, 2);
    assert.ok(chunks.every(item => item.url.includes("translation_revision=7&context=")));
    assert.ok(chunks.every(item => item.options.body instanceof Blob));
  });
  await test("API errors retain original in main/mini and no external HTML is interpreted", async () => {
    const h = harness(); await h.loadStatus();
    const original = "<img src=x onerror=alert(1)> original";
    const warning = "API request failed <script>bad()</script>";
    h.appendSegment({ ...base, original, translation: "", translation_ready: false, warning });
    const segment = h.state.segments.at(-1);
    assert.equal(segment.original, original);
    assert.ok(segment._element.innerHTML.includes("&lt;img"));
    assert.ok(segment._element.innerHTML.includes("&lt;script&gt;"));
    assert.ok(!segment._element.innerHTML.includes("<script>"));
    assert.equal(h.overlay.at(-1).original, original);
    assert.equal(h.overlay.at(-1).translation, warning);
    h.appendSegment({ ...base, translation: "<script>translation</script>" });
    assert.ok(h.state.segments.at(-1)._element.innerHTML.includes("&lt;script&gt;translation"));
    assert.equal(h.state.segments.length, 2);
  });
  await test("API form uses password input and clears draft key on close", async () => {
    assert.match(markup, /id="translationApiKey"[^>]*type="password"|type="password"[^>]*id="translationApiKey"/);
    assert.match(markup, /id="translationConsent"/);
    assert.match(markup, /id="translationNoKey"/);
    const h = harness(); await h.loadStatus(); h.draft(); h.windowEvents.get("beforeunload")();
    assert.equal(h.elements.translationApiKey.value, "");
  });
  console.log(`Frontend API translation: ${passed} regression groups passed`);
})().catch(error => { console.error(error); process.exitCode = 1; });
