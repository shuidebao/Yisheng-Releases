const $ = (selector) => document.querySelector(selector);

const elements = {
  recordButton: $("#recordButton"),
  recordLabel: $("#recordLabel"),
  recordHint: $("#recordHint"),
  sessionState: $("#sessionState"),
  liveDot: $("#liveDot"),
  transcriptList: $("#transcriptList"),
  emptyState: $("#emptyState"),
  thinkingRow: $("#thinkingRow"),
  latencyMetric: $("#latencyMetric"),
  languageMetric: $("#languageMetric"),
  segmentMetric: $("#segmentMetric"),
  languageSelect: $("#languageSelect"),
  audioSourceSelect: $("#audioSourceSelect"),
  modelSelect: $("#modelSelect"),
  modelDownloadTitle: $("#modelDownloadTitle"),
  modelDownloadDetail: $("#modelDownloadDetail"),
  modelDownloadTrack: $("#modelDownloadTrack"),
  modelDownloadBar: $("#modelDownloadBar"),
  deviceSelect: $("#deviceSelect"),
  systemDeviceSelect: $("#systemDeviceSelect"),
  systemAudioHelp: $("#systemAudioHelp"),
  exportButton: $("#exportButton"),
  clearButton: $("#clearButton"),
  levelBars: $("#levelBars"),
  miniButton: $("#miniButton"),
  settingsButton: $("#settingsButton"),
  appVersion: $("#appVersion"),
  aboutVersion: $("#aboutVersion"),
  officialRepository: $("#officialRepository"),
  settingsDrawer: $("#settingsDrawer"),
  drawerBackdrop: $("#drawerBackdrop"),
  closeSettings: $("#closeSettings"),
  saveSettingsButton: $("#saveSettingsButton"),
  installTranslationButton: $("#installTranslationButton"),
  clearCacheButton: $("#clearCacheButton"),
  cacheStatus: $("#cacheStatus"),
  cacheDetail: $("#cacheDetail"),
  translationStatus: $("#translationStatus"),
  translationDetail: $("#translationDetail"),
  gpuName: $("#gpuName"),
  hardwareMeta: $("#hardwareMeta"),
  hardwareState: $("#hardwareState"),
  deviceHelp: $("#deviceHelp"),
  toastStack: $("#toastStack"),
  updateOverlay: $("#updateOverlay"),
  updateVersion: $("#updateVersion"),
  updateNotes: $("#updateNotes"),
  updateProgress: $("#updateProgress"),
  updateProgressBar: $("#updateProgressBar"),
  updateProgressText: $("#updateProgressText"),
  updateError: $("#updateError"),
  updateLaterButton: $("#updateLaterButton"),
  updateActionButton: $("#updateActionButton"),
};

const state = {
  recording: false,
  stream: null,
  audioContext: null,
  sourceNode: null,
  captureNode: null,
  silentGain: null,
  buffers: [],
  bufferedFrames: 0,
  sampleRate: 48000,
  chunkSeconds: 4.8,
  overlapSeconds: 0.75,
  queue: [],
  processing: false,
  segments: [],
  status: null,
  fallbackProcessor: null,
  captureLanguage: "en",
  captureMode: "microphone",
  systemAudioActive: false,
  systemPollController: null,
  systemDevices: [],
  updatePollTimer: null,
  updateReady: false,
  whisperModels: null,
};

const languageNames = {
  en: "英语", ja: "日语", ko: "韩语", fr: "法语", de: "德语",
  es: "西班牙语", ru: "俄语", pt: "葡萄牙语", it: "意大利语", zh: "中文",
};

const audioSourceNames = {
  microphone: "麦克风",
  system: "电脑声音",
  both: "麦克风 + 电脑",
};

function toast(message, type = "info", timeout = 4800) {
  const item = document.createElement("div");
  item.className = `toast ${type}`;
  item.textContent = message;
  elements.toastStack.append(item);
  window.setTimeout(() => item.remove(), timeout);
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  let payload = null;
  try { payload = await response.json(); } catch { /* no-op */ }
  if (!response.ok) throw new Error(payload?.detail || `请求失败 (${response.status})`);
  return payload;
}

function hideUpdateDialog() {
  elements.updateOverlay.hidden = true;
  if (state.updatePollTimer) window.clearInterval(state.updatePollTimer);
  state.updatePollTimer = null;
}

function showUpdateDialog(result) {
  elements.updateVersion.textContent = `当前 ${result.current_version} → 最新 ${result.latest_version}`;
  elements.updateNotes.textContent = result.notes || "修复问题并提升稳定性。";
  elements.updateError.hidden = true;
  elements.updateProgress.hidden = true;
  elements.updateActionButton.disabled = false;
  elements.updateActionButton.textContent = "下载更新";
  state.updateReady = false;
  elements.updateOverlay.hidden = false;
}

