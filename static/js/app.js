const state = {
  file: null,
  objectUrl: "",
  duration: 0,
  cropMode: "full",
  crop: { x: 0, y: 0, w: 1, h: 1 },
  drag: null,
  pollTimer: 0,
};

const $ = (id) => document.getElementById(id);

const els = {
  runtimeStatus: $("runtimeStatus"),
  videoFile: $("videoFile"),
  dropzone: $("dropzone"),
  uploadStatus: $("uploadStatus"),
  videoPreview: $("videoPreview"),
  videoEmpty: $("videoEmpty"),
  videoMeta: $("videoMeta"),
  startRange: $("startRange"),
  startTime: $("startTime"),
  duration: $("duration"),
  width: $("width"),
  fps: $("fps"),
  speed: $("speed"),
  quality: $("quality"),
  cropOverlay: $("cropOverlay"),
  cropBox: $("cropBox"),
  cropFull: $("cropFull"),
  cropSquare: $("cropSquare"),
  cropCustom: $("cropCustom"),
  resetCrop: $("resetCrop"),
  createGif: $("createGif"),
  taskStatus: $("taskStatus"),
  progressBar: $("progressBar"),
  gifPreview: $("gifPreview"),
  gifEmpty: $("gifEmpty"),
  resultMeta: $("resultMeta"),
  downloadGif: $("downloadGif"),
  timelineLabel: $("timelineLabel"),
  toast: $("toast"),
};

function showToast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("visible");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => els.toast.classList.remove("visible"), 2600);
}

