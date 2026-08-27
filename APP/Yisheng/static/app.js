const $ = (selector) => document.querySelector(selector);

const INITIAL_UI_LANGUAGE = localStorage.getItem("yisheng-ui-language") === "en" ? "en" : "zh";
const UI_TEXT = {
  zh: {
    pageTitle: "译声 · 本地同声传译", brandHome: "译声首页", versionLoading: "版本读取中…",
    switchLanguage: "切换中文或英文界面", openMini: "打开迷你置顶字幕", miniTitle: "迷你置顶字幕",
    miniSubtitle: "迷你字幕", openSettings: "打开设置", settings: "设置", ready: "准备就绪",
    heroLead: "听见原声，", heroAccent: "即刻读懂。", heroCopy: "语音不上传云端。中文、日语、英语在你的电脑上完成识别与互译。",
    latency: "处理延迟", recognizedLanguage: "识别语言", segments: "片段", original: "原文",
    clearHistory: "清空记录", waitingVoice: "等待你的声音", startHelp: "选择原语言和翻译目标，然后点击下方按钮开始同传",
    processing: "正在识别与翻译…", sourceLanguage: "原语言", autoThree: "自动识别（中文/日语/英语）",
    chinese: "中文", english: "英语", japanese: "日语", translateTo: "翻译为", audioSource: "声音来源",
    microphoneOption: "麦克风（面对电脑说话）", systemOption: "电脑声音（游戏/视频推荐）", bothOption: "麦克风 + 电脑",
    startInterpreting: "开始同传", clickMicrophone: "点击开启麦克风", exportText: "导出文本",
    updateAvailable: "新版本可用", updateTitle: "译声可以更新", readingVersion: "正在读取版本信息…",
    prepareDownload: "准备下载…", later: "稍后提醒", downloadUpdate: "下载更新",
    updateSafe: "更新包通过 HTTPS 下载并进行 SHA-256 完整性校验。", localOptimization: "本机优化",
    runtimeSettings: "运行设置", closeSettings: "关闭设置", detectingHardware: "正在检测硬件…",
    pleaseWait: "请稍候", detecting: "检测中", interfaceLanguage: "界面语言", languageHint: "也可点击顶部 🌐 切换",
    recognitionModel: "识别模型", modelTradeoff: "越大越准确，也越慢",
    tinyOption: "Tiny · 极速 / 首次选择下载约 75 MB", baseOption: "Base · 已内置 / 性能均衡",
    smallOption: "Small · 更准确 / 首次选择下载约 484 MB", mediumOption: "Medium · 高准确度 / 首次选择下载约 1.53 GB",
    baseBundled: "Base 已内置", modelDownloadHelp: "选择其他模型后，点击“应用设置”开始下载",
    computeDevice: "计算设备", autoSelect: "自动选择", deviceHelp: "优先使用 GPU，运行库不可用时自动回退。",
    systemDevice: "电脑声音设备", gameVideoOutput: "游戏与视频输出", autoSpeaker: "自动选择当前扬声器",
    systemAudioHelp: "自动捕获 Windows 正在播放的声音，不需要打开“立体声混音”。",
    offlineTranslationModel: "离线互译模型", repair: "修复", cacheManagement: "缓存管理",
    cachePreserve: "保留已下载模型与字幕", calculating: "正在计算…", cacheItems: "临时音频、网页缓存与旧日志",
    clearCache: "清理缓存", applySettings: "应用设置", about: "关于", version: "版本", loading: "读取中…",
    runtimeLocal: "桌面本地处理 · 免费", runtimeWeb: "本地处理 · 免费",
    translationSuffix: "翻译", currentLanguage: "当前语言", autoDetectShort: "自动识别中/日/英",
    translationReady: "已安装 · 可离线使用", translationBroken: "内置模型不完整",
    microphone: "麦克风", systemAudio: "电脑声音", bothAudio: "麦克风 + 电脑", sound: "声音",
    requestFailed: "请求失败 ({status})", currentLatest: "当前 {current} → 最新 {latest}", defaultReleaseNotes: "修复问题并提升稳定性。",
    downloading: "正在下载…", installNow: "立即安装", verifiedDownload: "下载完成并通过完整性校验", retryDownload: "重新下载",
    updateFailedContinue: "更新下载失败，当前版本可以继续使用。", startingInstaller: "正在启动安装…", cannotStartUpdate: "无法启动更新。", downloadingAction: "下载中…",
    installed: "{model} 已安装{bundled}", bundled: " · 安装包内置", localModel: "本地模型约 {size}，切换时不会重复下载",
    modelDownloading: "正在下载 {model} · {progress}%", resumeDownload: "{done} / {total} · {source} · 可断点续传", connectingSource: "正在连接下载源",
    modelIncomplete: "{model} 下载未完成", applyRetry: "请点击“应用设置”重试", modelMissing: "{model} 尚未下载",
    firstDownload: "首次选择将下载约 {size}，下载完成后保存在本地", modelStatusFailed: "模型状态读取失败", modelDownloadFailed: "{model} 模型下载失败。",
    miniDesktopOnly: "迷你悬浮窗仅在桌面版中可用。", miniOpenFailed: "无法打开迷你悬浮窗。", cleanable: "可清理 {size}", none: "暂无",
    downloadedModels: "已下载模型：{models}（{size}，不会删除）", cacheStatusFailed: "缓存状态读取失败", stopBeforeClear: "请先停止同传并等待当前片段处理完成。",
    clearing: "清理中…", released: "已释放 {size}", cacheKeptRestart: "已下载模型、设置和字幕均已保留；重启后完成网页缓存清理。",
    cacheKept: "已下载模型、设置和字幕均已保留。", cacheCleared: "缓存清理完成，释放 {size}。已下载模型不会被删除。", clearFailed: "清理失败：{error}",
    unknown: "未知", noNvidia: "未检测到 NVIDIA 显卡", availableRam: " · 可用 {ram} GB", gpuReady: "GPU 就绪", cpuFallback: "CPU 回退",
    cudaReady: "CUDA 已就绪，推荐 {model} / GPU。", cudaIncomplete: "检测到显卡，但 CUDA 12 / cuDNN 9 运行库不完整；自动模式使用 CPU。",
    statusFailed: "无法读取引擎状态：{error}", defaultPrefix: "默认 · ", devicesFound: "已检测到 {count} 个 Windows 输出设备，使用 WASAPI 本地捕获。",
    noAudioDevice: "没有检测到可用的电脑声音设备。", audioComponentFailed: "电脑声音组件不可用：{error}", stillListening: "仍在监听 · 上一片段失败",
    processingFailed: "处理失败", sessionEnded: "本次同传已结束", translationUnavailable: "内置翻译模型不可用，请重新安装译声。",
    translationModelUnavailable: "翻译模型不可用", systemAudioReadFailed: "电脑声音读取失败 ({status})", systemAudioInterrupted: "电脑声音监听已中断",
    micHint: "只听本人说话 · 游戏/视频请选电脑声音", systemHint: "推荐 · 直接捕获游戏、视频和播客声音", bothHint: "同时监听两路声音",
    microphoneAdvice: "翻译游戏、视频或播客时请改选“电脑声音”；麦克风只适合直接说话。", stopInterpreting: "停止同传", interpreting: "正在同传",
    lowLatency: "低延迟同传 · {source}", micPermission: "需要允许麦克风权限才能监听麦克风。", audioStartFailed: "声音启动失败：{error}", finishingLast: "正在完成最后片段",
    exportTitle: "译声 · 同声传译记录", exportTime: "导出时间：{time}", originalLine: "[{index}] 原文（{source} · {language}）", untranslated: "[未翻译]",
    savedTo: "已保存到：{path}", saveFailed: "保存失败。", desktopExportFailed: "桌面导出失败：{error}", stopBeforeModel: "请先停止当前同传，再切换模型。",
    checkingModel: "检查模型中…", settingsApplied: "运行设置已应用。模型会在下次识别时加载。", checking: "检查中…", checkingLocalModel: "正在检查本地模型",
    translationChecked: "{source} → {target} 翻译模型检查完成。", offlinePackageMissing: "缺少离线模型包", install: "安装",
  },
  en: {
    pageTitle: "YiSheng · Local Live Interpreter", brandHome: "YiSheng home", versionLoading: "Loading version…",
    switchLanguage: "Switch between Chinese and English", openMini: "Open always-on-top mini subtitles", miniTitle: "Mini subtitles",
    miniSubtitle: "Mini subtitles", openSettings: "Open settings", settings: "Settings", ready: "Ready",
    heroLead: "Hear every word. ", heroAccent: "Understand it now.", heroCopy: "Audio never goes to the cloud. Chinese, Japanese, and English are recognized and translated locally on your PC.",
    latency: "Latency", recognizedLanguage: "Language", segments: "Segments", original: "Original",
    clearHistory: "Clear history", waitingVoice: "Waiting for audio", startHelp: "Choose a source and target language, then start live interpretation below.",
    processing: "Recognizing and translating…", sourceLanguage: "Source language", autoThree: "Auto detect (Chinese/Japanese/English)",
    chinese: "Chinese", english: "English", japanese: "Japanese", translateTo: "Translate to", audioSource: "Audio source",
    microphoneOption: "Microphone (speak to your PC)", systemOption: "Computer audio (games/videos)", bothOption: "Microphone + computer",
    startInterpreting: "Start interpreting", clickMicrophone: "Click to start the microphone", exportText: "Export text",
    updateAvailable: "Update available", updateTitle: "YiSheng can be updated", readingVersion: "Reading version information…",
    prepareDownload: "Preparing download…", later: "Later", downloadUpdate: "Download update",
    updateSafe: "The update is downloaded over HTTPS and verified with SHA-256.", localOptimization: "LOCAL OPTIMIZATION",
    runtimeSettings: "Runtime settings", closeSettings: "Close settings", detectingHardware: "Detecting hardware…",
    pleaseWait: "Please wait", detecting: "Detecting", interfaceLanguage: "Interface language", languageHint: "You can also use 🌐 at the top",
    recognitionModel: "Recognition model", modelTradeoff: "Larger is more accurate, but slower",
    tinyOption: "Tiny · Fastest / first download about 75 MB", baseOption: "Base · Bundled / balanced",
    smallOption: "Small · More accurate / first download about 484 MB", mediumOption: "Medium · High accuracy / first download about 1.53 GB",
    baseBundled: "Base is bundled", modelDownloadHelp: "Choose another model, then click Apply settings to download it",
    computeDevice: "Compute device", autoSelect: "Automatic", deviceHelp: "Prefer GPU and fall back to CPU if the runtime is unavailable.",
    systemDevice: "Computer audio device", gameVideoOutput: "Game and video output", autoSpeaker: "Automatically use the current speaker",
    systemAudioHelp: "Captures audio currently playing in Windows. Stereo Mix is not required.",
    offlineTranslationModel: "Offline translation models", repair: "Repair", cacheManagement: "Cache management",
    cachePreserve: "Downloaded models and subtitles are kept", calculating: "Calculating…", cacheItems: "Temporary audio, web cache, and old logs",
    clearCache: "Clear cache", applySettings: "Apply settings", about: "About", version: "Version", loading: "Loading…",
    runtimeLocal: "Local desktop processing · Free", runtimeWeb: "Local processing · Free",
    translationSuffix: " translation", currentLanguage: "current language", autoDetectShort: "Auto detect ZH/JA/EN",
    translationReady: "Installed · Available offline", translationBroken: "Bundled model is incomplete",
    microphone: "Microphone", systemAudio: "Computer audio", bothAudio: "Microphone + computer", sound: "Audio",
    requestFailed: "Request failed ({status})", currentLatest: "Current {current} → Latest {latest}", defaultReleaseNotes: "Bug fixes and stability improvements.",
    downloading: "Downloading…", installNow: "Install now", verifiedDownload: "Download complete and SHA-256 verified", retryDownload: "Download again",
    updateFailedContinue: "The update download failed. You can keep using the current version.", startingInstaller: "Starting installer…", cannotStartUpdate: "Could not start the update.", downloadingAction: "Downloading…",
    installed: "{model} installed{bundled}", bundled: " · Bundled", localModel: "Local model: about {size}. It will not be downloaded again when selected.",
    modelDownloading: "Downloading {model} · {progress}%", resumeDownload: "{done} / {total} · {source} · Resumable", connectingSource: "Connecting to a download source",
    modelIncomplete: "{model} download incomplete", applyRetry: "Click Apply settings to retry", modelMissing: "{model} is not downloaded",
    firstDownload: "The first selection downloads about {size} and keeps it locally", modelStatusFailed: "Could not read model status", modelDownloadFailed: "{model} model download failed.",
    miniDesktopOnly: "Mini overlay is only available in the desktop app.", miniOpenFailed: "Could not open the mini overlay.", cleanable: "Can clear {size}", none: "None",
    downloadedModels: "Downloaded models: {models} ({size}, kept)", cacheStatusFailed: "Could not read cache status", stopBeforeClear: "Stop interpreting and wait for the current segment before clearing cache.",
    clearing: "Clearing…", released: "Released {size}", cacheKeptRestart: "Downloaded models, settings, and subtitles were kept. Restart to finish clearing the web cache.",
    cacheKept: "Downloaded models, settings, and subtitles were kept.", cacheCleared: "Cache cleared. Released {size}; downloaded models were not deleted.", clearFailed: "Clear failed: {error}",
    unknown: "Unknown", noNvidia: "No NVIDIA GPU detected", availableRam: " · {ram} GB available", gpuReady: "GPU ready", cpuFallback: "CPU fallback",
    cudaReady: "CUDA is ready. Recommended: {model} / GPU.", cudaIncomplete: "An NVIDIA GPU was detected, but CUDA 12 / cuDNN 9 is incomplete. Automatic mode will use CPU.",
    statusFailed: "Could not read engine status: {error}", defaultPrefix: "Default · ", devicesFound: "Found {count} Windows output device(s). Capturing locally with WASAPI.",
    noAudioDevice: "No computer audio device was found.", audioComponentFailed: "Computer audio is unavailable: {error}", stillListening: "Still listening · Previous segment failed",
    processingFailed: "Processing failed", sessionEnded: "Interpretation ended", translationUnavailable: "The bundled translation model is unavailable. Reinstall YiSheng.",
    translationModelUnavailable: "Translation model unavailable", systemAudioReadFailed: "Computer audio read failed ({status})", systemAudioInterrupted: "Computer audio capture stopped",
    micHint: "Only listens to you · Choose computer audio for games or videos", systemHint: "Recommended · Captures games, videos, and podcasts directly", bothHint: "Listen to both audio sources",
    microphoneAdvice: "For games, videos, or podcasts, choose Computer audio. Microphone is intended for direct speech.", stopInterpreting: "Stop interpreting", interpreting: "Interpreting",
    lowLatency: "Low-latency interpretation · {source}", micPermission: "Microphone permission is required.", audioStartFailed: "Could not start audio: {error}", finishingLast: "Finishing the last segment",
    exportTitle: "YiSheng · Live interpretation transcript", exportTime: "Exported: {time}", originalLine: "[{index}] Original ({source} · {language})", untranslated: "[Not translated]",
    savedTo: "Saved to: {path}", saveFailed: "Could not save the file.", desktopExportFailed: "Desktop export failed: {error}", stopBeforeModel: "Stop the current session before switching models.",
    checkingModel: "Checking model…", settingsApplied: "Settings applied. The model will load on the next recognition request.", checking: "Checking…", checkingLocalModel: "Checking bundled models",
    translationChecked: "{source} → {target} translation model checked.", offlinePackageMissing: "Offline model package missing", install: "Install",
  },
};