async function checkForUpdates() {
  try {
    const result = await api("/api/update/check", { method: "POST" });
    if (result.available) showUpdateDialog(result);
  } catch {
    // Update checks must never interrupt normal offline use.
  }
}

function renderUpdateProgress(result) {
  const progress = Math.max(0, Math.min(100, Number(result.progress || 0)));
  elements.updateProgress.hidden = false;
  elements.updateProgressBar.style.width = `${progress}%`;
  elements.updateProgressText.textContent = result.total_bytes
    ? `${progress}% · ${formatBytes(result.downloaded_bytes)} / ${formatBytes(result.total_bytes)}`
    : `${progress}% · 正在下载…`;
}

async function pollUpdateDownload() {
  try {
    const result = await api("/api/update/status");
    renderUpdateProgress(result);
    if (result.status === "ready") {
      window.clearInterval(state.updatePollTimer);
      state.updatePollTimer = null;
      state.updateReady = true;
      elements.updateActionButton.disabled = false;
      elements.updateActionButton.textContent = "立即安装";
      elements.updateProgressText.textContent = "下载完成并通过完整性校验";
    } else if (result.status === "error") {
      window.clearInterval(state.updatePollTimer);
      state.updatePollTimer = null;
      elements.updateActionButton.disabled = false;
      elements.updateActionButton.textContent = "重新下载";
      elements.updateError.textContent = result.error || "更新下载失败，当前版本可以继续使用。";
      elements.updateError.hidden = false;
    }
  } catch {
    // A later poll can recover from a momentary local request failure.
  }
}

async function handleUpdateAction() {
  if (state.updateReady) {
    elements.updateActionButton.disabled = true;
    elements.updateActionButton.textContent = "正在启动安装…";
    try {
      const result = await window.pywebview.api.install_update();
      if (!result.ok) throw new Error(result.error || "无法启动更新。 ");
    } catch (error) {
      elements.updateActionButton.disabled = false;
      elements.updateActionButton.textContent = "立即安装";
      elements.updateError.textContent = error.message;
      elements.updateError.hidden = false;
    }
    return;
  }

  elements.updateError.hidden = true;
  elements.updateActionButton.disabled = true;
  elements.updateActionButton.textContent = "下载中…";
  try {
    const result = await api("/api/update/download", { method: "POST" });
    renderUpdateProgress(result);
    if (state.updatePollTimer) window.clearInterval(state.updatePollTimer);
    state.updatePollTimer = window.setInterval(pollUpdateDownload, 700);
  } catch (error) {
    elements.updateActionButton.disabled = false;
    elements.updateActionButton.textContent = "重新下载";
    elements.updateError.textContent = error.message;
    elements.updateError.hidden = false;
  }
}

