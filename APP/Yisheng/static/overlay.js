const originalText = document.querySelector("#originalText");
const translationText = document.querySelector("#translationText");
const subtitleMeta = document.querySelector("#subtitleMeta");
const opacitySlider = document.querySelector("#opacitySlider");
const opacityValue = document.querySelector("#opacityValue");
const restoreButton = document.querySelector("#restoreButton");
const lockButton = document.querySelector("#lockButton");
const resizeHandle = document.querySelector("#resizeHandle");
const toolbar = document.querySelector(".overlay-toolbar");
let overlayLocked = false;
let resizeStart = null;
let resizePending = false;
let uiLanguage = "zh";
const overlayName = document.querySelector("#overlayName");
const opacityLabel = document.querySelector("#opacityLabel");
const TEXT = {
  zh: { title: "译声 · 迷你字幕", name: "译声 · 置顶字幕", opacity: "背景透明度", lock: "锁定窗口", unlock: "解除锁定", restore: "返回主界面", waiting: "等待原声…", translation: "开始同传后，翻译会显示在这里", help: "窗口始终置顶 · 拖动顶部区域可移动" },
  en: { title: "YiSheng · Mini subtitles", name: "YiSheng · Always-on-top subtitles", opacity: "Background", lock: "Lock window", unlock: "Unlock", restore: "Main window", waiting: "Waiting for speech…", translation: "The translation will appear here", help: "Always on top · Drag the top bar to move" },
};

function applyLanguage(language) {
  uiLanguage = language === "en" ? "en" : "zh";
  const text = TEXT[uiLanguage];
  document.documentElement.lang = uiLanguage === "en" ? "en" : "zh-CN";
  document.title = text.title;
  overlayName.textContent = text.name;
  opacityLabel.textContent = text.opacity;
  restoreButton.textContent = text.restore;
  lockButton.textContent = overlayLocked ? text.unlock : text.lock;
}

function setTransparency(value) {
  const percent = Math.max(0, Math.min(100, Number(value || 0)));
  document.documentElement.style.setProperty("--panel-alpha", ((100 - percent) / 100).toFixed(2));
  opacitySlider.value = String(percent);
  opacityValue.textContent = `${percent}%`;
  localStorage.setItem("yisheng-overlay-transparency", String(percent));
}
window.setOverlayTransparency = setTransparency;

window.setOverlayLocked = (locked) => {
  overlayLocked = Boolean(locked);
  document.body.classList.toggle("overlay-locked", overlayLocked);
  toolbar.classList.toggle("pywebview-drag-region", !overlayLocked);
  lockButton.textContent = overlayLocked ? TEXT[uiLanguage].unlock : TEXT[uiLanguage].lock;
  localStorage.setItem("yisheng-overlay-locked", overlayLocked ? "1" : "0");
};

window.renderSubtitle = (payload = {}) => {
  const original = String(payload.original || "").trim();
  const translation = String(payload.translation || "").trim();
  originalText.textContent = original || TEXT[uiLanguage].waiting;
  translationText.textContent = translation || TEXT[uiLanguage].translation;
  subtitleMeta.textContent = String(payload.meta || TEXT[uiLanguage].help);
};

opacitySlider.addEventListener("input", () => setTransparency(opacitySlider.value));
lockButton.addEventListener("click", async () => {
  const next = !overlayLocked;
  window.setOverlayLocked(next);
  try {
    const result = await window.pywebview.api.set_overlay_locked(next);
    if (!result.ok) window.setOverlayLocked(!next);
  } catch {
    window.setOverlayLocked(!next);
  }
});

resizeHandle.addEventListener("pointerdown", (event) => {
  if (overlayLocked) return;
  event.preventDefault();
  resizeStart = { x: event.screenX, y: event.screenY, width: window.innerWidth, height: window.innerHeight };
  resizeHandle.setPointerCapture(event.pointerId);
});
resizeHandle.addEventListener("pointermove", (event) => {
  if (!resizeStart || resizePending || overlayLocked) return;
  const width = Math.round(resizeStart.width + event.screenX - resizeStart.x);
  const height = Math.round(resizeStart.height + event.screenY - resizeStart.y);
  resizePending = true;
  window.pywebview.api.resize_overlay(width, height).finally(() => { resizePending = false; });
});
function finishResize(event) {
  resizeStart = null;
  try { resizeHandle.releasePointerCapture(event.pointerId); } catch { /* pointer already released */ }
}
resizeHandle.addEventListener("pointerup", finishResize);
resizeHandle.addEventListener("pointercancel", finishResize);
restoreButton.addEventListener("click", async () => {
  try { await window.pywebview.api.restore_main(); } catch { /* keep overlay usable */ }
});

window.addEventListener("pywebviewready", async () => {
  try {
    const state = await window.pywebview.api.get_overlay_state();
    applyLanguage(state.ui_language);
    window.renderSubtitle(state);
    window.setOverlayLocked(Boolean(state.locked) || localStorage.getItem("yisheng-overlay-locked") === "1");
    await window.pywebview.api.set_overlay_locked(overlayLocked);
  } catch { /* wait for first subtitle */ }
});

const savedTransparency = localStorage.getItem("yisheng-overlay-transparency");
const legacyOpacity = localStorage.getItem("yisheng-overlay-opacity");
setTransparency(savedTransparency ?? (legacyOpacity === null ? "55" : String(100 - Number(legacyOpacity))));
window.setOverlayLocked(localStorage.getItem("yisheng-overlay-locked") === "1");
applyLanguage("zh");