function tr(key) {
  return UI_TEXT[state?.uiLanguage || INITIAL_UI_LANGUAGE]?.[key] || UI_TEXT.zh[key] || key;
}

function tf(key, values = {}) {
  return tr(key).replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? ""));
}

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
  languageToggle: $("#languageToggle"),
  languageToggleLabel: $("#languageToggleLabel"),
  languageChoices: [...document.querySelectorAll("[data-ui-language]")],
  languageSelect: $("#languageSelect"),
  targetLanguageSelect: $("#targetLanguageSelect"),
  translationColumnLabel: $("#translationColumnLabel"),
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
  uiLanguage: INITIAL_UI_LANGUAGE,
  recording: false,
  stream: null,
  audioContext: null,
  sourceNode: null,
  captureNode: null,
  silentGain: null,
  buffers: [],
  bufferedFrames: 0,
  sampleRate: 48000,
  chunkSeconds: 1.8,
  overlapSeconds: 0.5,
  captureChunkSeconds: 1.8,
  captureOverlapSeconds: 0.5,
  queue: [],
  processing: false,
  segments: [],
  status: null,
  fallbackProcessor: null,
  captureLanguage: "en",
  captureTarget: "zh",
  captureMode: "microphone",
  systemAudioActive: false,
  systemPollController: null,
  systemDevices: [],
  updatePollTimer: null,
  updateReady: false,
  whisperModels: null,
};