function openSettings() {
  loadCacheStatus();
  loadWhisperModels();
  elements.drawerBackdrop.hidden = false;
  requestAnimationFrame(() => elements.settingsDrawer.classList.add("open"));
  elements.settingsDrawer.setAttribute("aria-hidden", "false");
}

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let size = bytes / 1024;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size >= 10 ? size.toFixed(1) : size.toFixed(2)} ${units[index]}`;
}

const modelLabels = { tiny: "Tiny", base: "Base", small: "Small", medium: "Medium" };

function renderWhisperModelStatus(models = state.whisperModels) {
  if (!models) return;
  state.whisperModels = models;
  const selected = elements.modelSelect.value;
  const info = models[selected];
  if (!info) return;
  const label = modelLabels[selected] || selected;
  elements.modelDownloadTrack.hidden = info.status !== "downloading";
  elements.modelDownloadBar.style.width = `${Math.max(0, Math.min(100, Number(info.progress || 0)))}%`;
  if (info.installed) {
    elements.modelDownloadTitle.textContent = `${label} 已安装${info.bundled ? " · 安装包内置" : ""}`;
    elements.modelDownloadDetail.textContent = `本地模型约 ${formatBytes(info.total_bytes)}，切换时不会重复下载`;
  } else if (info.status === "downloading") {
    elements.modelDownloadTitle.textContent = `正在下载 ${label} · ${info.progress || 0}%`;
    elements.modelDownloadDetail.textContent = `${formatBytes(info.downloaded_bytes)} / ${formatBytes(info.total_bytes)} · ${info.source || "正在连接下载源"} · 可断点续传`;
  } else if (info.status === "error") {
    elements.modelDownloadTitle.textContent = `${label} 下载未完成`;
    elements.modelDownloadDetail.textContent = info.error || "请点击“应用设置”重试";
  } else {
    elements.modelDownloadTitle.textContent = `${label} 尚未下载`;
    elements.modelDownloadDetail.textContent = `首次选择将下载约 ${formatBytes(info.total_bytes)}，下载完成后保存在本地`;
  }
}

async function loadWhisperModels() {
  try {
    state.whisperModels = await api("/api/models/whisper/status");
    renderWhisperModelStatus();
  } catch (error) {
    elements.modelDownloadTitle.textContent = "模型状态读取失败";
    elements.modelDownloadDetail.textContent = error.message;
  }
}

async function ensureWhisperModel(model) {
  let info = await api(`/api/models/whisper/${model}/status`);
  if (info.installed) return info;
  info = await api(`/api/models/whisper/${model}/download`, { method: "POST" });
  while (info.status === "downloading") {
    state.whisperModels = { ...(state.whisperModels || {}), [model]: info };
    renderWhisperModelStatus();
    elements.saveSettingsButton.textContent = `下载 ${modelLabels[model] || model} · ${info.progress || 0}%`;
    await new Promise((resolve) => window.setTimeout(resolve, 600));
    info = await api(`/api/models/whisper/${model}/status`);
  }
  state.whisperModels = { ...(state.whisperModels || {}), [model]: info };
  renderWhisperModelStatus();
  if (!info.installed) throw new Error(info.error || `${modelLabels[model] || model} 模型下载失败。`);
  return info;
}

async function openMiniOverlay() {
  if (!window.pywebview?.api?.show_overlay) {
    toast("迷你悬浮窗仅在桌面版中可用。", "error");
    return;
  }
  try {
    const result = await window.pywebview.api.show_overlay();
    if (!result.ok) throw new Error(result.error || "无法打开迷你悬浮窗。");
  } catch (error) {
    toast(error.message, "error");
  }
}

async function loadCacheStatus() {
  try {
    const result = await api("/api/cache/status");
    elements.cacheStatus.textContent = `可清理 ${formatBytes(result.cache_bytes)}`;
    const models = result.installed_models?.length ? result.installed_models.join("、") : "暂无";
    elements.cacheDetail.textContent = `已下载模型：${models}（${formatBytes(result.model_bytes)}，不会删除）`;
  } catch (error) {
    elements.cacheStatus.textContent = "缓存状态读取失败";
    elements.cacheDetail.textContent = error.message;
  }
}

async function clearAppCache() {
  if (state.recording || state.processing) {
    toast("请先停止同传并等待当前片段处理完成。", "error");
    return;
  }
  elements.clearCacheButton.disabled = true;
  elements.clearCacheButton.textContent = "清理中…";
  try {
    state.queue = [];
    state.buffers = [];
    state.bufferedFrames = 0;
    elements.thinkingRow.hidden = true;
    if ("caches" in window) {
      const keys = await window.caches.keys();
      await Promise.all(keys.map((key) => window.caches.delete(key)));
    }
    const result = await api("/api/cache/clear", { method: "POST" });
    elements.cacheStatus.textContent = `已释放 ${formatBytes(result.removed_bytes)}`;
    elements.cacheDetail.textContent = result.restart_required
      ? "已下载模型、设置和字幕均已保留；重启后完成网页缓存清理。"
      : "已下载模型、设置和字幕均已保留。";
    toast(`缓存清理完成，释放 ${formatBytes(result.removed_bytes)}。已下载模型不会被删除。`, "info", 6500);
  } catch (error) {
    toast(`清理失败：${error.message}`, "error", 6500);
    await loadCacheStatus();
  } finally {
    elements.clearCacheButton.disabled = false;
    elements.clearCacheButton.textContent = "清理缓存";
  }
}

function closeSettings() {
  elements.settingsDrawer.classList.remove("open");
  elements.settingsDrawer.setAttribute("aria-hidden", "true");
  window.setTimeout(() => { elements.drawerBackdrop.hidden = true; }, 300);
}

function refreshTranslationState() {
  if (!state.status) return;
  const source = elements.languageSelect.value;
  const pairs = state.status.translation_pairs || [];
  const ready = source === "zh" || pairs.includes(`${source}-zh`) ||
    (pairs.includes(`${source}-en`) && pairs.includes("en-zh"));
  elements.translationDetail.textContent = `${languageNames[source] || "当前语言"} → 中文`;
  elements.translationStatus.textContent = ready ? "已安装 · 可离线使用" : source === "auto" ? "自动识别后检查" : "尚未安装";
  elements.installTranslationButton.hidden = ready || source === "auto" || source === "zh";
}

async function loadStatus() {
  try {
    state.status = await api("/api/status");
    const { hardware, recommended, engine } = state.status;
    state.chunkSeconds = Number(recommended.chunk_seconds || 4.8);
    const version = state.status.version || "未知";
    if (elements.appVersion) elements.appVersion.textContent = `版本 ${version}`;
    if (elements.aboutVersion) elements.aboutVersion.textContent = version;
    const repository = state.status.app_info?.repository;
    if (repository && elements.officialRepository) {
      elements.officialRepository.href = repository;
      elements.officialRepository.textContent = repository.replace(/^https?:\/\//, "");
    }
    elements.modelSelect.value = engine.model;
    renderWhisperModelStatus();
    elements.deviceSelect.value = engine.requested_device;
    elements.gpuName.textContent = hardware.gpu || "未检测到 NVIDIA 显卡";
    const availableRam = hardware.available_ram_gb ? ` · 可用 ${hardware.available_ram_gb} GB` : "";
    elements.hardwareMeta.textContent = `${hardware.cpu} · ${hardware.ram_gb || "?"} GB RAM${availableRam}`;
    elements.hardwareState.textContent = hardware.cuda_runtime_ready ? "GPU 就绪" : "CPU 回退";
    elements.hardwareState.style.color = hardware.cuda_runtime_ready ? "var(--lime)" : "#f3c969";
    elements.deviceHelp.textContent = hardware.cuda_runtime_ready
      ? `CUDA 已就绪，推荐 ${recommended.model} / GPU。`
      : "检测到显卡，但 CUDA 12 / cuDNN 9 运行库不完整；自动模式使用 CPU。";
    refreshTranslationState();
  } catch (error) {
    toast(`无法读取引擎状态：${error.message}`, "error");
  }
}

async function loadSystemAudioDevices() {
  try {
    const result = await api("/api/audio/system/devices");
    state.systemDevices = result.devices || [];
    elements.systemDeviceSelect.innerHTML = '<option value="">自动选择当前扬声器</option>';
    for (const device of state.systemDevices) {
      const option = document.createElement("option");
      option.value = String(device.index);
      option.textContent = `${device.default ? "默认 · " : ""}${device.name}`;
      elements.systemDeviceSelect.append(option);
    }

    const savedDevice = localStorage.getItem("yisheng-system-device") || "";
    if ([...elements.systemDeviceSelect.options].some((item) => item.value === savedDevice)) {
      elements.systemDeviceSelect.value = savedDevice;
    }
    const available = Boolean(result.available && state.systemDevices.length);
    elements.systemDeviceSelect.disabled = !available;
    elements.systemAudioHelp.textContent = available
      ? `已检测到 ${state.systemDevices.length} 个 Windows 输出设备，使用 WASAPI 本地捕获。`
      : (result.error || "没有检测到可用的电脑声音设备。");
    for (const option of elements.audioSourceSelect.options) {
      if (option.value !== "microphone") option.disabled = !available;
    }
    if (available && !localStorage.getItem("yisheng-audio-source")) {
      elements.audioSourceSelect.value = "system";
      updateSourceHint();
    }
    if (!available && elements.audioSourceSelect.value !== "microphone") {
      elements.audioSourceSelect.value = "microphone";
      updateSourceHint();
    }
  } catch (error) {
    elements.systemDeviceSelect.disabled = true;
    elements.systemAudioHelp.textContent = `电脑声音组件不可用：${error.message}`;
    for (const option of elements.audioSourceSelect.options) {
      if (option.value !== "microphone") option.disabled = true;
    }
  }
}

function createLevelBars() {
  for (let index = 0; index < 13; index += 1) {
    const bar = document.createElement("i");
    elements.levelBars.append(bar);
  }
}

function updateLevel(samples) {
  let sum = 0;
  for (let index = 0; index < samples.length; index += 8) sum += samples[index] * samples[index];
  const rms = Math.min(1, Math.sqrt(sum / Math.max(1, samples.length / 8)) * 5.5);
  updateLevelMeter(rms);
}

function updateLevelMeter(level) {
  const rms = Math.max(0, Math.min(1, Number(level) || 0));
  const bars = elements.levelBars.children;
  for (let index = 0; index < bars.length; index += 1) {
    const distance = Math.abs(index - (bars.length - 1));
    const jitter = .45 + Math.random() * .55;
    bars[index].style.height = `${Math.max(3, rms * (17 - distance * .55) * jitter)}px`;
  }
}

function ingestSamples(samples) {
  if (!state.recording) return;
  state.buffers.push(samples);
  state.bufferedFrames += samples.length;
  updateLevel(samples);
  if (state.bufferedFrames >= state.sampleRate * state.chunkSeconds) flushAudio(false);
}

function concatenate(buffers, totalLength) {
  const output = new Float32Array(totalLength);
  let offset = 0;
  for (const buffer of buffers) {
    output.set(buffer, offset);
    offset += buffer.length;
  }
  return output;
}

function downsample(input, inputRate, outputRate = 16000) {
  if (inputRate === outputRate) return input;
  const ratio = inputRate / outputRate;
  const length = Math.round(input.length / ratio);
  const output = new Float32Array(length);
  for (let outIndex = 0; outIndex < length; outIndex += 1) {
    const start = Math.floor(outIndex * ratio);
    const end = Math.min(input.length, Math.floor((outIndex + 1) * ratio));
    let total = 0;
    for (let inIndex = start; inIndex < end; inIndex += 1) total += input[inIndex];
    output[outIndex] = total / Math.max(1, end - start);
  }
  return output;
}

function encodeWav(samples, sampleRate = 16000) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeString = (offset, value) => {
    for (let index = 0; index < value.length; index += 1) view.setUint8(offset + index, value.charCodeAt(index));
  };
  writeString(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, "data");
  view.setUint32(40, samples.length * 2, true);
  let offset = 44;
  for (const value of samples) {
    const clamped = Math.max(-1, Math.min(1, value));
    view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
    offset += 2;
  }
  return new Blob([view], { type: "audio/wav" });
}

function flushAudio(finalChunk) {
  if (state.bufferedFrames < state.sampleRate * (finalChunk ? .45 : 1)) return;
  const combined = concatenate(state.buffers, state.bufferedFrames);
  const duration = combined.length / state.sampleRate;
  const resampled = downsample(combined, state.sampleRate);
  state.queue.push({ blob: encodeWav(resampled), duration, language: state.captureLanguage, audioSource: "microphone" });

  if (finalChunk) {
    state.buffers = [];
    state.bufferedFrames = 0;
  } else {
    const overlapFrames = Math.min(combined.length, Math.floor(state.sampleRate * state.overlapSeconds));
    const overlap = combined.slice(combined.length - overlapFrames);
    state.buffers = [overlap];
    state.bufferedFrames = overlap.length;
  }
  processQueue();
}

function trimWordOverlap(previous, current) {
  if (!previous || !current) return current.trim();
  const oldWords = previous.trim().split(/\s+/);
  const newWords = current.trim().split(/\s+/);
  const max = Math.min(12, oldWords.length, newWords.length);
  for (let width = max; width >= 2; width -= 1) {
    const left = oldWords.slice(-width).join(" ").toLocaleLowerCase();
    const right = newWords.slice(0, width).join(" ").toLocaleLowerCase();
    if (left === right) return newWords.slice(width).join(" ");
  }
  return current.trim();
}

function trimCharacterOverlap(previous, current) {
  if (!previous || !current) return current.trim();
  const oldText = previous.replace(/\s/g, "");
  const newText = current.replace(/\s/g, "");
  const max = Math.min(28, oldText.length, newText.length);
  for (let width = max; width >= 3; width -= 1) {
    if (oldText.slice(-width) === newText.slice(0, width)) return newText.slice(width);
  }
  return current.trim();
}

async function processQueue() {
  if (state.processing || !state.queue.length) return;
  state.processing = true;
  elements.thinkingRow.hidden = false;
  const chunk = state.queue.shift();
  const source = chunk.language;
  try {
    const previous = state.segments.at(-1);
    const sameStream = previous?.audio_source === (chunk.audioSource || "microphone");
    const explicitSameLanguage = source !== "auto" && previous?.language === source;
    const incomplete = previous && !/[.!?。！？…][\"'”’）】]*$/.test(previous.original.trim());
    const context = sameStream && explicitSameLanguage && incomplete && previous.original.length <= 180
      ? previous.original
      : "";
    const result = await api(`/api/transcribe?language=${encodeURIComponent(source)}&duration=${chunk.duration.toFixed(2)}&context=${encodeURIComponent(context)}`, {
      method: "POST",
      headers: { "Content-Type": "audio/wav" },
      body: chunk.blob,
    });
    result.audio_source = chunk.audioSource || "microphone";
    if (result.original) appendSegment(result);
    if (result.warning) toast(result.warning, result.translation_ready ? "info" : "error", 6500);
  } catch (error) {
    toast(error.message, "error", 6500);
    setSessionState(state.recording ? "仍在监听 · 上一片段失败" : "处理失败", state.recording);
  } finally {
    state.processing = false;
    elements.thinkingRow.hidden = state.queue.length === 0;
    if (state.queue.length) processQueue();
    else if (!state.recording) setSessionState("本次同传已结束", false);
  }
}

function appendSegment(result) {
  const previous = state.segments.at(-1);
  const sameSource = previous?.audio_source === result.audio_source;
  const continuing = Boolean(result.continued && sameSource && previous?._element);
  if (!continuing) {
    const cjk = ["ja", "zh", "ko"].includes(result.language);
    result.original = cjk
      ? trimCharacterOverlap(sameSource ? previous.original : "", result.original)
      : trimWordOverlap(sameSource ? previous.original : "", result.original);
    result.translation = trimCharacterOverlap(sameSource ? previous.translation : "", result.translation);
  }
  if (!result.original) return;

  elements.emptyState.hidden = true;
  const item = continuing ? previous._element : document.createElement("article");
  const timestamp = continuing
    ? previous._timestamp
    : new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  result._element = item;
  result._timestamp = timestamp;
  if (continuing) state.segments[state.segments.length - 1] = result;
  else state.segments.push(result);

  item.className = "transcript-item";
  const confidence = result.language_probability ? `${Math.round(result.language_probability * 100)}%` : "—";
  const translatedContent = result.translation_ready && result.translation
    ? `<p>${escapeHtml(result.translation)}</p>`
    : `<p>内置翻译模型不可用，请重新安装译声。</p>`;
  item.innerHTML = `
    <div class="transcript-cell original">
      <p>${escapeHtml(result.original)}</p>
      <div class="transcript-meta"><span>${timestamp}</span><span>${audioSourceNames[result.audio_source] || "声音"}</span><span>${languageNames[result.language] || result.language}</span><span class="confidence">${confidence}</span></div>
    </div>
    <div class="transcript-cell translation ${result.translation_ready ? "" : "missing"}">
      ${translatedContent}
      <div class="transcript-meta"><span>${result.model}</span><span>${result.device.toUpperCase()}</span><span>${result.latency_ms} ms</span></div>
    </div>`;
  if (!continuing) elements.transcriptList.append(item);
  item.scrollIntoView({ behavior: "smooth", block: "end" });

  elements.latencyMetric.textContent = result.latency_ms >= 1000 ? `${(result.latency_ms / 1000).toFixed(1)}s` : `${result.latency_ms}ms`;
  elements.languageMetric.textContent = languageNames[result.language] || result.language.toUpperCase();
  elements.segmentMetric.textContent = state.segments.length;
  elements.exportButton.disabled = false;
  if (window.pywebview?.api?.update_overlay) {
    window.pywebview.api.update_overlay({
      original: result.original,
      translation: result.translation_ready ? result.translation : "翻译模型不可用",
      meta: `${timestamp} · ${modelLabels[result.model] || result.model} · ${result.latency_ms} ms`,
    }).catch(() => {});
  }
}

function escapeHtml(text) {
  const element = document.createElement("span");
  element.textContent = text || "";
  return element.innerHTML;
}

function setSessionState(label, live) {
  elements.sessionState.textContent = label;
  elements.liveDot.classList.toggle("live", Boolean(live));
}

async function startMicrophoneCapture() {
  state.stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    video: false,
  });
  state.audioContext = new AudioContext({ latencyHint: "interactive" });
  state.sampleRate = state.audioContext.sampleRate;
  state.sourceNode = state.audioContext.createMediaStreamSource(state.stream);
  state.silentGain = state.audioContext.createGain();
  state.silentGain.gain.value = 0;

  try {
    await state.audioContext.audioWorklet.addModule("/static/pcm-worklet.js?v=ui");
    state.captureNode = new AudioWorkletNode(state.audioContext, "pcm-bridge");
    state.captureNode.port.onmessage = (event) => ingestSamples(event.data);
  } catch {
    const processor = state.audioContext.createScriptProcessor(4096, 1, 1);
    processor.onaudioprocess = (event) => ingestSamples(new Float32Array(event.inputBuffer.getChannelData(0)));
    state.captureNode = processor;
    state.fallbackProcessor = processor;
  }
  state.sourceNode.connect(state.captureNode);
  state.captureNode.connect(state.silentGain);
  state.silentGain.connect(state.audioContext.destination);
}

async function pollSystemAudio() {
  while (state.systemAudioActive) {
    const controller = new AbortController();
    state.systemPollController = controller;
    try {
      const response = await fetch("/api/audio/system/chunk?timeout=5", { signal: controller.signal, cache: "no-store" });
      if (!state.systemAudioActive) break;
      if (response.status === 204) continue;
      if (!response.ok) {
        let detail = `电脑声音读取失败 (${response.status})`;
        try { detail = (await response.json()).detail || detail; } catch { /* no-op */ }
        throw new Error(detail);
      }
      const duration = Number(response.headers.get("X-Audio-Duration")) || state.chunkSeconds;
      const level = Number(response.headers.get("X-Audio-Level")) || 0;
      const blob = await response.blob();
      updateLevelMeter(level);
      state.queue.push({ blob, duration, language: state.captureLanguage, audioSource: "system" });
      processQueue();
    } catch (error) {
      if (error.name === "AbortError" || !state.systemAudioActive) break;
      state.systemAudioActive = false;
      toast(error.message, "error", 6500);
      setSessionState("电脑声音监听已中断", false);
      break;
    } finally {
      if (state.systemPollController === controller) state.systemPollController = null;
    }
  }
}

async function startSystemAudioCapture() {
  const rawDeviceIndex = elements.systemDeviceSelect.value;
  await api("/api/audio/system/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      device_index: rawDeviceIndex === "" ? null : Number(rawDeviceIndex),
      chunk_seconds: state.chunkSeconds,
    }),
  });
  state.systemAudioActive = true;
  pollSystemAudio();
}

async function stopCaptureResources() {
  state.systemAudioActive = false;
  state.systemPollController?.abort();
  state.systemPollController = null;
  try { state.sourceNode?.disconnect(); } catch { /* no-op */ }
  try { state.captureNode?.disconnect(); } catch { /* no-op */ }
  state.stream?.getTracks().forEach((track) => track.stop());
  try { await state.audioContext?.close(); } catch { /* no-op */ }
  state.stream = null;
  state.audioContext = null;
  state.sourceNode = null;
  state.captureNode = null;
  state.fallbackProcessor = null;
  try { await api("/api/audio/system/stop", { method: "POST" }); } catch { /* The backend also stops on exit. */ }
}

function updateSourceHint() {
  if (state.recording) return;
  const hints = {
    microphone: "只听本人说话 · 游戏/视频请选电脑声音",
    system: "推荐 · 直接捕获游戏、视频和播客声音",
    both: "同时监听两路声音",
  };
  elements.recordHint.textContent = hints[elements.audioSourceSelect.value] || hints.microphone;
}

async function startRecording() {
  state.captureLanguage = elements.languageSelect.value;
  state.captureMode = elements.audioSourceSelect.value;
  state.recording = true;
  state.buffers = [];
  state.bufferedFrames = 0;
  try {
    if (state.captureMode === "microphone") {
      toast("翻译游戏、视频或播客时请改选“电脑声音”；麦克风只适合直接说话。", "info", 7000);
    }
    if (state.captureMode === "microphone" || state.captureMode === "both") {
      await startMicrophoneCapture();
    }
    if (state.captureMode === "system" || state.captureMode === "both") {
      await startSystemAudioCapture();
    }

    elements.recordButton.classList.add("recording");
    elements.recordButton.setAttribute("aria-label", "停止同传");
    elements.recordLabel.textContent = "正在同传";
    elements.recordHint.textContent = audioSourceNames[state.captureMode];
    elements.levelBars.classList.add("active");
    elements.languageSelect.disabled = true;
    elements.audioSourceSelect.disabled = true;
    elements.systemDeviceSelect.disabled = true;
    setSessionState(`正在监听 · ${audioSourceNames[state.captureMode]}`, true);
  } catch (error) {
    state.recording = false;
    await stopCaptureResources();
    const permissionDenied = error.name === "NotAllowedError";
    toast(permissionDenied ? "需要允许麦克风权限才能监听麦克风。" : `声音启动失败：${error.message}`, "error", 6500);
  }
}

async function stopRecording() {
  state.recording = false;
  if (state.captureMode === "microphone" || state.captureMode === "both") flushAudio(true);
  state.buffers = [];
  state.bufferedFrames = 0;
  await stopCaptureResources();
  elements.recordButton.classList.remove("recording");
  elements.recordButton.setAttribute("aria-label", "开始同传");
  elements.recordLabel.textContent = "开始同传";
  elements.levelBars.classList.remove("active");
  elements.languageSelect.disabled = false;
  elements.audioSourceSelect.disabled = false;
  elements.systemDeviceSelect.disabled = state.systemDevices.length === 0;
  updateSourceHint();
  setSessionState(state.processing || state.queue.length ? "正在完成最后片段" : "本次同传已结束", false);
}

function clearTranscript() {
  state.segments = [];
  elements.transcriptList.querySelectorAll(".transcript-item").forEach((item) => item.remove());
  elements.emptyState.hidden = false;
  elements.exportButton.disabled = true;
  elements.latencyMetric.textContent = "—";
  elements.languageMetric.textContent = "—";
  elements.segmentMetric.textContent = "0";
  if (window.pywebview?.api?.clear_overlay) window.pywebview.api.clear_overlay().catch(() => {});
}

function formatTranscript() {
  const lines = ["译声 · 同声传译记录", `导出时间：${new Date().toLocaleString("zh-CN")}`, ""];
  state.segments.forEach((segment, index) => {
    const source = audioSourceNames[segment.audio_source] || "声音";
    lines.push(`[${index + 1}] 原文（${source} · ${languageNames[segment.language] || segment.language}）`);
    lines.push(segment.original);
    lines.push("中文");
    lines.push(segment.translation || "[未翻译]");
    lines.push("");
  });
  return lines.join("\r\n");
}

async function exportTranscript() {
  if (!state.segments.length) return;
  const content = formatTranscript();
  if (window.pywebview?.api?.save_transcript) {
    try {
      const result = await window.pywebview.api.save_transcript(content);
      if (result.ok) toast(`已保存到：${result.path}`);
      else if (!result.cancelled) toast(result.error || "保存失败。", "error");
    } catch (error) {
      toast(`桌面导出失败：${error.message}`, "error");
    }
    return;
  }
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `译声同传_${new Date().toISOString().slice(0, 19).replaceAll(":", "-")}.txt`;
  link.click();
  URL.revokeObjectURL(link.href);
}

async function saveSettings() {
  if (state.recording) {
    toast("请先停止当前同传，再切换模型。", "error");
    return;
  }
  elements.saveSettingsButton.disabled = true;
  elements.clearCacheButton.disabled = true;
  elements.saveSettingsButton.textContent = "检查模型中…";
  try {
    await ensureWhisperModel(elements.modelSelect.value);
    await api("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: elements.modelSelect.value, device: elements.deviceSelect.value }),
    });
    localStorage.setItem("yisheng-engine", JSON.stringify({
      model: elements.modelSelect.value,
      device: elements.deviceSelect.value,
    }));
    toast("运行设置已应用。模型会在下次识别时加载。");
    await loadStatus();
    closeSettings();
  } catch (error) {
    toast(error.message, "error");
  } finally {
    elements.saveSettingsButton.disabled = false;
    elements.clearCacheButton.disabled = false;
    elements.saveSettingsButton.textContent = "应用设置";
  }
}

async function installTranslation() {
  const source = elements.languageSelect.value;
  elements.installTranslationButton.disabled = true;
  elements.installTranslationButton.textContent = "检查中…";
  elements.translationStatus.textContent = "正在检查本地模型";
  try {
    const result = await api(`/api/models/translation/${source}`, { method: "POST" });
    state.status.translation_pairs = result.pairs;
    refreshTranslationState();
    toast(`${languageNames[source] || source} → 中文翻译模型安装完成。`);
  } catch (error) {
    elements.translationStatus.textContent = "缺少离线模型包";
    toast(error.message, "error", 7000);
  } finally {
    elements.installTranslationButton.disabled = false;
    elements.installTranslationButton.textContent = "安装";
  }
}

elements.recordButton.addEventListener("click", () => state.recording ? stopRecording() : startRecording());
elements.miniButton.addEventListener("click", openMiniOverlay);
elements.settingsButton.addEventListener("click", openSettings);
elements.closeSettings.addEventListener("click", closeSettings);
elements.drawerBackdrop.addEventListener("click", closeSettings);
elements.clearButton.addEventListener("click", clearTranscript);
elements.exportButton.addEventListener("click", exportTranscript);
elements.saveSettingsButton.addEventListener("click", saveSettings);
elements.installTranslationButton.addEventListener("click", installTranslation);
elements.clearCacheButton.addEventListener("click", clearAppCache);
elements.updateLaterButton.addEventListener("click", hideUpdateDialog);
elements.updateActionButton.addEventListener("click", handleUpdateAction);
elements.languageSelect.addEventListener("change", () => {
  localStorage.setItem("yisheng-language", elements.languageSelect.value);
  refreshTranslationState();
});
elements.audioSourceSelect.addEventListener("change", () => {
  localStorage.setItem("yisheng-audio-source", elements.audioSourceSelect.value);
  updateSourceHint();
});
elements.systemDeviceSelect.addEventListener("change", () => {
  localStorage.setItem("yisheng-system-device", elements.systemDeviceSelect.value);
});
elements.modelSelect.addEventListener("change", () => renderWhisperModelStatus());
document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeSettings(); });
window.addEventListener("beforeunload", () => {
  state.stream?.getTracks().forEach((track) => track.stop());
  if (state.systemAudioActive) fetch("/api/audio/system/stop", { method: "POST", keepalive: true });
});
window.addEventListener("pywebviewready", async () => {
  document.body.classList.add("desktop-app");
  const runtimeLabel = $("#runtimeLabel");
  if (runtimeLabel) runtimeLabel.textContent = "桌面本地处理 · 免费";
  try {
    const info = await window.pywebview.api.get_app_info();
    document.documentElement.dataset.desktopVersion = info.version || "";
    if (elements.appVersion && info.version) elements.appVersion.textContent = `版本 ${info.version}`;
  } catch { /* Desktop bridge status is non-critical. */ }
});

createLevelBars();
const savedLanguage = localStorage.getItem("yisheng-language");
if (savedLanguage && [...elements.languageSelect.options].some((item) => item.value === savedLanguage)) {
  elements.languageSelect.value = savedLanguage;
}
const savedAudioSource = localStorage.getItem("yisheng-audio-source");
if (savedAudioSource && [...elements.audioSourceSelect.options].some((item) => item.value === savedAudioSource)) {
  elements.audioSourceSelect.value = savedAudioSource;
}
updateSourceHint();

async function initialize() {
  await Promise.all([loadStatus(), loadSystemAudioDevices(), loadCacheStatus(), loadWhisperModels()]);
  try {
    const saved = JSON.parse(localStorage.getItem("yisheng-engine") || "null");
    if (saved && state.status && (saved.model !== state.status.engine.model || saved.device !== state.status.engine.requested_device)) {
      await api("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(saved),
      });
      await loadStatus();
    }
  } catch {
    localStorage.removeItem("yisheng-engine");
  }
  window.setTimeout(checkForUpdates, 1800);
}

initialize();
document.documentElement.dataset.appReady = "1";
