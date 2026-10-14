const $ = (selector) => document.querySelector(selector);
const { enqueueLatest, recognitionPlan, MicrophoneSegmenter } = window.YishengAudioSession;

const INITIAL_UI_LANGUAGE = localStorage.getItem("yisheng-ui-language") === "en" ? "en" : "zh";
const UI_TEXT = {
  zh: {
    pageTitle: "译声 · 本地同声传译", brandHome: "译声首页", versionLoading: "版本读取中…",
    switchLanguage: "切换中文或英文界面", openMini: "打开迷你置顶字幕", miniTitle: "迷你置顶字幕",
    miniSubtitle: "迷你字幕", openSettings: "打开设置", settings: "设置", ready: "准备就绪",
    heroLead: "听见原声，", heroAccent: "即刻读懂。", heroCopy: "语音始终在本机识别。默认离线翻译，也可在设置中自选 API 翻译文字。",
    latency: "处理延迟", recognizedLanguage: "识别语言", segments: "片段", original: "原文",
    clearHistory: "清空记录", waitingVoice: "等待你的声音", startHelp: "选择原语言和翻译目标，然后点击下方按钮开始同传",
    processing: "正在识别与翻译…", sourceLanguage: "原语言", autoLanguages: "自动识别（中文/日语/英语/韩语）",
    chinese: "中文", english: "英语", japanese: "日语", korean: "韩语", translateTo: "翻译为", audioSource: "声音来源",
    microphoneOption: "麦克风（面对电脑说话）", systemOption: "电脑声音（游戏/视频推荐）", bothOption: "麦克风 + 电脑",
    startInterpreting: "开始同传", clickMicrophone: "点击开启麦克风", exportText: "导出文本",
    updateAvailable: "新版本可用", updateTitle: "译声可以更新", readingVersion: "正在读取版本信息…",
    prepareDownload: "准备下载…", later: "稍后提醒", downloadUpdate: "下载更新",
    updateSafe: "更新包通过 HTTPS 下载并进行 SHA-256 完整性校验。", localOptimization: "本机优化",
    runtimeSettings: "运行设置", closeSettings: "关闭设置", detectingHardware: "正在检测硬件…",
    pleaseWait: "请稍候", detecting: "检测中", interfaceLanguage: "界面语言", languageHint: "也可点击顶部 🌐 切换",
    recognitionModel: "识别模型", modelTradeoff: "Base 低占用；Small 更准但更吃 CPU，不能修正翻译模型的错译",
    tinyOption: "Tiny · 极速 / 首次选择下载约 75 MB", baseOption: "Base · 已内置 / 性能均衡",
    smallOption: "Small · 更准确 / 首次选择下载约 484 MB", mediumOption: "Medium · 高准确度 / 首次选择下载约 1.53 GB",
    baseBundled: "Base 已内置", modelDownloadHelp: "选择其他模型后，点击“应用设置”开始下载",
    computeDevice: "计算设备", autoSelect: "自动（游戏优先）", deviceHelp: "自动模式使用低占用 CPU，为游戏保留显卡；需要更快识别时可手动选择 GPU。",
    systemDevice: "电脑声音设备", gameVideoOutput: "游戏与视频输出", autoSpeaker: "自动选择当前扬声器",
    systemAudioHelp: "自动捕获 Windows 正在播放的声音，不需要打开“立体声混音”。",
    offlineTranslationModel: "离线互译模型", repair: "修复", cacheManagement: "缓存管理",
    cachePreserve: "保留已下载模型与字幕", calculating: "正在计算…", cacheItems: "临时音频、网页缓存与旧日志",
    clearCache: "清理缓存", applySettings: "应用设置", about: "关于", version: "版本", loading: "读取中…",
    runtimeLocal: "桌面本地处理 · 免费", runtimeWeb: "本地处理 · 免费",
    translationSuffix: "翻译", currentLanguage: "当前语言", autoDetectShort: "自动识别中/日/英/韩",
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
    clearing: "清理中…", released: "已释放 {size}", releasedRestart: "已释放 {size} · 重启再释放 {pending}", cachePartial: "已释放 {size}，{count} 项被占用，可稍后重试", cacheKeptRestart: "常驻模型内存已释放；已下载模型、设置和字幕均保留，重启后完成网页缓存清理。",
    cacheKept: "常驻模型内存已释放；已下载模型、设置和字幕均已保留。", cacheCleared: "缓存清理完成，释放 {size}。已下载模型不会被删除。", cacheClearedRestart: "已立即释放 {size}，重启后再释放网页缓存 {pending}。已下载模型不会被删除。", clearFailed: "清理失败：{error}",
    unknown: "未知", noNvidia: "未检测到 NVIDIA 显卡", availableRam: " · 可用 {ram} GB", gpuReady: "GPU 可选", cpuFallback: "低占用 CPU",
    cudaReady: "CUDA 已就绪；自动模式使用低占用 CPU，为游戏保留显卡。需要更快识别可手动选择 GPU。", cudaIncomplete: "检测到显卡，但 CUDA 12 / cuDNN 9 运行库不完整；自动模式使用低占用 CPU。",
    statusFailed: "无法读取引擎状态：{error}", defaultPrefix: "默认 · ", devicesFound: "已检测到 {count} 个 Windows 输出设备，使用 WASAPI 本地捕获。",
    noAudioDevice: "没有检测到可用的电脑声音设备。", audioComponentFailed: "电脑声音组件不可用：{error}", stillListening: "仍在监听 · 上一片段失败",
    audioNotStarted: "声音未启动 · 请检查声音设备后重试", deviceDisconnected: "未连接 · {name}",
    processingFailed: "处理失败", sessionEnded: "本次同传已结束", translationUnavailable: "内置翻译模型不可用，请重新安装译声。",
    translationModelUnavailable: "翻译模型不可用", systemAudioReadFailed: "电脑声音读取失败 ({status})", systemAudioInterrupted: "电脑声音监听已中断",
    micHint: "只听本人说话 · 游戏/视频请选电脑声音", systemHint: "按停顿成句 · 已知游戏语言时请明确选择原语言", bothHint: "同时监听两路声音 · 计算量更大",
    microphoneAdvice: "翻译游戏、视频或播客时请改选“电脑声音”；麦克风只适合直接说话。", stopInterpreting: "停止同传", interpreting: "正在同传", preparingEngine: "正在准备本地语音模型…",
    lowLatency: "按停顿成句 · {source}", micPermission: "需要允许麦克风权限才能监听麦克风。", audioStartFailed: "声音启动失败：{error}", finishingLast: "正在完成最后片段",
    audioBehind: "当前算力跟不上，已跳过积压音频并转到最新内容。建议使用 Base 和单一音源，或降低游戏负载。",
    exportTitle: "译声 · 同声传译记录", exportTime: "导出时间：{time}", originalLine: "[{index}] 原文（{source} · {language}）", untranslated: "[未翻译]",
    savedTo: "已保存到：{path}", saveFailed: "保存失败。", desktopExportFailed: "桌面导出失败：{error}", stopBeforeModel: "请先停止当前同传，再切换模型。",
    checkingModel: "检查模型中…", settingsApplied: "运行设置已应用。模型会在下次识别时加载。", checking: "检查中…", checkingLocalModel: "正在检查本地模型",
    translationChecked: "{source} → {target} 翻译模型检查完成。", offlinePackageMissing: "缺少离线模型包", install: "安装",
    translationMode: "翻译方式", localTranslationOption: "本地翻译 · 离线免费", apiTranslationOption: "API 翻译 · 自备服务",
    translationModeHelp: "每次启动默认本地模式。选择后点击“应用设置”才会生效；本地识别模型仍会使用。",
    readingMode: "正在读取翻译模式…", localModeActive: "已生效：本地离线翻译", apiModeActive: "已生效：API 翻译 · 文字发送至自选服务",
    apiRuntime: "本地识别 + API 翻译", apiBaseUrl: "服务地址（Base URL）", apiModel: "服务方模型名称", apiKey: "API 密钥",
    apiBaseUrlHelp: "仅支持 Chat Completions 兼容服务。填写服务方的完整 Base URL（常见以 /v1 结尾），也可填写完整 /chat/completions 地址。远程服务需要 HTTPS。",
    apiKeyRequired: "请输入密钥，或明确勾选“此服务不需要密钥”。更换服务地址或模型后需要重新填写。",
    apiKeyReuse: "此地址和模型已配置密钥；留空可沿用本次运行的密钥，输入新密钥可替换。",
    apiNoKey: "此服务不需要密钥（例如本机服务）", apiKeyMemory: "API 配置仅供本次运行使用，不保存到磁盘；切回本地会清除后台密钥，退出后需重新配置。",
    apiConsent: "我同意将识别后的文字发送到上述服务，可能产生费用；语音仍在本地处理。",
    testApi: "测试连接（发送一句测试文字）", apiTestHelp: "仅发送固定测试句 Hello.（英语→中文），不发送字幕历史，也不会切换当前模式。",
    apiTesting: "正在发送测试文字…", apiTestSuccess: "连接成功 · {latency} ms · {translation}", apiConsentRequired: "请先确认文字发送与费用提示，再测试或应用 API 设置。",
    apiFieldsRequired: "请填写完整的服务地址和模型名称。", apiStoppedRequired: "请先停止同传并等待当前片段处理结束，再更改或测试翻译设置。",
    apiAddressInvalid: "请填写不含账号、密码、查询参数或片段的 HTTPS 服务地址；HTTP 仅限本机地址。",
    apiTranslationFailed: "API 翻译失败，请检查服务配置或连接。", apiModeShort: "API 翻译", localModeShort: "本地翻译", settingsBusy: "正在应用或测试设置，请稍候。",
  },
  en: {
    audioNotStarted: "Audio not started · Check your audio device and retry", deviceDisconnected: "Disconnected · {name}",
    pageTitle: "YiSheng · Local Live Interpreter", brandHome: "YiSheng home", versionLoading: "Loading version…",
    switchLanguage: "Switch between Chinese and English", openMini: "Open always-on-top mini subtitles", miniTitle: "Mini subtitles",
    miniSubtitle: "Mini subtitles", openSettings: "Open settings", settings: "Settings", ready: "Ready",
    heroLead: "Hear every word. ", heroAccent: "Understand it now.", heroCopy: "Speech recognition stays on your PC. Translate offline by default, or choose your own API service for text in Settings.",
    latency: "Latency", recognizedLanguage: "Language", segments: "Segments", original: "Original",
    clearHistory: "Clear history", waitingVoice: "Waiting for audio", startHelp: "Choose a source and target language, then start live interpretation below.",
    processing: "Recognizing and translating…", sourceLanguage: "Source language", autoLanguages: "Auto detect (Chinese/Japanese/English/Korean)",
    chinese: "Chinese", english: "English", japanese: "Japanese", korean: "Korean", translateTo: "Translate to", audioSource: "Audio source",
    microphoneOption: "Microphone (speak to your PC)", systemOption: "Computer audio (games/videos)", bothOption: "Microphone + computer",
    startInterpreting: "Start interpreting", clickMicrophone: "Click to start the microphone", exportText: "Export text",
    updateAvailable: "Update available", updateTitle: "YiSheng can be updated", readingVersion: "Reading version information…",
    prepareDownload: "Preparing download…", later: "Later", downloadUpdate: "Download update",
    updateSafe: "The update is downloaded over HTTPS and verified with SHA-256.", localOptimization: "LOCAL OPTIMIZATION",
    runtimeSettings: "Runtime settings", closeSettings: "Close settings", detectingHardware: "Detecting hardware…",
    pleaseWait: "Please wait", detecting: "Detecting", interfaceLanguage: "Interface language", languageHint: "You can also use 🌐 at the top",
    recognitionModel: "Recognition model", modelTradeoff: "Base uses less CPU; Small may improve recognition, not translation errors",
    tinyOption: "Tiny · Fastest / first download about 75 MB", baseOption: "Base · Bundled / balanced",
    smallOption: "Small · More accurate / first download about 484 MB", mediumOption: "Medium · High accuracy / first download about 1.53 GB",
    baseBundled: "Base is bundled", modelDownloadHelp: "Choose another model, then click Apply settings to download it",
    computeDevice: "Compute device", autoSelect: "Automatic (game-first)", deviceHelp: "Automatic uses low-impact CPU processing and reserves the GPU for games. Select GPU manually for faster recognition.",
    systemDevice: "Computer audio device", gameVideoOutput: "Game and video output", autoSpeaker: "Automatically use the current speaker",
    systemAudioHelp: "Captures audio currently playing in Windows. Stereo Mix is not required.",
    offlineTranslationModel: "Offline translation models", repair: "Repair", cacheManagement: "Cache management",
    cachePreserve: "Downloaded models and subtitles are kept", calculating: "Calculating…", cacheItems: "Temporary audio, web cache, and old logs",
    clearCache: "Clear cache", applySettings: "Apply settings", about: "About", version: "Version", loading: "Loading…",
    runtimeLocal: "Local desktop processing · Free", runtimeWeb: "Local processing · Free",
    translationSuffix: " translation", currentLanguage: "current language", autoDetectShort: "Auto detect ZH/JA/EN/KO",
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
    clearing: "Clearing…", released: "Released {size}", releasedRestart: "Released {size} · restart frees {pending} more", cachePartial: "Released {size}; {count} item(s) are busy and can be retried later", cacheKeptRestart: "Resident model memory was released. Downloaded models, settings, and subtitles were kept; restart to finish clearing the web cache.",
    cacheKept: "Resident model memory was released. Downloaded models, settings, and subtitles were kept.", cacheCleared: "Cache cleared. Released {size}; downloaded models were not deleted.", cacheClearedRestart: "Released {size} now; restarting will free another {pending} of web cache. Downloaded models were not deleted.", clearFailed: "Clear failed: {error}",
    unknown: "Unknown", noNvidia: "No NVIDIA GPU detected", availableRam: " · {ram} GB available", gpuReady: "GPU optional", cpuFallback: "Low-impact CPU",
    cudaReady: "CUDA is ready. Automatic mode uses low-impact CPU processing to reserve the GPU for games; select GPU manually for faster recognition.", cudaIncomplete: "An NVIDIA GPU was detected, but CUDA 12 / cuDNN 9 is incomplete. Automatic mode uses low-impact CPU processing.",
    statusFailed: "Could not read engine status: {error}", defaultPrefix: "Default · ", devicesFound: "Found {count} Windows output device(s). Capturing locally with WASAPI.",
    noAudioDevice: "No computer audio device was found.", audioComponentFailed: "Computer audio is unavailable: {error}", stillListening: "Still listening · Previous segment failed",
    processingFailed: "Processing failed", sessionEnded: "Interpretation ended", translationUnavailable: "The bundled translation model is unavailable. Reinstall YiSheng.",
    translationModelUnavailable: "Translation model unavailable", systemAudioReadFailed: "Computer audio read failed ({status})", systemAudioInterrupted: "Computer audio capture stopped",
    micHint: "Only listens to you · Choose computer audio for games or videos", systemHint: "Pause-delimited sentences · Select the game's language when known", bothHint: "Both audio sources · More processing required",
    microphoneAdvice: "For games, videos, or podcasts, choose Computer audio. Microphone is intended for direct speech.", stopInterpreting: "Stop interpreting", interpreting: "Interpreting", preparingEngine: "Preparing the local speech model…",
    lowLatency: "Pause-delimited interpretation · {source}", micPermission: "Microphone permission is required.", audioStartFailed: "Could not start audio: {error}", finishingLast: "Finishing the last segment",
    audioBehind: "Processing cannot keep up. Skipped queued audio to catch up. Try Base with one audio source, or reduce game load.",
    exportTitle: "YiSheng · Live interpretation transcript", exportTime: "Exported: {time}", originalLine: "[{index}] Original ({source} · {language})", untranslated: "[Not translated]",
    savedTo: "Saved to: {path}", saveFailed: "Could not save the file.", desktopExportFailed: "Desktop export failed: {error}", stopBeforeModel: "Stop the current session before switching models.",
    checkingModel: "Checking model…", settingsApplied: "Settings applied. The model will load on the next recognition request.", checking: "Checking…", checkingLocalModel: "Checking bundled models",
    translationChecked: "{source} → {target} translation model checked.", offlinePackageMissing: "Offline model package missing", install: "Install",
    translationMode: "Translation mode", localTranslationOption: "Local translation · Free and offline", apiTranslationOption: "API translation · Your own service",
    translationModeHelp: "Each app launch defaults to local mode. Click Apply settings to activate your choice. Speech recognition still runs locally.",
    readingMode: "Reading translation mode…", localModeActive: "Active: local offline translation", apiModeActive: "Active: API translation · Text sent to your service",
    apiRuntime: "Local speech + API translation", apiBaseUrl: "Service address (Base URL)", apiModel: "Service model name", apiKey: "API key",
    apiBaseUrlHelp: "Chat Completions-compatible services only. Enter the service's full Base URL (often ending in /v1), or its full /chat/completions address. Remote services require HTTPS.",
    apiKeyRequired: "Enter a key, or explicitly select 'This service needs no key'. Enter the key again after changing the address or model.",
    apiKeyReuse: "A key is configured for this address and model. Leave blank to reuse it for this app session, or enter a replacement.",
    apiNoKey: "This service needs no key (such as a local server)", apiKeyMemory: "API settings are used only for this app session, never saved to disk. Local mode clears the backend key. Configure again after restarting.",
    apiConsent: "I agree to send recognized text to the service above, which may charge fees. Audio processing stays local.",
    testApi: "Test connection (sends one test sentence)", apiTestHelp: "Sends only the fixed sentence Hello. (English to Chinese), not subtitle history. Does not change the active mode.",
    apiTesting: "Sending test text…", apiTestSuccess: "Connected · {latency} ms · {translation}", apiConsentRequired: "Confirm the text-sharing and fee notice before testing or applying API settings.",
    apiFieldsRequired: "Enter the full service address and model name.", apiStoppedRequired: "Stop interpreting and wait for the current segment before changing or testing translation settings.",
    apiAddressInvalid: "Use an HTTPS service address without credentials, query parameters or fragments. HTTP is allowed only for a loopback address.",
    apiTranslationFailed: "API translation failed. Check the service configuration or connection.", apiModeShort: "API translation", localModeShort: "Local translation", settingsBusy: "Applying or testing settings. Please wait.",
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
  translationModeSelect: $("#translationModeSelect"),
  translationModeBadge: $("#translationModeBadge"),
  apiTranslationFields: $("#apiTranslationFields"),
  translationBaseUrl: $("#translationBaseUrl"),
  translationApiModel: $("#translationApiModel"),
  translationApiKey: $("#translationApiKey"),
  translationNoKey: $("#translationNoKey"),
  translationConsent: $("#translationConsent"),
  apiKeyHelp: $("#apiKeyHelp"),
  testTranslationButton: $("#testTranslationButton"),
  translationTestResult: $("#translationTestResult"),
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
  starting: false,
  stopping: false,
  settingsBusy: false,
  testingTranslation: false,
  translationDraftInitialized: false,
  translationDraftDirty: false,
  translationTest: null,
  releasePromise: null,
  sessionId: 0,
  microphoneSegmenter: null,
  lastBacklogNotice: 0,
  lastSystemSequence: 0,
  systemPollTask: null,
  stream: null,
  audioContext: null,
  sourceNode: null,
  captureNode: null,
  silentGain: null,
  buffers: [],
  bufferedFrames: 0,
  sampleRate: 48000,
  chunkSeconds: 8.0,
  overlapSeconds: 0.5,
  captureChunkSeconds: 8.0,
  captureOverlapSeconds: 0.6,
  queue: [],
  processing: false,
  segments: [],
  status: null,
  fallbackProcessor: null,
  captureLanguage: "en",
  captureTarget: "zh",
  captureTranslationRevision: null,
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
  window.YishengVR?.setLanguage(locale);
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
  } else if (state.starting) {
    elements.recordLabel.textContent = tr("preparingEngine");
  } else {
    elements.recordLabel.textContent = tr("startInterpreting");
    elements.recordButton.setAttribute("aria-label", tr("startInterpreting"));
  }
  renderTranslationSettings();
  renderTranslationMode();
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
  if (!state.recording && !state.starting && !state.stopping) loadSystemAudioDevices();
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
  if (state.settingsBusy || translationSessionBusy()) {
    toast(tr("stopBeforeClear"), "error");
    return;
  }
  state.settingsBusy = true;
  renderTranslationSettings();
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
    const released = formatBytes(result.removed_bytes);
    const pending = formatBytes(result.pending_restart_bytes || 0);
    elements.cacheStatus.textContent = result.skipped_items
      ? tf("cachePartial", { size: released, count: result.skipped_items })
      : result.pending_restart_bytes
        ? tf("releasedRestart", { size: released, pending })
        : tf("released", { size: released });
    elements.cacheDetail.textContent = result.restart_required
      ? tr("cacheKeptRestart")
      : tr("cacheKept");
    toast(result.skipped_items
      ? tf("cachePartial", { size: released, count: result.skipped_items })
      : result.pending_restart_bytes
        ? tf("cacheClearedRestart", { size: released, pending })
        : tf("cacheCleared", { size: released }), result.skipped_items ? "error" : "info", 6500);
  } catch (error) {
    toast(tf("clearFailed", { error: error.message }), "error", 6500);
    await loadCacheStatus();
  } finally {
    state.settingsBusy = false;
    renderTranslationSettings();
    elements.clearCacheButton.textContent = tr("clearCache");
  }
}