const languageNameSets = {
  zh: { auto: "自动识别", en: "英语", ja: "日语", ko: "韩语", fr: "法语", de: "德语", es: "西班牙语", ru: "俄语", pt: "葡萄牙语", it: "意大利语", zh: "中文" },
  en: { auto: "Auto detect", en: "English", ja: "Japanese", ko: "Korean", fr: "French", de: "German", es: "Spanish", ru: "Russian", pt: "Portuguese", it: "Italian", zh: "Chinese" },
};
const languageNames = { ...languageNameSets[state.uiLanguage] };
const audioSourceNames = state.uiLanguage === "en"
  ? { microphone: "Microphone", system: "Computer audio", both: "Microphone + computer" }
  : { microphone: "麦克风", system: "电脑声音", both: "麦克风 + 电脑" };

function applyUiLanguage() {
  const locale = state.uiLanguage === "en" ? "en" : "zh";
  document.documentElement.lang = locale === "en" ? "en" : "zh-CN";
  document.title = tr("pageTitle");
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = tr(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((node) => {
    node.setAttribute("aria-label", tr(node.dataset.i18nAria));
  });
  document.querySelectorAll("[data-i18n-title]").forEach((node) => {
    node.setAttribute("title", tr(node.dataset.i18nTitle));
  });
  elements.languageToggleLabel.textContent = locale === "en" ? "EN / 中" : "中 / EN";
  elements.languageChoices.forEach((button) => button.classList.toggle("active", button.dataset.uiLanguage === locale));
  Object.keys(languageNames).forEach((key) => delete languageNames[key]);
  Object.assign(languageNames, languageNameSets[locale]);
  Object.assign(audioSourceNames, locale === "en"
    ? { microphone: tr("microphone"), system: tr("systemAudio"), both: tr("bothAudio") }
    : { microphone: tr("microphone"), system: tr("systemAudio"), both: tr("bothAudio") });
  if (state.status) {
    refreshTranslationState();
    renderWhisperModelStatus();
  }
  updateSourceHint();
  if (state.recording) {
    elements.recordLabel.textContent = tr("interpreting");
    elements.recordButton.setAttribute("aria-label", tr("stopInterpreting"));
    setSessionState(tf("lowLatency", { source: audioSourceNames[state.captureMode] }), true);
  } else {
    elements.recordLabel.textContent = tr("startInterpreting");
    elements.recordButton.setAttribute("aria-label", tr("startInterpreting"));
  }
  const runtimeLabel = $("#runtimeLabel");
  if (runtimeLabel) runtimeLabel.textContent = window.pywebview?.api ? tr("runtimeLocal") : tr("runtimeWeb");
  if (window.pywebview?.api?.set_ui_language) {
    window.pywebview.api.set_ui_language(locale).catch(() => {});
  }
}

function setUiLanguage(language) {
  state.uiLanguage = language === "en" ? "en" : "zh";
  localStorage.setItem("yisheng-ui-language", state.uiLanguage);
  applyUiLanguage();
}

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
  if (!response.ok) throw new Error(payload?.detail || tf("requestFailed", { status: response.status }));
  return payload;
}

