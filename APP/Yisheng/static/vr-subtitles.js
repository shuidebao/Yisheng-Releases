(() => {
  "use strict";
  const root = document.getElementById("vrSettings");
  if (!root) return;
  const node = id => document.getElementById(`vr${id}`);
  const text = {
    zh: {
      title: "VR 私人字幕 · 实验版", help: "先连接头显并启动 SteamVR，再开启字幕。优先面向 Quest PCVR；不支持一体机独立运行。录屏或直播可能捕获字幕。",
      size: "字幕大小", vertical: "上下位置", distance: "距离（米）", opacity: "不透明度", original: "同时显示原文",
      start: "开启 VR 字幕", stop: "关闭", reset: "恢复默认位置与样式", off: "未开启", starting: "正在连接 SteamVR…",
      empty: "等待字幕 · 可先显示测试字幕检查位置", subtitle: "正在显示当前一句字幕", preview: "正在显示测试字幕 · 最长 5 秒",
      test: "显示测试字幕（5 秒）", test_help: "仅显示固定测试文字，不开启录音或调用 API；新字幕或清空会提前结束测试。",
      stopping: "正在关闭…", error: "连接已停止，请检查后重新开启。", not_ready: "VR 字幕尚未连接，请连接头显并开启后再测试。",
      bridge_error: "暂时无法读取 VR 状态，正在重试；仍可尝试关闭。",
      cleanup_failed: "VR 显示进程尚未确认退出，请再次点击关闭；暂时不能重新开启。",
      desktop_only: "请在译声桌面版中开启 VR 字幕。", missing_dependency: "当前运行环境缺少 VR 组件，请按 VR 使用说明安装。",
      no_runtime: "未找到 SteamVR，请先安装并启动。", no_headset: "未检测到已连接头显，请连接后启动 SteamVR，再重新开启字幕。",
      runtime_quit: "SteamVR 已退出，字幕已关闭。", runtime_error: "SteamVR 连接或绘制失败，请确认运行时和头显已就绪，再重新开启。",
      timeout: "SteamVR 响应超时，字幕已停止。请检查后重新开启。", worker_exit: "VR 显示进程已退出，请重新开启。",
      windows_only: "此实验版需要 Windows PCVR。", invalid_settings: "请填写有效距离（0.8–3 米），并检查其他显示设置。",
    },
    en: {
      title: "Private VR subtitles · Experimental", help: "Connect your headset and start SteamVR first. Quest PCVR is the priority; standalone mode is not supported. Recordings or streams may capture subtitles.",
      size: "Subtitle size", vertical: "Vertical position", distance: "Distance (metres)", opacity: "Opacity", original: "Show original text",
      start: "Enable VR subtitles", stop: "Disable", reset: "Reset position and style", off: "Off", starting: "Connecting to SteamVR…",
      empty: "Waiting for subtitles · Use test text to check the position", subtitle: "Showing the current subtitle", preview: "Showing test subtitles · Up to 5 seconds",
      test: "Show test subtitles (5 seconds)", test_help: "Shows fixed test text without recording or calling an API. New subtitles or clearing ends the test early.",
      stopping: "Closing…", error: "Disconnected. Check your setup and enable again.", not_ready: "VR subtitles are not connected. Connect your headset and enable them before testing.",
      bridge_error: "Unable to read VR status. Retrying; you can still try Disable.",
      cleanup_failed: "The VR display process has not exited yet. Try Disable again before enabling it.",
      desktop_only: "Use the YiSheng desktop app to enable VR subtitles.", missing_dependency: "VR components are missing. See the VR setup guide.",
      no_runtime: "SteamVR was not found. Install and start it first.", no_headset: "No connected headset found. Connect it, start SteamVR, then enable again.",
      runtime_quit: "SteamVR exited. Subtitles are off.", runtime_error: "SteamVR connection or rendering failed. Check your runtime and headset, then enable again.",
      timeout: "SteamVR timed out. Subtitles stopped; check your setup and enable again.", worker_exit: "The VR display process exited. Enable again.",
      windows_only: "This preview requires Windows PCVR.", invalid_settings: "Enter a valid distance (0.8–3 metres) and check the display settings.",
    },
  };
  let language = document.documentElement.lang === "en" ? "en" : "zh";
  let current = {state: "off"}, busy = false, timer = null, polling = false, revision = 0;
  let validationError = "", settingsRestored = false, unloaded = false;
  const api = () => window.pywebview?.api;
  const options = () => ({size: Number(node("Size").value), distance: Number(node("Distance").value),
    vertical: Number(node("Vertical").value), opacity: Number(node("Opacity").value), original: node("Original").checked});
  function restoreSettings(settings) {
    if (!settings) return;
    for (const id of ["Size", "Distance", "Vertical", "Opacity"]) node(id).value = settings[id.toLowerCase()];
    node("Original").checked = settings.original;
    settingsRestored = true;
  }
  function render() {
    root.querySelectorAll("[data-vr-text]").forEach(el => { el.textContent = text[language][el.dataset.vrText]; });
    const display = ["preview", "subtitle"].includes(current.display) ? current.display : "empty";
    node("Status").textContent = text[language][current.error || validationError || (current.state === "ready" ? display : current.state)] || text[language].error;
    const cleanupPending = current.error === "cleanup_failed";
    const active = cleanupPending || ["starting", "ready", "stopping"].includes(current.state);
    node("Start").disabled = busy || active || !api()?.start_vr_overlay;
    node("Stop").disabled = busy || !active || current.state === "stopping";
    node("Preview").disabled = busy || cleanupPending || current.state !== "ready" || !api()?.preview_vr_overlay;
    for (const id of ["Size", "Distance", "Vertical", "Opacity", "Original", "Reset"]) node(id).disabled = busy;
  }
  function schedule() {
    clearTimeout(timer);
    if (!unloaded && (["starting", "ready", "stopping"].includes(current.state) || current.error === "bridge_error")) timer = setTimeout(refresh, 750);
  }
  async function refresh() {
    if (unloaded) return;
    if (busy || polling || !api()?.get_vr_state) { schedule(); return; }
    polling = true;
    const requestRevision = revision;
    try {
      const result = await api().get_vr_state();
      if (!unloaded && requestRevision === revision) {
        current = result;
        if (!settingsRestored) restoreSettings(result.settings);
      }
    } catch { if (!unloaded && requestRevision === revision) current = {...current, error: "bridge_error"}; }
    finally { polling = false; render(); schedule(); }
  }
  async function call(method, value) {
    if (busy || unloaded) return;
    if (!api()?.[method]) { current = {state: "off", error: "desktop_only"}; render(); return; }
    busy = true; revision++; clearTimeout(timer); render();
    try {
      const result = await api()[method](...(value === undefined ? [] : [value]));
      validationError = result.error === "invalid_settings" ? result.error : "";
      if (!validationError) {
        current = result.state ? result : {...current, error: result.error};
        if (method === "configure_vr_overlay" || method === "start_vr_overlay") restoreSettings(result.settings);
      }
    } catch { current = {...current, error: "runtime_error"}; }
    finally { busy = false; render(); schedule(); }
  }
  node("Start").addEventListener("click", () => call("start_vr_overlay", options()));
  node("Stop").addEventListener("click", () => call("stop_vr_overlay"));
  node("Preview").addEventListener("click", () => {
    if (current.state === "ready" && current.error !== "cleanup_failed") return call("preview_vr_overlay");
  });
  for (const id of ["Size", "Distance", "Vertical", "Opacity", "Original"]) {
    node(id).addEventListener("change", () => call("configure_vr_overlay", options()));
  }
  node("Reset").addEventListener("click", () => {
    node("Size").value = 1; node("Distance").value = 1.5; node("Vertical").value = -0.35;
    node("Opacity").value = 0.8; node("Original").checked = true;
    return call("configure_vr_overlay", options());
  });
  window.YishengVR = {setLanguage(value) { language = value === "en" ? "en" : "zh"; render(); }, refresh};
  window.addEventListener("pywebviewready", refresh);
  window.addEventListener("beforeunload", () => { unloaded = true; revision++; clearTimeout(timer); });
  render();
  if (api()?.get_vr_state) refresh();
})();