function closeSettings() {
  elements.settingsDrawer.classList.remove("open");
  elements.settingsDrawer.setAttribute("aria-hidden", "true");
  window.setTimeout(() => { elements.drawerBackdrop.hidden = true; }, 300);
}

function translationSessionBusy() {
  return Boolean(state.recording || state.starting || state.stopping || state.processing || state.queue.length || state.releasePromise);
}

function normalizeTranslationBaseUrl(value) {
  const raw = String(value || "").trim();
  // Keep the path spelling identical to the backend: never infer /v1, resolve
  // dot segments, or reuse a credential for a different provider path.
  if (!raw || /[^\x21-\x7e]|[\\?#]/.test(raw)) throw new Error(tr("apiAddressInvalid"));
  const match = raw.match(/^(https?):\/\/([^/]+)(\/.*)?$/i);
  if (!match || match[2].includes("@") || match[2].includes("%")) throw new Error(tr("apiAddressInvalid"));
  let parsed;
  try { parsed = new URL(raw); } catch { throw new Error(tr("apiAddressInvalid")); }
  if (parsed.protocol === "http:" && !["localhost", "127.0.0.1", "[::1]"].includes(parsed.hostname)) {
    throw new Error(tr("apiAddressInvalid"));
  }
  const path = (match[3] || "").replace(/\/+$/, "").replace(/\/chat\/completions$/, "");
  return `${parsed.protocol}//${parsed.host}${path}`;
}

function canReuseTranslationKey() {
  const applied = state.status?.translation;
  if (applied?.mode !== "api" || !applied.has_api_key) return false;
  try {
    return normalizeTranslationBaseUrl(elements.translationBaseUrl.value) === applied.base_url
      && elements.translationApiModel.value.trim() === applied.model;
  } catch { return false; }
}

function initializeTranslationDraft() {
  if (state.translationDraftInitialized || !state.status) return;
  const applied = state.status.translation || { mode: "local" };
  elements.translationModeSelect.value = applied.mode === "api" ? "api" : "local";
  elements.translationBaseUrl.value = applied.mode === "api" ? applied.base_url : "";
  elements.translationApiModel.value = applied.mode === "api" ? applied.model : "";
  // Never restore API configuration or consent from persistent browser storage.
  elements.translationApiKey.value = "";
  elements.translationNoKey.checked = false;
  elements.translationConsent.checked = false;
  state.translationDraftInitialized = true;
}

function renderTranslationMode() {
  const mode = state.status ? (state.status.translation?.mode === "api" ? "api" : "local") : "unknown";
  elements.translationModeBadge.dataset.mode = mode;
  elements.translationModeBadge.textContent = tr(mode === "api" ? "apiModeActive" : mode === "local" ? "localModeActive" : "readingMode");
  const runtimeLabel = $("#runtimeLabel");
  if (runtimeLabel) runtimeLabel.textContent = tr(mode === "api" ? "apiRuntime" : mode === "unknown" ? "readingMode" : window.pywebview?.api ? "runtimeLocal" : "runtimeWeb");
}

function renderTranslationSettings() {
  const busy = state.settingsBusy || translationSessionBusy();
  const disabled = busy || !state.translationDraftInitialized;
  const apiDraft = elements.translationModeSelect.value === "api";
  elements.apiTranslationFields.hidden = !apiDraft;
  for (const field of [elements.translationModeSelect, elements.translationBaseUrl, elements.translationApiModel,
    elements.translationNoKey, elements.translationConsent]) field.disabled = disabled;
  elements.translationApiKey.disabled = disabled || elements.translationNoKey.checked;
  elements.apiKeyHelp.textContent = tr(canReuseTranslationKey() ? "apiKeyReuse" : "apiKeyRequired");
  elements.testTranslationButton.disabled = disabled || !apiDraft;
  elements.testTranslationButton.textContent = tr(state.testingTranslation ? "apiTesting" : "testApi");
  elements.saveSettingsButton.disabled = disabled;
  if (!state.settingsBusy) elements.saveSettingsButton.textContent = tr("applySettings");
  elements.modelSelect.disabled = busy;
  elements.deviceSelect.disabled = busy;
  elements.clearCacheButton.disabled = busy;
  elements.installTranslationButton.disabled = busy;
  if (state.settingsBusy) elements.recordButton.disabled = true;
  else if (!state.starting && !state.stopping) elements.recordButton.disabled = false;
  const result = state.translationTest;
  elements.translationTestResult.hidden = !result;
  elements.translationTestResult.dataset.error = String(Boolean(result?.error));
  elements.translationTestResult.textContent = result
    ? result.error || tf("apiTestSuccess", { latency: result.latency_ms, translation: result.translation }) : "";
}

function translationDraftChanged(identityChanged = false) {
  state.translationDraftDirty = true;
  state.translationTest = null;
  if (identityChanged) {
    elements.translationApiKey.value = "";
    elements.translationNoKey.checked = false;
    elements.translationConsent.checked = false;
  }
  renderTranslationSettings();
}

function translationSettingsPayload() {
  if (elements.translationModeSelect.value !== "api") return { mode: "local" };
  if (!elements.translationBaseUrl.value.trim() || !elements.translationApiModel.value.trim()) throw new Error(tr("apiFieldsRequired"));
  if (!elements.translationConsent.checked) throw new Error(tr("apiConsentRequired"));
  const base_url = normalizeTranslationBaseUrl(elements.translationBaseUrl.value);
  const model = elements.translationApiModel.value.trim();
  const key = elements.translationApiKey.value.trim();
  if (!key && !elements.translationNoKey.checked && !canReuseTranslationKey()) throw new Error(tr("apiKeyRequired"));
  return { mode: "api", base_url, model, consent: true,
    api_key: elements.translationNoKey.checked ? "" : key || null };
}

function canChangeTranslationSettings() {
  if (state.settingsBusy) { toast(tr("settingsBusy"), "info"); return false; }
  if (translationSessionBusy()) { toast(tr("apiStoppedRequired"), "error"); return false; }
  if (!state.translationDraftInitialized) { toast(tr("readingMode"), "info"); return false; }
  return true;
}

async function testTranslationConnection() {
  if (!canChangeTranslationSettings() || elements.translationModeSelect.value !== "api") return;
  let payload;
  try { payload = translationSettingsPayload(); } catch (error) { toast(error.message, "error"); return; }
  state.settingsBusy = true;
  state.testingTranslation = true;
  state.translationTest = null;
  renderTranslationSettings();
  try {
    const result = await api("/api/translation/test", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
    if (!result?.ok) throw new Error(tr("apiTranslationFailed"));
    state.translationTest = { translation: result.translation, latency_ms: result.latency_ms };
  } catch (error) {
    state.translationTest = { error: error.message };
  } finally {
    state.settingsBusy = false;
    state.testingTranslation = false;
    renderTranslationSettings();
  }
}

function refreshTranslationState() {
  if (!state.status) return;
  const source = elements.languageSelect.value;
  const target = elements.targetLanguageSelect.value;
  const pairs = state.status.translation_pairs || [];
  const sources = source === "auto" ? ["zh", "ja", "en", "ko"] : [source];
  const ready = sources.every((item) => item === target || pairs.includes(`${item}-${target}`));
  const sourceLabel = source === "auto" ? tr("autoDetectShort") : (languageNames[source] || tr("currentLanguage"));
  const targetLabel = languageNames[target] || target;
  elements.translationDetail.textContent = `${sourceLabel} → ${targetLabel}`;
  elements.translationStatus.textContent = ready ? tr("translationReady") : tr("translationBroken");
  elements.installTranslationButton.hidden = ready || source === "auto" || source === target;
  if (elements.translationColumnLabel) elements.translationColumnLabel.textContent = `${targetLabel}${tr("translationSuffix")}`;
}

function realtimeChunkSeconds(engine, recommended) {
  // This is only the uninterrupted-speech ceiling; a 600 ms pause emits early.
  return Math.min(8, Math.max(3, Number(recommended?.chunk_seconds) || 8));
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
    initializeTranslationDraft();
    renderTranslationSettings();
    renderTranslationMode();
  } catch (error) {
    toast(tf("statusFailed", { error: error.message }), "error");
  }
}

async function loadSystemAudioDevices() {
  try {
    const result = await api("/api/audio/system/devices");
    if (state.recording || state.starting || state.stopping) return;
    state.systemDevices = result.devices || [];
    // Never restore a saved numeric index: Windows may reuse it for another device.
    const savedDevice = localStorage.getItem("yisheng-system-device-name") || "";
    elements.systemDeviceSelect.innerHTML = `<option value="">${tr("autoSpeaker")}</option>`;
    for (const device of state.systemDevices) {
      const option = document.createElement("option");
      option.value = device.name;
      option.textContent = `${device.default ? tr("defaultPrefix") : ""}${device.name}`;
      elements.systemDeviceSelect.append(option);
    }

    if (savedDevice && !state.systemDevices.some(device => device.name === savedDevice)) {
      const missing = document.createElement("option");
      missing.value = savedDevice;
      missing.textContent = tf("deviceDisconnected", { name: savedDevice });
      elements.systemDeviceSelect.append(missing);
    }
    elements.systemDeviceSelect.value = savedDevice;
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
    // A missing output must not silently turn a game capture into microphone capture.
  } catch (error) {
    if (state.recording || state.starting || state.stopping) return;
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
  updateLevel(samples);
  for (const chunk of state.microphoneSegmenter.push(samples)) enqueueMicrophoneChunk(chunk);
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
  if (!finalChunk) return;
  const chunk = state.microphoneSegmenter?.finish();
  if (chunk) enqueueMicrophoneChunk(chunk);
}

function enqueueMicrophoneChunk(chunk) {
  const { samples, ...metadata } = chunk;
  enqueueAudio({ ...metadata, blob: encodeWav(downsample(samples, state.sampleRate)), audioSource: "microphone" });
}

function warnAudioBehind() {
  if (Date.now() - state.lastBacklogNotice < 15000) return;
  state.lastBacklogNotice = Date.now();
  toast(tr("audioBehind"), "error", 8000);
}

function enqueueAudio(chunk) {
  const dropped = enqueueLatest(state.queue, {
    ...chunk, sessionId: state.sessionId, language: state.captureLanguage, target: state.captureTarget,
    translationRevision: state.captureTranslationRevision,
  });
  if (dropped) warnAudioBehind();
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
  renderTranslationSettings();
  elements.thinkingRow.hidden = false;
  const chunk = state.queue.shift();
  const source = chunk.language;
  try {
    const previous = state.segments.at(-1);
    const { language: requestLanguage, context } = recognitionPlan(previous, chunk);
    const revision = Number.isInteger(chunk.translationRevision) ? `&translation_revision=${chunk.translationRevision}` : "";
    const result = await api(`/api/transcribe?language=${encodeURIComponent(requestLanguage)}&target=${encodeURIComponent(chunk.target)}&duration=${chunk.duration.toFixed(2)}${revision}&context=${encodeURIComponent(context)}`, {
      method: "POST",
      headers: { "Content-Type": "audio/wav" },
      body: chunk.blob,
    });
    result.audio_source = chunk.audioSource || "microphone";
    result._receivedAt = Date.now();
    result._sessionId = chunk.sessionId;
    result._sequence = chunk.sequence;
    result._endedAt = chunk.endedAt;
    if (result.original) appendSegment(result);
    if (result.warning) toast(result.warning, result.translation_ready ? "info" : "error", 6500);
  } catch (error) {
    toast(error.message, "error", 6500);
    setSessionState(state.recording ? tr("stillListening") : tr("processingFailed"), state.recording);
  } finally {
    state.processing = false;
    elements.thinkingRow.hidden = state.queue.length === 0;
    if (state.queue.length) processQueue();
    else if (!state.recording && !state.stopping) {
      setSessionState(tr(state.captureError ? "systemAudioInterrupted" : "sessionEnded"), false);
      await releaseEngineIfIdle();
    }
    renderTranslationSettings();
  }
}

function appendSegment(result) {
  const previous = state.segments.at(-1);
  const sameSource = previous?.audio_source === result.audio_source;
  const continuing = Boolean(result.continued && sameSource && previous?._element);
  // Separate utterances can legitimately repeat words. Do not independently
  // clip translated prefixes; that changes meaning and can erase a whole line.
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
  const unavailable = result.translation_mode === "api"
    ? result.warning || tr("apiTranslationFailed") : tr("translationUnavailable");
  const translatedContent = result.translation_ready && result.translation
    ? `<p>${escapeHtml(result.translation)}</p>`
    : `<p>${escapeHtml(unavailable)}</p>`;
  item.innerHTML = `
    <div class="transcript-cell original">
      <p>${escapeHtml(result.original)}</p>
      <div class="transcript-meta"><span>${timestamp}</span><span>${escapeHtml(audioSourceNames[result.audio_source] || tr("sound"))}</span><span>${escapeHtml(languageNames[result.language] || result.language)}</span><span class="confidence">${confidence}</span></div>
    </div>
    <div class="transcript-cell translation ${result.translation_ready ? "" : "missing"}" data-target-language="${escapeHtml(languageNames[result.target_language] || result.target_language)}">
      ${translatedContent}
      <div class="transcript-meta"><span>${escapeHtml(languageNames[result.target_language] || result.target_language)}</span><span>${escapeHtml(result.model)}</span><span>${escapeHtml(String(result.device || "").toUpperCase())}</span><span>${escapeHtml(String(result.latency_ms))} ms</span><span>${escapeHtml(tr(result.translation_mode === "api" ? "apiModeShort" : "localModeShort"))}</span></div>
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
      translation: result.translation_ready ? result.translation : result.translation_mode === "api" ? unavailable : tr("translationModelUnavailable"),
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
  state.microphoneSegmenter = new MicrophoneSegmenter(state.sampleRate);
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
      if (response.status === 204) continue;
      if (!response.ok) {
        let detail = tf("systemAudioReadFailed", { status: response.status });
        try { detail = (await response.json()).detail || detail; } catch { /* no-op */ }
        throw new Error(detail);
      }
      await consumeSystemChunk(response);
    } catch (error) {
      if (error.name === "AbortError" || !state.systemAudioActive) break;
      state.systemAudioActive = false;
      return error;
    } finally {
      if (state.systemPollController === controller) state.systemPollController = null;
    }
  }
}

async function consumeSystemChunk(response) {
  const duration = Number(response.headers.get("X-Audio-Duration")) || state.captureChunkSeconds;
  const sequence = Number(response.headers.get("X-Audio-Sequence"));
  if (sequence > state.lastSystemSequence + 1) warnAudioBehind();
  state.lastSystemSequence = sequence;
  updateLevelMeter(Number(response.headers.get("X-Audio-Level")) || 0);
  enqueueAudio({
    blob: await response.blob(), duration, sequence, audioSource: "system",
    continuation: response.headers.get("X-Audio-Continuation") === "1",
    startedAt: Number(response.headers.get("X-Audio-Started-At")),
    endedAt: Number(response.headers.get("X-Audio-Ended-At")),
  });
}

async function startSystemAudioCapture() {
  const result = await api("/api/audio/system/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      device_name: elements.systemDeviceSelect.value || null,
      chunk_seconds: state.captureChunkSeconds,
    }),
  });
  if (!result.running || result.error) throw new Error(result.error || tr("audioNotStarted"));
  state.systemAudioActive = true;
  const session = state.sessionId;
  state.systemPollTask = pollSystemAudio();
  // Cleanup only after polling has settled, never from inside the task it awaits.
  state.systemPollTask.then(error => {
    if (!error || session !== state.sessionId || !state.recording || state.stopping) return;
    state.captureError = error;
    if (!state.starting) void stopRecording(error);
  });
}

async function stopCaptureResources({ discard = false, silent = false } = {}) {
  state.systemAudioActive = false;
  if (discard) state.systemPollController?.abort();
  // Let an in-flight response finish: aborting after the backend dequeues its
  // audio would silently lose that sentence. Stop flushes the remaining tail.
  try { state.sourceNode?.disconnect(); } catch { /* no-op */ }
  try { state.captureNode?.disconnect(); } catch { /* no-op */ }
  state.stream?.getTracks().forEach((track) => track.stop());
  try { await state.audioContext?.close(); } catch { /* no-op */ }
  state.stream = null;
  state.audioContext = null;
  state.sourceNode = null;
  state.captureNode = null;
  state.fallbackProcessor = null;
  try {
    await api("/api/audio/system/stop", { method: "POST" });
    await state.systemPollTask;
    if (!discard && (state.captureMode === "system" || state.captureMode === "both")) {
      for (;;) {
        const response = await fetch("/api/audio/system/chunk?timeout=0.05", { cache: "no-store" });
        if (response.status === 204) break;
        if (!response.ok) throw new Error(tr("systemAudioInterrupted"));
        await consumeSystemChunk(response);
      }
    }
  } catch (error) {
    if (!silent) toast(error.message, "error", 6500);
  } finally {
    state.systemPollTask = null;
  }
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
  if (state.settingsBusy) { toast(tr("settingsBusy"), "info"); return; }
  if (!state.status) { toast(tr("readingMode"), "info"); return; }
  if (state.starting || state.recording || state.stopping) return;
  if (state.processing || state.queue.length) {
    toast(tr("finishingLast"), "info");
    return;
  }
  state.starting = true;
  state.captureError = null;
  renderTranslationSettings();
  elements.recordButton.disabled = true;
  elements.recordLabel.textContent = tr("preparingEngine");
  setSessionState(tr("preparingEngine"), true);
  state.captureLanguage = elements.languageSelect.value;
  state.captureTarget = elements.targetLanguageSelect.value;
  state.captureTranslationRevision = Number.isInteger(state.status.translation?.revision) ? state.status.translation.revision : null;
  state.captureMode = elements.audioSourceSelect.value;
  state.sessionId += 1;
  state.lastSystemSequence = 0;
  state.captureChunkSeconds = state.chunkSeconds;
  state.captureOverlapSeconds = .6;
  state.buffers = [];
  state.bufferedFrames = 0;
  try {
    await state.releasePromise;
    await api("/api/engine/prepare", { method: "POST" });
    state.recording = true;
    if (state.captureMode === "microphone") {
      toast(tr("microphoneAdvice"), "info", 7000);
    }
    if (state.captureMode === "microphone" || state.captureMode === "both") {
      await startMicrophoneCapture();
    }
    if (state.captureMode === "system" || state.captureMode === "both") {
      await startSystemAudioCapture();
    }
    if (state.captureError) throw state.captureError;

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
    await stopCaptureResources({ discard: true, silent: true });
    await releaseEngineIfIdle();
    setSessionState(tr("audioNotStarted"), false);
    const permissionDenied = error.name === "NotAllowedError";
    toast(permissionDenied ? tr("micPermission") : tf("audioStartFailed", { error: error.message }), "error", 6500);
  } finally {
    state.starting = false;
    if (!state.recording) await releaseEngineIfIdle();
    elements.recordButton.disabled = false;
    if (!state.recording) {
      elements.recordButton.classList.remove("recording");
      elements.levelBars.classList.remove("active");
      elements.languageSelect.disabled = false;
      elements.targetLanguageSelect.disabled = false;
      elements.audioSourceSelect.disabled = false;
      elements.systemDeviceSelect.disabled = state.systemDevices.length === 0;
      elements.recordLabel.textContent = tr("startInterpreting");
      elements.recordButton.setAttribute("aria-label", tr("startInterpreting"));
      updateSourceHint();
    }
    renderTranslationSettings();
  }
}

async function stopRecording(captureError = null) {
  if (state.stopping) return;
  state.stopping = true;
  renderTranslationSettings();
  elements.recordButton.disabled = true;
  elements.recordLabel.textContent = tr("finishingLast");
  setSessionState(tr("finishingLast"), false);
  state.recording = false;
  if (state.captureMode === "microphone" || state.captureMode === "both") flushAudio(true);
  state.buffers = [];
  state.bufferedFrames = 0;
  await stopCaptureResources({ silent: Boolean(captureError) });
  state.stopping = false;
  elements.recordButton.disabled = false;
  elements.recordButton.classList.remove("recording");
  elements.recordButton.setAttribute("aria-label", tr("startInterpreting"));
  elements.recordLabel.textContent = tr("startInterpreting");
  elements.levelBars.classList.remove("active");
  elements.languageSelect.disabled = false;
  elements.targetLanguageSelect.disabled = false;
  elements.audioSourceSelect.disabled = false;
  elements.systemDeviceSelect.disabled = state.systemDevices.length === 0;
  updateSourceHint();
  setSessionState(captureError ? tr("systemAudioInterrupted") :
    (state.processing || state.queue.length ? tr("finishingLast") : tr("sessionEnded")), false);
  if (captureError) toast(captureError.message, "error", 6500);
  if (!state.processing && !state.queue.length) await releaseEngineIfIdle();
  renderTranslationSettings();
}

async function releaseEngineIfIdle() {
  if (state.recording || state.processing || state.queue.length || state.starting || state.stopping) return;
  try {
    if (!state.releasePromise) state.releasePromise = api("/api/engine/release", { method: "POST" });
    await state.releasePromise;
  } catch {
    // The process still releases all models during normal application exit.
  } finally {
    state.releasePromise = null;
    renderTranslationSettings();
  }
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
  if (!canChangeTranslationSettings()) return;
  let translationPayload;
  try { translationPayload = translationSettingsPayload(); } catch (error) { toast(error.message, "error"); return; }
  const model = elements.modelSelect.value;
  const device = elements.deviceSelect.value;
  state.settingsBusy = true;
  renderTranslationSettings();
  elements.saveSettingsButton.textContent = tr("checkingModel");
  try {
    await ensureWhisperModel(model);
    await api("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model, device }),
    });
    localStorage.setItem("yisheng-engine", JSON.stringify({ model, device }));
    // Applying local ASR settings does not grant permission to send text.
    // Only this explicit, validated action changes the translation provider.
    state.status = await api("/api/translation/config", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(translationPayload),
    });
    elements.translationApiKey.value = "";
    state.translationDraftDirty = false;
    state.translationDraftInitialized = false;
    initializeTranslationDraft();
    // Applied API settings retain consent for same-provider reuse this session.
    elements.translationConsent.checked = state.status.translation?.mode === "api";
    elements.translationNoKey.checked = state.status.translation?.mode === "api" && !state.status.translation.has_api_key;
    state.translationTest = null;
    refreshTranslationState();
    renderTranslationMode();
    toast(tr("settingsApplied"));
    closeSettings();
  } catch (error) {
    toast(error.message, "error");
    // Reconcile applied state after partial ASR success or a lost response.
    // loadStatus does not overwrite the in-progress API draft.
    await loadStatus();
  } finally {
    state.settingsBusy = false;
    renderTranslationSettings();
  }
}

async function installTranslation() {
  if (!canChangeTranslationSettings()) return;
  state.settingsBusy = true;
  renderTranslationSettings();
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
    state.settingsBusy = false;
    renderTranslationSettings();
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
elements.testTranslationButton.addEventListener("click", testTranslationConnection);
elements.translationModeSelect.addEventListener("change", () => translationDraftChanged());
elements.translationBaseUrl.addEventListener("input", () => translationDraftChanged(true));
elements.translationApiModel.addEventListener("input", () => translationDraftChanged(true));
elements.translationApiKey.addEventListener("input", () => translationDraftChanged());
elements.translationNoKey.addEventListener("change", () => {
  if (elements.translationNoKey.checked) elements.translationApiKey.value = "";
  translationDraftChanged();
});
elements.translationConsent.addEventListener("change", () => translationDraftChanged());
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
  localStorage.setItem("yisheng-system-device-name", elements.systemDeviceSelect.value);
});
elements.modelSelect.addEventListener("change", () => renderWhisperModelStatus());
document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeSettings(); });
window.addEventListener("beforeunload", () => {
  elements.translationApiKey.value = "";
  state.stream?.getTracks().forEach((track) => track.stop());
  if (state.systemAudioActive) fetch("/api/audio/system/stop", { method: "POST", keepalive: true });
});
window.addEventListener("pywebviewready", async () => {
  document.body.classList.add("desktop-app");
  renderTranslationMode();
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