function hideUpdateDialog() {
  elements.updateOverlay.hidden = true;
  if (state.updatePollTimer) window.clearInterval(state.updatePollTimer);
  state.updatePollTimer = null;
}

function showUpdateDialog(result) {
  elements.updateVersion.textContent = tf("currentLatest", { current: result.current_version, latest: result.latest_version });
  elements.updateNotes.textContent = result.notes || tr("defaultReleaseNotes");
  elements.updateError.hidden = true;
  elements.updateProgress.hidden = true;
  elements.updateActionButton.disabled = false;
  elements.updateActionButton.textContent = tr("downloadUpdate");
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
    : `${progress}% · ${tr("downloading")}`;
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
      elements.updateActionButton.textContent = tr("installNow");
      elements.updateProgressText.textContent = tr("verifiedDownload");
    } else if (result.status === "error") {
      window.clearInterval(state.updatePollTimer);
      state.updatePollTimer = null;
      elements.updateActionButton.disabled = false;
      elements.updateActionButton.textContent = tr("retryDownload");
      elements.updateError.textContent = result.error || tr("updateFailedContinue");
      elements.updateError.hidden = false;
    }
  } catch {
    // A later poll can recover from a momentary local request failure.
  }
}

async function handleUpdateAction() {
  if (state.updateReady) {
    elements.updateActionButton.disabled = true;
    elements.updateActionButton.textContent = tr("startingInstaller");
    try {
      const result = await window.pywebview.api.install_update();
      if (!result.ok) throw new Error(result.error || tr("cannotStartUpdate"));
    } catch (error) {
      elements.updateActionButton.disabled = false;
      elements.updateActionButton.textContent = tr("installNow");
      elements.updateError.textContent = error.message;
      elements.updateError.hidden = false;
    }
    return;
  }

  elements.updateError.hidden = true;
  elements.updateActionButton.disabled = true;
  elements.updateActionButton.textContent = tr("downloadingAction");
  try {
    const result = await api("/api/update/download", { method: "POST" });
    renderUpdateProgress(result);
    if (state.updatePollTimer) window.clearInterval(state.updatePollTimer);
    state.updatePollTimer = window.setInterval(pollUpdateDownload, 700);
  } catch (error) {
    elements.updateActionButton.disabled = false;
    elements.updateActionButton.textContent = tr("retryDownload");
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
    elements.modelDownloadTitle.textContent = tf("installed", { model: label, bundled: info.bundled ? tr("bundled") : "" });
    elements.modelDownloadDetail.textContent = tf("localModel", { size: formatBytes(info.total_bytes) });
  } else if (info.status === "downloading") {
    elements.modelDownloadTitle.textContent = tf("modelDownloading", { model: label, progress: info.progress || 0 });
    elements.modelDownloadDetail.textContent = tf("resumeDownload", { done: formatBytes(info.downloaded_bytes), total: formatBytes(info.total_bytes), source: info.source || tr("connectingSource") });
  } else if (info.status === "error") {
    elements.modelDownloadTitle.textContent = tf("modelIncomplete", { model: label });
    elements.modelDownloadDetail.textContent = info.error || tr("applyRetry");
  } else {
    elements.modelDownloadTitle.textContent = tf("modelMissing", { model: label });
    elements.modelDownloadDetail.textContent = tf("firstDownload", { size: formatBytes(info.total_bytes) });
  }
}