function formatTime(seconds) {
  const safe = Math.max(0, Number(seconds) || 0);
  const mins = Math.floor(safe / 60);
  const secs = Math.floor(safe % 60);
  const tenth = Math.floor((safe % 1) * 10);
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}.${tenth}`;
}

function bytesLabel(bytes) {
  const value = Number(bytes) || 0;
  if (value >= 1024 * 1024) return `${(value / 1024 / 1024).toFixed(2)}MB`;
  if (value >= 1024) return `${Math.round(value / 1024)}KB`;
  return `${value}B`;
}

async function checkRuntime() {
  try {
    const res = await fetch("/api/gif/status");
    const data = await res.json();
    els.runtimeStatus.textContent = data.ready ? "FFmpeg ready" : "FFmpeg missing";
    els.runtimeStatus.classList.toggle("ready", data.ready);
    els.runtimeStatus.classList.toggle("missing", !data.ready);
  } catch (_error) {
    els.runtimeStatus.textContent = "status unavailable";
    els.runtimeStatus.classList.add("missing");
  }
}

function syncTimeline() {
  const start = Number(els.startTime.value) || 0;
  const duration = Math.min(Number(els.duration.value) || 3, 5);
  const maxStart = Math.max(0, state.duration - duration);
  const cleanStart = Math.min(start, maxStart);
  els.startTime.value = cleanStart.toFixed(1).replace(/\.0$/, "");
  els.startRange.max = String(maxStart);
  els.startRange.value = String(cleanStart);
  els.timelineLabel.textContent = `${formatTime(cleanStart)} / ${formatTime(state.duration)}`;
}

function setCropMode(mode) {
  state.cropMode = mode;
  for (const button of [els.cropFull, els.cropSquare, els.cropCustom]) {
    button.classList.toggle("active", button.dataset.cropMode === mode);
  }
  els.cropOverlay.hidden = mode !== "custom";
  if (mode === "square") {
    state.crop = { x: 0, y: 0, w: 1, h: 1 };
  }
  updateCropBox();
}

function resetCrop() {
  state.crop = { x: 0.15, y: 0.15, w: 0.7, h: 0.7 };
  updateCropBox();
}

function updateCropBox() {
  const crop = state.cropMode === "custom" ? state.crop : { x: 0, y: 0, w: 1, h: 1 };
  els.cropBox.style.left = `${crop.x * 100}%`;
  els.cropBox.style.top = `${crop.y * 100}%`;
  els.cropBox.style.width = `${crop.w * 100}%`;
  els.cropBox.style.height = `${crop.h * 100}%`;
}

function clampCrop(next) {
  const min = 0.08;
  const crop = {
    x: Math.max(0, Math.min(0.95, next.x)),
    y: Math.max(0, Math.min(0.95, next.y)),
    w: Math.max(min, Math.min(1, next.w)),
    h: Math.max(min, Math.min(1, next.h)),
  };
  crop.w = Math.min(crop.w, 1 - crop.x);
  crop.h = Math.min(crop.h, 1 - crop.y);
  return crop;
}

function pointerPosition(event) {
  const rect = els.cropOverlay.getBoundingClientRect();
  return {
    x: (event.clientX - rect.left) / rect.width,
    y: (event.clientY - rect.top) / rect.height,
  };
}

function beginCropDrag(event) {
  if (state.cropMode !== "custom") return;
  event.preventDefault();
  const point = pointerPosition(event);
  state.drag = {
    handle: event.target.dataset.handle || "move",
    start: point,
    crop: { ...state.crop },
  };
  window.addEventListener("pointermove", updateCropDrag);
  window.addEventListener("pointerup", endCropDrag, { once: true });
}

function updateCropDrag(event) {
  if (!state.drag) return;
  const point = pointerPosition(event);
  const dx = point.x - state.drag.start.x;
  const dy = point.y - state.drag.start.y;
  const base = state.drag.crop;
  let next = { ...base };
  const handle = state.drag.handle;
  if (handle === "move") {
    next.x = base.x + dx;
    next.y = base.y + dy;
  }
  if (handle.includes("e")) next.w = base.w + dx;
  if (handle.includes("s")) next.h = base.h + dy;
  if (handle.includes("w")) {
    next.x = base.x + dx;
    next.w = base.w - dx;
  }
  if (handle.includes("n")) {
    next.y = base.y + dy;
    next.h = base.h - dy;
  }
  state.crop = clampCrop(next);
  updateCropBox();
}

function endCropDrag() {
  state.drag = null;
  window.removeEventListener("pointermove", updateCropDrag);
}

function updateFile(file) {
  if (!file) return;
  state.file = file;
  if (state.objectUrl) URL.revokeObjectURL(state.objectUrl);
  state.objectUrl = URL.createObjectURL(file);
  els.videoPreview.src = state.objectUrl;
  els.videoEmpty.style.display = "none";
  els.uploadStatus.textContent = file.name;
  els.videoMeta.textContent = `${file.name} | ${bytesLabel(file.size)}`;
  resetCrop();
}

function buildFormData() {
  if (!state.file) {
    showToast("Choose a video first");
    return null;
  }
  const form = new FormData();
  form.append("file", state.file);
  form.append("start_time", els.startTime.value || "0");
  form.append("duration", els.duration.value || "3");
  form.append("width", els.width.value);
  form.append("fps", els.fps.value);
  form.append("speed", els.speed.value);
  form.append("quality_mode", els.quality.value);
  form.append("target_size", "1048576");
  form.append("crop_mode", state.cropMode);
  const crop = state.cropMode === "custom" ? state.crop : { x: 0, y: 0, w: 1, h: 1 };
  form.append("crop_x", String(crop.x));
  form.append("crop_y", String(crop.y));
  form.append("crop_w", String(crop.w));
  form.append("crop_h", String(crop.h));
  return form;
}

function setProgress(percent, label) {
  els.progressBar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
  els.taskStatus.textContent = label;
}

async function pollTask(taskId) {
  window.clearTimeout(state.pollTimer);
  const res = await fetch(`/api/gif/tasks/${taskId}`);
  const task = await res.json();
  setProgress(task.progress || 0, task.status || "processing");
  if (task.status === "success") {
    els.gifPreview.src = `${task.gif_url}?t=${Date.now()}`;
    els.gifPreview.style.display = "block";
    els.gifEmpty.style.display = "none";
    els.downloadGif.href = task.download_url;
    els.downloadGif.classList.remove("disabled");
    els.resultMeta.innerHTML = `<span>${bytesLabel(task.file_size)}</span><span>${task.width}x${task.height || "auto"} | ${task.fps}fps</span>`;
    return;
  }
  if (task.status === "failed") {
    els.resultMeta.innerHTML = `<span>failed</span><span>${task.error || "try lower settings"}</span>`;
    showToast(task.error || "GIF generation failed");
    return;
  }
  state.pollTimer = window.setTimeout(() => pollTask(taskId), 900);
}

async function createGif() {
  const form = buildFormData();
  if (!form) return;
  els.downloadGif.classList.add("disabled");
  els.gifPreview.style.display = "none";
  els.gifEmpty.style.display = "grid";
  els.resultMeta.innerHTML = "<span>target 1MB</span><span>uploading</span>";
  setProgress(8, "uploading");
  try {
    const res = await fetch("/api/gif/create", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Request failed");
    setProgress(20, "processing");
    pollTask(data.task_id);
  } catch (error) {
    setProgress(0, "failed");
    showToast(error.message || "Request failed");
  }
}

els.videoFile.addEventListener("change", () => updateFile(els.videoFile.files[0]));
els.videoPreview.addEventListener("loadedmetadata", () => {
  state.duration = els.videoPreview.duration || 0;
  els.videoMeta.textContent = `${els.videoMeta.textContent} | ${formatTime(state.duration)}`;
  syncTimeline();
});
els.startRange.addEventListener("input", () => {
  els.startTime.value = Number(els.startRange.value).toFixed(1).replace(/\.0$/, "");
  syncTimeline();
});
els.startTime.addEventListener("input", syncTimeline);
els.duration.addEventListener("input", syncTimeline);
els.cropFull.addEventListener("click", () => setCropMode("full"));
els.cropSquare.addEventListener("click", () => setCropMode("square"));
els.cropCustom.addEventListener("click", () => {
  setCropMode("custom");
  resetCrop();
});
els.resetCrop.addEventListener("click", resetCrop);
els.cropBox.addEventListener("pointerdown", beginCropDrag);
els.createGif.addEventListener("click", createGif);

checkRuntime();
setCropMode("full");
