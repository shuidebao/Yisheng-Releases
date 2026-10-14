const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');
function element() {
  const classes = new Set(), events = new Map();
  return {value: '', options: [], children: [], dataset: {}, style: {}, disabled: false,
    classList: {add: x => classes.add(x), remove: x => classes.delete(x), contains: x => classes.has(x),
      toggle(x, on) { if (on) classes.add(x); else classes.delete(x); }},
    append(x) { this.children.push(x); this.options.push(x); },
    setAttribute() {}, querySelectorAll() { return []; }, scrollIntoView() {},
    addEventListener: (name, fn) => events.set(name, fn), emit(name) { return events.get(name)?.(); },
    set innerHTML(value) { this.options = value.includes('<option') ? [{value: ''}] : []; this._html = value; },
    get innerHTML() { return this._html || ''; }};
}
function harness() {
  const nodes = new Map(), requests = [], notices = [], storage = new Map();
  const sandbox = {console, Date, URL, Blob, AbortController, setTimeout, clearTimeout,
    requestAnimationFrame: fn => fn(), localStorage: {getItem: key => storage.get(key) || null,
      setItem: (key, value) => storage.set(key, value)},
    document: {documentElement: {dataset: {}}, body: element(), addEventListener() {},
      querySelector(key) { if (!nodes.has(key)) nodes.set(key, element()); return nodes.get(key); },
      querySelectorAll() { return []; }, createElement: element},
    window: {addEventListener() {}, YishengAudioSession: require('../static/audio-session.js')}};
  vm.createContext(sandbox);
  vm.runInContext(source.split('\ncreateLevelBars();')[0] + `
    globalThis.ui = {state, elements, loadSystemAudioDevices, startRecording, stopRecording, UI_TEXT};
    api = (...args) => mockApi(...args); toast = (...args) => note(...args);`, sandbox);
  const {state, elements} = sandbox.ui;
  state.status = {translation: {mode: 'local', revision: 0}};
  elements.audioSourceSelect.value = 'system';
  elements.audioSourceSelect.options = ['system', 'both', 'microphone'].map(value => ({value}));
  elements.languageSelect.value = 'en'; elements.targetLanguageSelect.value = 'zh';
  sandbox.note = (...args) => notices.push(args);
  sandbox.mockApi = async (url, options = {}) => { requests.push({url, options}); return {}; };
  sandbox.fetch = async () => { throw Error('unexpected fetch'); };
  return {...sandbox.ui, sandbox, requests, notices, storage};
}
const tick = () => new Promise(resolve => setImmediate(resolve));
async function settled(h) {
  for (let i = 0; i < 100; i++) {
    if (!h.state.starting && !h.state.recording && !h.state.stopping && !h.state.releasePromise) return;
    await tick();
  }
  throw Error('Capture cleanup did not finish');
}
let passed = 0;
async function test(name, fn) { await fn(); console.log('PASS ' + name); passed++; }
(async () => {
  await test('device names survive index changes; legacy numeric preference is not restored', async () => {
    const h = harness(); h.storage.set('yisheng-system-device', '7');
    const devices = [{index: 7, name: 'Headphones', default: true}];
    h.sandbox.mockApi = async () => ({available: true, devices});
    await h.loadSystemAudioDevices(); assert.equal(h.elements.systemDeviceSelect.value, '');
    h.elements.systemDeviceSelect.value = 'Headphones'; h.elements.systemDeviceSelect.emit('change');
    assert.equal(h.storage.get('yisheng-system-device-name'), 'Headphones');
    devices[0].index = 30; await h.loadSystemAudioDevices();
    assert.equal(h.elements.systemDeviceSelect.value, 'Headphones');
    devices.length = 0; await h.loadSystemAudioDevices();
    assert.equal(h.elements.systemDeviceSelect.value, 'Headphones');
    assert.equal(h.elements.audioSourceSelect.value, 'system', 'must not silently select microphone');
    assert.match(h.elements.systemDeviceSelect.options.at(-1).textContent, /未连接/);
  });
  await test('late device-list refresh cannot change a recording session', async () => {
    const h = harness(); let done;
    h.sandbox.mockApi = () => new Promise(resolve => {done = resolve;});
    const load = h.loadSystemAudioDevices(); h.state.starting = true;
    h.elements.systemDeviceSelect.value = 'Headphones'; done({available: true, devices: []}); await load;
    assert.equal(h.elements.systemDeviceSelect.value, 'Headphones');
  });
  await test('startup failure restores controls, releases models and shows only one error', async () => {
    const h = harness(); const normal = h.sandbox.mockApi;
    h.elements.systemDeviceSelect.value = 'Headphones';
    h.sandbox.mockApi = async (url, options) => {
      const result = await normal(url, options);
      if (url.endsWith('/start')) throw Error('Invalid device -9996');
      return result;
    };
    await h.startRecording();
    assert.equal(h.state.recording, false); assert.equal(h.state.starting, false);
    assert.equal(h.elements.recordButton.disabled, false);
    assert.equal(h.elements.sessionState.textContent, h.UI_TEXT.zh.audioNotStarted);
    assert.equal(h.elements.liveDot.classList.contains('live'), false);
    assert.equal(h.elements.recordLabel.textContent, h.UI_TEXT.zh.startInterpreting);
    assert.equal(h.notices.length, 1); assert.match(h.notices[0][0], /-9996/);
    assert.equal(h.requests.filter(x => x.url === '/api/engine/release').length, 1);
    const config = JSON.parse(h.requests.find(x => x.url.endsWith('/start')).options.body);
    assert.equal(config.device_name, 'Headphones'); assert.ok(!('device_index' in config));
  });
  await test('backend running=false is not presented as a successful start', async () => {
    const h = harness(); await h.startRecording();
    assert.equal(h.state.recording, false); assert.equal(h.notices.length, 1);
    assert.equal(h.elements.sessionState.textContent, h.UI_TEXT.zh.audioNotStarted);
  });
  for (const immediate of [false, true]) {
    await test(`capture interruption cleans up without awaiting itself (immediate=${immediate})`, async () => {
      const h = harness(); let fail;
      h.sandbox.fetch = () => immediate ? Promise.reject(Error('Device disconnected')) : new Promise(resolve => {fail = resolve;});
      const normal = h.sandbox.mockApi;
      h.sandbox.mockApi = async (url, options) => {
        await normal(url, options); return url.endsWith('/start') ? {running: true} : {};
      };
      await h.startRecording();
      if (!immediate) {
        assert.equal(h.state.recording, true);
        h.sandbox.fetch = async () => ({ok: false, status: 503});
        fail({ok: false, status: 503, json: async () => ({detail: 'Device disconnected'})});
      }
      await settled(h);
      assert.equal(h.state.systemAudioActive, false);
      assert.equal(h.elements.recordButton.disabled, false);
      assert.equal(h.elements.recordButton.classList.contains('recording'), false);
      assert.equal(h.notices.length, 1);
      assert.equal(h.requests.filter(x => x.url === '/api/engine/release').length, 1);
      assert.ok(h.requests.some(x => x.url === '/api/audio/system/stop'));
    });
  }
  await test('failed second source stops an already opened microphone', async () => {
    const h = harness(); let stopped = 0, closed = 0;
    h.elements.audioSourceSelect.value = 'both';
    h.sandbox.setMic = () => { h.state.stream = {getTracks: () => [{stop() {stopped++;}}]};
      h.state.audioContext = {close: async () => {closed++;}}; };
    vm.runInContext('startMicrophoneCapture = async () => setMic();', h.sandbox);
    await h.startRecording();
    assert.equal(stopped, 1); assert.equal(closed, 1); assert.equal(h.notices.length, 1);
  });
  console.log(`Frontend system audio: ${passed} regression groups passed`);
})().catch(error => {console.error(error); process.exitCode = 1;});