async function loadWhisperModels() {
  try {
    state.whisperModels = await api("/api/models/whisper/status");
    renderWhisperModelStatus();
  } catch (error) {
    elements.modelDownloadTitle.textContent = tr("modelStatusFailed");
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
    elements.saveSettingsButton.textContent = tf("modelDownloading", { model: modelLabels[model] || model, progress: info.progress || 0 });
    await new Promise((resolve) => window.setTimeout(resolve, 600));
    info = await api(`/api/models/whisper/${model}/status`);
  }
  state.whisperModels = { ...(state.whisperModels || {}), [model]: info };
  renderWhisperModelStatus();
  if (!info.installed) throw new Error(info.error || tf("modelDownloadFailed", { model: modelLabels[model] || model }));
  return info;
}

async function openMiniOverlay() {
  if (!window.pywebview?.api?.show_overlay) {
    toast(tr("miniDesktopOnly"), "error");
    return;
  }
  try {
    const result = await window.pywebview.api.show_overlay();
    if (!result.ok) throw new Error(result.error || tr("miniOpenFailed"));
  } catch (error) {
    toast(error.message, "error");
  }
}

async function loadCacheStatus() {
  try {
    const result = await api("/api/cache/status");
    elements.cacheStatus.textContent = tf("cleanable", { size: formatBytes(result.cache_bytes) });
    const models = result.installed_models?.length ? result.installed_models.join(state.uiLanguage === "en" ? ", " : "、") : tr("none");
    elements.cacheDetail.textContent = tf("downloadedModels", { models, size: formatBytes(result.model_bytes) });
  } catch (error) {
    elements.cacheStatus.textContent = tr("cacheStatusFailed");
    elements.cacheDetail.textContent = error.message;
  }
}

async function clearAppCache() {
  if (state.recording || state.processing) {
    toast(tr("stopBeforeClear"), "error");
    return;
  }
  elements.clearCacheButton.disabled = true;
  elements.clearCacheButton.textContent = tr("clearing");
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
    elements.cacheStatus.textContent = tf("released", { size: formatBytes(result.removed_bytes) });
    elements.cacheDetail.textContent = result.restart_required
      ? tr("cacheKeptRestart")
      : tr("cacheKept");
    toast(tf("cacheCleared", { size: formatBytes(result.removed_bytes) }), "info", 6500);
  } catch (error) {
    toast(tf("clearFailed", { error: error.message }), "error", 6500);
    await loadCacheStatus();
  } finally {
    elements.clearCacheButton.disabled = false;
    elements.clearCacheButton.textContent = tr("clearCache");
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
  const target = elements.targetLanguageSelect.value;
  const pairs = state.status.translation_pairs || [];
  const sources = source === "auto" ? ["zh", "ja", "en"] : [source];
  const ready = sources.every((item) => item === target || pairs.includes(`${item}-${target}`));
  const sourceLabel = source === "auto" ? tr("autoDetectShort") : (languageNames[source] || tr("currentLanguage"));
  const targetLabel = languageNames[target] || target;
  elements.translationDetail.textContent = `${sourceLabel} → ${targetLabel}`;
  elements.translationStatus.textContent = ready ? tr("translationReady") : tr("translationBroken");
  elements.installTranslationButton.hidden = ready || source === "auto" || source === target;
  if (elements.translationColumnLabel) elements.translationColumnLabel.textContent = `${targetLabel}${tr("translationSuffix")}`;
}

