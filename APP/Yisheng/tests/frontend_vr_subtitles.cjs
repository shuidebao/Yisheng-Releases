const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/vr-subtitles.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, '../static/index.html'), 'utf8');
function harness(api) {
  const nodes = new Map(), timers = new Map(), events = {}; let timer = 0;
  for (const id of ['Settings', 'Status', 'Start', 'Stop', 'Preview', 'PreviewHelp', 'Reset', 'Size', 'Distance', 'Vertical', 'Opacity', 'Original']) {
    nodes.set('vr' + id, {value: '', checked: false, disabled: false, events: {},
      querySelectorAll: () => [], addEventListener(name, fn) { this.events[name] = fn; }});
  }
  nodes.get('vrPreview').dataset = {vrText: 'test'};
  nodes.get('vrPreviewHelp').dataset = {vrText: 'test_help'};
  nodes.get('vrSettings').querySelectorAll = () => [nodes.get('vrPreview'), nodes.get('vrPreviewHelp')];
  for (const [id, value] of Object.entries({Size: 1, Distance: 1.5, Vertical: -.35, Opacity: .8})) nodes.get('vr'+id).value=value;
  nodes.get('vrOriginal').checked=true;
  const context = {document: {documentElement: {lang: 'zh-CN'}, getElementById: id => nodes.get(id)},
    window: {addEventListener(name, fn) { events[name] = fn; }, ...(api ? {pywebview: {api}} : {})},
    setTimeout: fn => { timers.set(++timer, fn); return timer; }, clearTimeout: id => timers.delete(id)};
  vm.runInNewContext(source, context);
  return {nodes, timers, context, events, click: id => nodes.get('vr'+id).events.click(), change: id => nodes.get('vr'+id).events.change()};
}
const tick = () => new Promise(resolve => setImmediate(resolve));
const defaults = {size: 1, distance: 1.5, vertical: -.35, opacity: .8, original: true};
(async () => {
  assert.match(html, /id="vrPreview"[^>]*data-vr-text="test"[^>]*disabled/);
  assert.match(html, /id="vrPreviewHelp"[^>]*data-vr-text="test_help"/);
  const plain = harness();
  assert.equal(plain.nodes.get('vrStart').disabled, true);
  assert.equal(plain.nodes.get('vrPreview').disabled, true);
  assert.equal(plain.timers.size, 0);
  let requests = [], resolvePoll;
  const api = {get_vr_state: async () => ({state: 'off'}),
    start_vr_overlay: async options => { requests.push(options); return {state: 'starting'}; },
    configure_vr_overlay: async options => { requests.push(options); return {state: 'ready'}; },
    stop_vr_overlay: async () => ({state: 'off'})};
  const h = harness(api); await tick();
  assert.equal(requests.length, 0); // Loading settings never enables VR or sends subtitles.
  await h.click('Start');
  assert.equal(h.nodes.get('vrStart').disabled, true);
  assert.equal(h.nodes.get('vrStop').disabled, false);
  assert.equal(h.nodes.get('vrPreview').disabled, true);
  assert.equal(h.timers.size, 1);
  assert.deepEqual(Object.keys(requests[0]).sort(), ['distance','opacity','original','size','vertical']);
  api.get_vr_state = () => new Promise(resolve => { resolvePoll = resolve; });
  const poll = h.context.window.YishengVR.refresh();
  await h.click('Stop');
  resolvePoll({state:'ready'}); await poll;
  assert.equal(h.nodes.get('vrStart').disabled, false); // Late polling cannot undo stop.
  assert.equal(h.timers.size, 0);
  api.start_vr_overlay = async () => ({state:'error', error:'no_headset'});
  await h.click('Start');
  assert.match(h.nodes.get('vrStatus').textContent, /头显/);
  h.context.window.YishengVR.setLanguage('en');
  assert.match(h.nodes.get('vrStatus').textContent, /headset/);
  await h.click('Reset');
  assert.equal(requests.at(-1).distance, 1.5);
  assert.equal(requests.at(-1).vertical, -.35);
  assert.equal(requests.at(-1).original, true);
  let snapshot = {state: 'ready', display: 'empty', settings: {...defaults, size: 1.25, distance: 2, original: false}};
  const previewCalls = [];
  let resolvePreview, resolveStale;
  const previewApi = {
    get_vr_state: async () => snapshot,
    preview_vr_overlay: (...args) => { previewCalls.push(args); return new Promise(resolve => { resolvePreview = resolve; }); },
    start_vr_overlay: () => { throw Error('Test text must not start the overlay or recording'); },
    configure_vr_overlay: async settings => ({...snapshot, settings}),
    stop_vr_overlay: async () => ({state: 'off', display: 'empty'}),
  };
  const p = harness(previewApi); await tick();
  assert.equal(p.nodes.get('vrPreview').disabled, false);
  assert.match(p.nodes.get('vrStatus').textContent, /^等待字幕/);
  assert.equal(p.nodes.get('vrDistance').value, 2); // Reloading the UI restores active runtime settings.
  assert.equal(p.nodes.get('vrSize').value, 1.25);
  assert.equal(p.nodes.get('vrOriginal').checked, false);
  p.nodes.get('vrDistance').value = 2.5;
  await p.context.window.YishengVR.refresh();
  assert.equal(p.nodes.get('vrDistance').value, 2.5); // Polling cannot overwrite an unfinished edit.

  previewApi.get_vr_state = () => new Promise(resolve => { resolveStale = resolve; });
  const stalePoll = p.context.window.YishengVR.refresh();
  const previewRequest = p.click('Preview');
  assert.equal(p.nodes.get('vrPreview').disabled, true);
  await p.click('Preview');
  assert.equal(previewCalls.length, 1); // Suppress a duplicate while the bridge call is pending.
  assert.deepEqual(previewCalls[0], []); // No text, settings, audio, or API payload leaves this button.
  resolvePreview({...snapshot, display: 'preview'}); await previewRequest;
  resolveStale({...snapshot, display: 'empty'}); await stalePoll;
  assert.match(p.nodes.get('vrStatus').textContent, /^正在显示测试字幕/);
  assert.equal(p.nodes.get('vrDistance').value, 2.5); // Preview does not apply or discard the settings draft.
  p.context.window.YishengVR.setLanguage('en');
  assert.match(p.nodes.get('vrStatus').textContent, /^Showing test subtitles/);
  assert.equal(p.nodes.get('vrPreview').textContent, 'Show test subtitles (5 seconds)');
  assert.match(p.nodes.get('vrPreviewHelp').textContent, /without recording or calling an API/);
  previewApi.get_vr_state = async () => snapshot;
  snapshot = {...snapshot, display: 'subtitle'};
  await p.context.window.YishengVR.refresh();
  assert.equal(p.nodes.get('vrStatus').textContent, 'Showing the current subtitle');
  snapshot = {...snapshot, display: 'empty'};
  await p.context.window.YishengVR.refresh();
  assert.match(p.nodes.get('vrStatus').textContent, /^Waiting for subtitles/);

  previewApi.configure_vr_overlay = async () => ({ok: false, error: 'invalid_settings'});
  p.nodes.get('vrDistance').value = '';
  await p.change('Distance');
  await p.context.window.YishengVR.refresh();
  assert.match(p.nodes.get('vrStatus').textContent, /valid distance/);
  assert.equal(p.nodes.get('vrStop').disabled, false);
  assert.equal(p.nodes.get('vrDistance').value, '');
  previewApi.configure_vr_overlay = async settings => ({...snapshot, settings});
  await p.click('Reset');
  assert.equal(p.nodes.get('vrDistance').value, 1.5);
  assert.match(p.nodes.get('vrStatus').textContent, /^Waiting for subtitles/);

  previewApi.get_vr_state = async () => { throw Error('Transient bridge failure'); };
  await p.context.window.YishengVR.refresh();
  assert.equal(p.nodes.get('vrStart').disabled, true);
  assert.equal(p.nodes.get('vrStop').disabled, false);
  assert.equal(p.timers.size, 1); // A failed poll must not strand a still-running overlay.
  assert.match(p.nodes.get('vrStatus').textContent, /Retrying/);
  previewApi.get_vr_state = async () => snapshot;
  await p.context.window.YishengVR.refresh();
  assert.match(p.nodes.get('vrStatus').textContent, /^Waiting for subtitles/);
  previewApi.preview_vr_overlay = async () => ({ok: false, state: 'error', error: 'not_ready'});
  await p.click('Preview');
  assert.match(p.nodes.get('vrStatus').textContent, /not connected/);
  assert.equal(p.nodes.get('vrPreview').disabled, true);
  assert.equal(p.timers.size, 0);
  previewApi.preview_vr_overlay = async (...args) => { previewCalls.push(args); return snapshot; };
  for (const state of ['off', 'starting', 'stopping', 'error']) {
    snapshot = {state, display: 'preview'};
    await p.context.window.YishengVR.refresh();
    assert.equal(p.nodes.get('vrPreview').disabled, true);
    const count = previewCalls.length;
    await p.click('Preview');
    assert.equal(previewCalls.length, count);
    assert.doesNotMatch(p.nodes.get('vrStatus').textContent, /^Showing test subtitles/);
  }
  snapshot = {state: 'error', error: 'cleanup_failed', display: 'empty'};
  await p.context.window.YishengVR.refresh();
  assert.equal(p.nodes.get('vrStart').disabled, true);
  assert.equal(p.nodes.get('vrPreview').disabled, true);
  assert.equal(p.nodes.get('vrStop').disabled, false);
  assert.match(p.nodes.get('vrStatus').textContent, /Try Disable again/);
  p.context.window.YishengVR.setLanguage('zh');
  assert.match(p.nodes.get('vrStatus').textContent, /再次点击关闭/);
  await p.click('Stop');
  assert.equal(p.nodes.get('vrStart').disabled, false);
  assert.equal(p.nodes.get('vrStop').disabled, true);
  snapshot = {state: 'ready', display: 'empty'};
  delete previewApi.preview_vr_overlay;
  await p.context.window.YishengVR.refresh();
  assert.equal(p.nodes.get('vrPreview').disabled, true); // Older desktop bridges remain safe.
  previewApi.get_vr_state = () => new Promise(resolve => { resolveStale = resolve; });
  const unloadPoll = p.context.window.YishengVR.refresh();
  p.events.beforeunload();
  resolveStale(snapshot); await unloadPoll;
  assert.equal(p.timers.size, 0); // A late promise must not restart polling after unload.

  const initialFailure = harness({get_vr_state: async () => { throw Error('Not ready yet'); }});
  await tick();
  assert.equal(initialFailure.timers.size, 1); // Retry an initial bridge failure as well.
  initialFailure.events.beforeunload();
  console.log('PASS VR default-off/start/options, ready-only no-argument preview, display states/language, preview/poll and stop/poll races, settings restoration/drafts, validation/reset, poll recovery, disconnect, cleanup retry, unload');
})().catch(error => { console.error(error); process.exitCode=1; });