function realtimeChunkSeconds(engine, recommended) {
  const model = engine?.model || "base";
  const gpu = engine?.active_device === "cuda";
  // Larger models need a little more audio per request on ordinary CPUs, or
  // inference can fall behind real time. Base remains deliberately aggressive
  // because it is the bundled/default model used by most people.
  const cpuSeconds = { tiny: 1.4, base: 1.8, small: 2.4, medium: 3.2 };
  const gpuSeconds = { tiny: 1.2, base: 1.4, small: 1.7, medium: 2.2 };
  const selected = (gpu ? gpuSeconds : cpuSeconds)[model];
  return Number(selected || recommended?.chunk_seconds || 1.8);
}

async function loadStatus() {
  try {
    state.status = await api("/api/status");
    const { hardware, recommended, engine } = state.status;
    state.chunkSeconds = realtimeChunkSeconds(engine, recommended);
    const version = state.status.version || tr("unknown");
    if (elements.appVersion) elements.appVersion.textContent = `${tr("version")} ${version}`;
    if (elements.aboutVersion) elements.aboutVersion.textContent = version;
    const repository = state.status.app_info?.repository;
    if (repository && elements.officialRepository) {
      elements.officialRepository.href = repository;
      elements.officialRepository.textContent = repository.replace(/^https?:\/\//, "");
    }
    elements.modelSelect.value = engine.model;
    renderWhisperModelStatus();
    elements.deviceSelect.value = engine.requested_device;
    elements.gpuName.textContent = hardware.gpu || tr("noNvidia");
    const availableRam = hardware.available_ram_gb ? tf("availableRam", { ram: hardware.available_ram_gb }) : "";
    elements.hardwareMeta.textContent = `${hardware.cpu} · ${hardware.ram_gb || "?"} GB RAM${availableRam}`;
    elements.hardwareState.textContent = hardware.cuda_runtime_ready ? tr("gpuReady") : tr("cpuFallback");
    elements.hardwareState.style.color = hardware.cuda_runtime_ready ? "var(--lime)" : "#f3c969";
    elements.deviceHelp.textContent = hardware.cuda_runtime_ready
      ? tf("cudaReady", { model: recommended.model })
      : tr("cudaIncomplete");
    refreshTranslationState();
  } catch (error) {
    toast(tf("statusFailed", { error: error.message }), "error");
  }
}

async function loadSystemAudioDevices() {
  try {
    const result = await api("/api/audio/system/devices");
    state.systemDevices = result.devices || [];
    elements.systemDeviceSelect.innerHTML = `<option value="">${tr("autoSpeaker")}</option>`;
    for (const device of state.systemDevices) {
      const option = document.createElement("option");
      option.value = String(device.index);
      option.textContent = `${device.default ? tr("defaultPrefix") : ""}${device.name}`;
      elements.systemDeviceSelect.append(option);
    }

    const savedDevice = localStorage.getItem("yisheng-system-device") || "";
    if ([...elements.systemDeviceSelect.options].some((item) => item.value === savedDevice)) {
      elements.systemDeviceSelect.value = savedDevice;
    }
    const available = Boolean(result.available && state.systemDevices.length);
    elements.systemDeviceSelect.disabled = !available;
    elements.systemAudioHelp.textContent = available
      ? tf("devicesFound", { count: state.systemDevices.length })
      : (result.error || tr("noAudioDevice"));
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
    elements.systemAudioHelp.textContent = tf("audioComponentFailed", { error: error.message });
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
  if (state.bufferedFrames >= state.sampleRate * state.captureChunkSeconds) flushAudio(false);
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
    const overlapFrames = Math.min(combined.length, Math.floor(state.sampleRate * state.captureOverlapSeconds));
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
    const confidentAutoLanguage = source === "auto"
      && ["zh", "ja", "en"].includes(previous?.language)
      && Number(previous?.language_probability || 0) >= .7
      && (Date.now() - Number(previous?._receivedAt || 0)) < 4200;
    const requestLanguage = confidentAutoLanguage ? previous.language : source;
    const sameLanguage = requestLanguage !== "auto" && previous?.language === requestLanguage;
    const sameTarget = previous?.target_language === state.captureTarget;
    // Short Whisper windows sometimes add a full stop even while somebody is
    // still speaking. Treat nearby chunks from the same stream as one rolling
    // utterance so the existing row and its translation can be revised with
    // the newly heard words. A long pause or 180 characters starts a new row.
    const recent = previous && (Date.now() - Number(previous._receivedAt || 0)) < 4200;
    const context = sameStream && sameTarget && sameLanguage && recent && previous.original.length <= 180
      ? previous.original
      : "";
    const result = await api(`/api/transcribe?language=${encodeURIComponent(requestLanguage)}&target=${encodeURIComponent(state.captureTarget)}&duration=${chunk.duration.toFixed(2)}&context=${encodeURIComponent(context)}`, {
      method: "POST",
      headers: { "Content-Type": "audio/wav" },
      body: chunk.blob,
    });
    result.audio_source = chunk.audioSource || "microphone";
    result._receivedAt = Date.now();
    if (source === "auto" && ["ja", "en"].includes(result.language) && result.language_probability >= .7) {
      const autoJapanese = result.language === "ja";
      state.captureChunkSeconds = Math.max(state.chunkSeconds, autoJapanese ? 3.2 : 2.8);
      state.captureOverlapSeconds = Math.max(state.overlapSeconds, autoJapanese ? .8 : .7);
    }
    if (result.original) appendSegment(result);
    if (result.warning) toast(result.warning, result.translation_ready ? "info" : "error", 6500);
  } catch (error) {
    toast(error.message, "error", 6500);
    setSessionState(state.recording ? tr("stillListening") : tr("processingFailed"), state.recording);
  } finally {
    state.processing = false;
    elements.thinkingRow.hidden = state.queue.length === 0;
    if (state.queue.length) processQueue();
    else if (!state.recording) setSessionState(tr("sessionEnded"), false);
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
    const cjkTarget = ["ja", "zh"].includes(result.target_language);
    result.translation = cjkTarget
      ? trimCharacterOverlap(sameSource && previous?.target_language === result.target_language ? previous.translation : "", result.translation)
      : trimWordOverlap(sameSource && previous?.target_language === result.target_language ? previous.translation : "", result.translation);
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
    : `<p>${escapeHtml(tr("translationUnavailable"))}</p>`;
  item.innerHTML = `
    <div class="transcript-cell original">
      <p>${escapeHtml(result.original)}</p>
      <div class="transcript-meta"><span>${timestamp}</span><span>${audioSourceNames[result.audio_source] || tr("sound")}</span><span>${languageNames[result.language] || result.language}</span><span class="confidence">${confidence}</span></div>
    </div>
    <div class="transcript-cell translation ${result.translation_ready ? "" : "missing"}" data-target-language="${escapeHtml(languageNames[result.target_language] || result.target_language)}">
      ${translatedContent}
      <div class="transcript-meta"><span>${languageNames[result.target_language] || result.target_language}</span><span>${result.model}</span><span>${result.device.toUpperCase()}</span><span>${result.latency_ms} ms</span></div>
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
      translation: result.translation_ready ? result.translation : tr("translationModelUnavailable"),
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
        let detail = tf("systemAudioReadFailed", { status: response.status });
        try { detail = (await response.json()).detail || detail; } catch { /* no-op */ }
        throw new Error(detail);
      }
      const duration = Number(response.headers.get("X-Audio-Duration")) || state.captureChunkSeconds;
      const level = Number(response.headers.get("X-Audio-Level")) || 0;
      const blob = await response.blob();
      updateLevelMeter(level);
      state.queue.push({ blob, duration, language: state.captureLanguage, audioSource: "system" });
      processQueue();
    } catch (error) {
      if (error.name === "AbortError" || !state.systemAudioActive) break;
      state.systemAudioActive = false;
      toast(error.message, "error", 6500);
      setSessionState(tr("systemAudioInterrupted"), false);
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
      chunk_seconds: state.captureChunkSeconds,
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
    microphone: tr("micHint"),
    system: tr("systemHint"),
    both: tr("bothHint"),
  };
  elements.recordHint.textContent = hints[elements.audioSourceSelect.value] || hints.microphone;
}

async function startRecording() {
  state.captureLanguage = elements.languageSelect.value;
  state.captureTarget = elements.targetLanguageSelect.value;
  state.captureMode = elements.audioSourceSelect.value;
  const japaneseCapture = state.captureLanguage === "ja";
  const englishCapture = state.captureLanguage === "en";
  state.captureChunkSeconds = japaneseCapture
    ? Math.max(state.chunkSeconds, 3.2)
    : englishCapture ? Math.max(state.chunkSeconds, 2.8) : state.chunkSeconds;
  state.captureOverlapSeconds = japaneseCapture
    ? Math.max(state.overlapSeconds, .8)
    : englishCapture ? Math.max(state.overlapSeconds, .7) : state.overlapSeconds;
  state.recording = true;
  state.buffers = [];
  state.bufferedFrames = 0;
  try {
    if (state.captureMode === "microphone") {
      toast(tr("microphoneAdvice"), "info", 7000);
    }
    if (state.captureMode === "microphone" || state.captureMode === "both") {
      await startMicrophoneCapture();
    }
    if (state.captureMode === "system" || state.captureMode === "both") {
      await startSystemAudioCapture();
    }

    elements.recordButton.classList.add("recording");
    elements.recordButton.setAttribute("aria-label", tr("stopInterpreting"));
    elements.recordLabel.textContent = tr("interpreting");
    elements.recordHint.textContent = audioSourceNames[state.captureMode];
    elements.levelBars.classList.add("active");
    elements.languageSelect.disabled = true;
    elements.targetLanguageSelect.disabled = true;
    elements.audioSourceSelect.disabled = true;
    elements.systemDeviceSelect.disabled = true;
    setSessionState(tf("lowLatency", { source: audioSourceNames[state.captureMode] }), true);
  } catch (error) {
    state.recording = false;
    await stopCaptureResources();
    const permissionDenied = error.name === "NotAllowedError";
    toast(permissionDenied ? tr("micPermission") : tf("audioStartFailed", { error: error.message }), "error", 6500);
  }
}

async function stopRecording() {
  state.recording = false;
  if (state.captureMode === "microphone" || state.captureMode === "both") flushAudio(true);
  state.buffers = [];
  state.bufferedFrames = 0;
  await stopCaptureResources();
  elements.recordButton.classList.remove("recording");
  elements.recordButton.setAttribute("aria-label", tr("startInterpreting"));
  elements.recordLabel.textContent = tr("startInterpreting");
  elements.levelBars.classList.remove("active");
  elements.languageSelect.disabled = false;
  elements.targetLanguageSelect.disabled = false;
  elements.audioSourceSelect.disabled = false;
  elements.systemDeviceSelect.disabled = state.systemDevices.length === 0;
  updateSourceHint();
  setSessionState(state.processing || state.queue.length ? tr("finishingLast") : tr("sessionEnded"), false);
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
  const locale = state.uiLanguage === "en" ? "en-US" : "zh-CN";
  const lines = [tr("exportTitle"), tf("exportTime", { time: new Date().toLocaleString(locale) }), ""];
  state.segments.forEach((segment, index) => {
    const source = audioSourceNames[segment.audio_source] || tr("sound");
    lines.push(tf("originalLine", { index: index + 1, source, language: languageNames[segment.language] || segment.language }));
    lines.push(segment.original);
    lines.push(languageNames[segment.target_language] || segment.target_language || tr("translationSuffix"));
    lines.push(segment.translation || tr("untranslated"));
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
      if (result.ok) toast(tf("savedTo", { path: result.path }));
      else if (!result.cancelled) toast(result.error || tr("saveFailed"), "error");
    } catch (error) {
      toast(tf("desktopExportFailed", { error: error.message }), "error");
    }
    return;
  }
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  const filenamePrefix = state.uiLanguage === "en" ? "YiSheng_Transcript" : "译声同传";
  link.download = `${filenamePrefix}_${new Date().toISOString().slice(0, 19).replaceAll(":", "-")}.txt`;
  link.click();
  URL.revokeObjectURL(link.href);
}

async function saveSettings() {
  if (state.recording) {
    toast(tr("stopBeforeModel"), "error");
    return;
  }
  elements.saveSettingsButton.disabled = true;
  elements.clearCacheButton.disabled = true;
  elements.saveSettingsButton.textContent = tr("checkingModel");
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
    toast(tr("settingsApplied"));
    await loadStatus();
    closeSettings();
  } catch (error) {
    toast(error.message, "error");
  } finally {
    elements.saveSettingsButton.disabled = false;
    elements.clearCacheButton.disabled = false;
    elements.saveSettingsButton.textContent = tr("applySettings");
  }
}

async function installTranslation() {
  const source = elements.languageSelect.value;
  const target = elements.targetLanguageSelect.value;
  elements.installTranslationButton.disabled = true;
  elements.installTranslationButton.textContent = tr("checking");
  elements.translationStatus.textContent = tr("checkingLocalModel");
  try {
    const result = await api(`/api/models/translation/${source}?target=${encodeURIComponent(target)}`, { method: "POST" });
    state.status.translation_pairs = result.pairs;
    refreshTranslationState();
    toast(tf("translationChecked", { source: languageNames[source] || source, target: languageNames[target] || target }));
  } catch (error) {
    elements.translationStatus.textContent = tr("offlinePackageMissing");
    toast(error.message, "error", 7000);
  } finally {
    elements.installTranslationButton.disabled = false;
    elements.installTranslationButton.textContent = tr("install");
  }
}

elements.recordButton.addEventListener("click", () => state.recording ? stopRecording() : startRecording());
elements.languageToggle.addEventListener("click", () => setUiLanguage(state.uiLanguage === "zh" ? "en" : "zh"));
elements.languageChoices.forEach((button) => button.addEventListener("click", () => setUiLanguage(button.dataset.uiLanguage)));
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
elements.targetLanguageSelect.addEventListener("change", () => {
  localStorage.setItem("yisheng-target-language", elements.targetLanguageSelect.value);
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
  if (runtimeLabel) runtimeLabel.textContent = tr("runtimeLocal");
  try {
    const info = await window.pywebview.api.get_app_info();
    document.documentElement.dataset.desktopVersion = info.version || "";
    if (elements.appVersion && info.version) elements.appVersion.textContent = `${tr("version")} ${info.version}`;
    if (window.pywebview?.api?.set_ui_language) await window.pywebview.api.set_ui_language(state.uiLanguage);
  } catch { /* Desktop bridge status is non-critical. */ }
});

createLevelBars();
const savedLanguage = localStorage.getItem("yisheng-language");
if (savedLanguage && [...elements.languageSelect.options].some((item) => item.value === savedLanguage)) {
  elements.languageSelect.value = savedLanguage;
}
const savedTargetLanguage = localStorage.getItem("yisheng-target-language");
if (savedTargetLanguage && [...elements.targetLanguageSelect.options].some((item) => item.value === savedTargetLanguage)) {
  elements.targetLanguageSelect.value = savedTargetLanguage;
}
const savedAudioSource = localStorage.getItem("yisheng-audio-source");
if (savedAudioSource && [...elements.audioSourceSelect.options].some((item) => item.value === savedAudioSource)) {
  elements.audioSourceSelect.value = savedAudioSource;
}
updateSourceHint();
applyUiLanguage();

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
