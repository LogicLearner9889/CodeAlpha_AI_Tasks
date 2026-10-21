/* AI Music Generator - frontend logic with layered error handling */
(() => {
"use strict";

const CFG = {
  MAX_FILE_MB: 20, MAX_FILES: 50, MAX_TOTAL_MB: 60, EXT: [".mid", ".midi"],
  TIMEOUT: { json: 15000, generate: 120000, upload: 120000, midi: 20000 },
  POLL_MS: 2000, POLL_MAX_FAILS: 5, PLAYER_LOAD_MS: 15000,
};
const STATUS_MSG = {
  400: "The request was invalid.", 404: "Server endpoint not found. Is the app up to date?",
  405: "That action is not allowed.", 409: "The server is busy. Try again shortly.",
  413: "Upload too large for the server.", 415: "Unsupported request format.",
  429: "Too many requests. Please slow down.", 500: "Server error. Check the server console.",
  502: "Server unavailable.", 503: "Server unavailable.", 504: "Server timed out.",
};

const $ = (id) => document.getElementById(id);
const clamp = (n, lo, hi) => Math.min(hi, Math.max(lo, n));
const mb = (b) => (b / 1048576).toFixed(1) + " MB";
const state = { files: [], uploading: false, training: false, modelReady: false, fileCount: 0 };

/* ---------- Safe storage (blocked in private mode / some webviews) ---------- */
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* ignore */ } },
};

/* ---------- UI helpers ---------- */
function toast(message, type = "info") {
  const host = $("toastHost");
  if (!host) return;
  if ([...host.children].some((t) => t.dataset.m === message)) return; // de-dupe
  const el = document.createElement("div");
  el.className = `toast show align-items-center border-0 toast-${type}`;
  el.dataset.m = message;
  el.setAttribute("role", "alert");
  const body = document.createElement("div");
  body.className = "d-flex";
  const txt = document.createElement("div");
  txt.className = "toast-body";
  txt.textContent = message;
  const x = document.createElement("button");
  x.className = "btn-close btn-close-white me-2 m-auto";
  x.setAttribute("aria-label", "Close");
  x.onclick = () => el.remove();
  body.append(txt, x);
  el.append(body);
  host.append(el);
  setTimeout(() => el.remove(), type === "err" ? 7000 : 4000);
}

function showMsg(id, text, type = "danger", retry = null) {
  const box = $(id);
  box.replaceChildren();
  if (!text) return;
  const a = document.createElement("div");
  a.className = `alert alert-${type}`;
  a.setAttribute("role", "alert");
  const s = document.createElement("span");
  s.textContent = text;
  a.append(s);
  if (retry) {
    const b = document.createElement("button");
    b.className = "btn btn-sm btn-outline-light";
    b.textContent = "Retry";
    b.onclick = retry;
    a.append(b);
  }
  box.append(a);
}

function setBusy(btn, busy) {
  btn.disabled = busy;
  btn.classList.toggle("busy", busy);
}

/* ---------- API layer: offline, timeout, network, HTTP, bad JSON ---------- */
class ApiError extends Error {
  constructor(msg, kind, status) { super(msg); this.kind = kind; this.status = status; }
}

async function api(url, { method = "GET", body, timeout = CFG.TIMEOUT.json } = {}) {
  if (!navigator.onLine) throw new ApiError("You are offline. Check your connection.", "offline");
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeout);
  let res;
  try {
    res = await fetch(url, {
      method, cache: "no-store", signal: ctrl.signal,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw ctrl.signal.aborted
      ? new ApiError("The request timed out. The server may be busy.", "timeout")
      : new ApiError("Cannot reach the server. Is app.py still running?", "network");
  } finally { clearTimeout(timer); }

  let data = null;
  if ((res.headers.get("content-type") || "").includes("application/json")) {
    try { data = await res.json(); }
    catch { throw new ApiError("Server sent invalid data.", "parse", res.status); }
  }
  if (!res.ok) throw new ApiError((data && data.error) || STATUS_MSG[res.status] || `Unexpected error (HTTP ${res.status}).`, "http", res.status);
  if (data === null) throw new ApiError("Server returned an unexpected (non-JSON) response.", "parse", res.status);
  return data;
}

function fail(err, msgId, retry) {
  console.error(err);
  const text = err instanceof ApiError ? err.message : "Something went wrong. Please try again.";
  if (msgId) showMsg(msgId, text, "danger", err.kind === "http" && err.status < 500 && err.status !== 409 ? null : retry);
  toast(text, "err");
}

/* ---------- Compatibility, connectivity, global errors ---------- */
function checkCompat() {
  const ok = window.fetch && window.Promise && window.FormData && window.AbortController && window.XMLHttpRequest;
  $("compatBanner").classList.toggle("show", !ok);
  if (!ok) document.querySelectorAll(".btn-glow").forEach((b) => (b.disabled = true));
  return !!ok;
}
const setOnline = () => $("offlineBanner").classList.toggle("show", !navigator.onLine);
window.addEventListener("offline", () => { setOnline(); toast("Connection lost.", "err"); });
window.addEventListener("online", () => { setOnline(); toast("Back online.", "ok"); });

let lastGlobal = 0;
const globalErr = (e) => {
  console.error(e);
  if (Date.now() - lastGlobal > 3000) { lastGlobal = Date.now(); toast("Unexpected error in the page. See console for details.", "err"); }
};
window.addEventListener("error", (e) => { if (e.target === window) globalErr(e.error || e.message); });
window.addEventListener("unhandledrejection", (e) => { e.preventDefault(); globalErr(e.reason); });
window.addEventListener("beforeunload", (e) => {
  if (state.uploading || state.training) { e.preventDefault(); e.returnValue = ""; }
});

function checkLibraries() {
  const missing = [];
  if (typeof bootstrap === "undefined") { missing.push("Bootstrap"); document.documentElement.classList.add("no-bootstrap"); }
  if (typeof window.tailwind === "undefined") missing.push("Tailwind");
  if (!window.customElements || !customElements.get("midi-player")) missing.push("MIDI player");
  if (missing.length) toast(`Could not load: ${missing.join(", ")}. The app still works with reduced styling or playback.`, "warn");
}

/* ---------- Audio device handling ---------- */
const AudioCtx = window.AudioContext || window.webkitAudioContext;
function unlockAudio() {
  if (!AudioCtx) return toast("This device has no Web Audio support. You can still download the MIDI file.", "warn");
  try {
    const ctx = new AudioCtx();
    ctx.resume().catch(() => toast("Audio is blocked. Check the volume and silent switch, then tap Play.", "warn"));
  } catch { toast("Could not start the audio output on this device.", "warn"); }
}
document.addEventListener("pointerdown", unlockAudio, { once: true });

/* ---------- Step 1: file selection + upload ---------- */
async function looksLikeMidi(file) {
  try {
    const head = new Uint8Array(await file.slice(0, 4).arrayBuffer());
    return String.fromCharCode(...head) === "MThd";
  } catch { return null; } // unreadable
}

async function addFiles(list) {
  const problems = [];
  let total = state.files.reduce((s, f) => s + f.size, 0);
  for (const f of list) {
    const ext = f.name.slice(f.name.lastIndexOf(".")).toLowerCase();
    if (!CFG.EXT.includes(ext)) { problems.push(`${f.name}: not a MIDI file`); continue; }
    if (!f.size) { problems.push(`${f.name}: file is empty`); continue; }
    if (f.size > CFG.MAX_FILE_MB * 1048576) { problems.push(`${f.name}: over ${CFG.MAX_FILE_MB} MB`); continue; }
    if (state.files.some((x) => x.name === f.name && x.size === f.size)) { problems.push(`${f.name}: already added`); continue; }
    if (state.files.length >= CFG.MAX_FILES) { problems.push(`Limit of ${CFG.MAX_FILES} files reached`); break; }
    if (total + f.size > CFG.MAX_TOTAL_MB * 1048576) { problems.push(`${f.name}: total size limit reached`); break; }
    const ok = await looksLikeMidi(f);
    if (ok === null) { problems.push(`${f.name}: cannot be read (moved or deleted?)`); continue; }
    if (!ok) { problems.push(`${f.name}: corrupt or not real MIDI`); continue; }
    state.files.push(f); total += f.size;
  }
  renderFiles();
  if (problems.length) {
    showMsg("uploadMsg", `Skipped ${problems.length}: ${problems.slice(0, 3).join("; ")}${problems.length > 3 ? "…" : ""}`, "warning");
    toast(`${problems.length} file(s) skipped.`, "warn");
  } else showMsg("uploadMsg", "");
}

function renderFiles() {
  const box = $("fileList");
  box.replaceChildren(...state.files.map((f, i) => {
    const row = document.createElement("div");
    row.className = "file-item";
    const n = document.createElement("span");
    n.className = "name"; n.textContent = `🎼 ${f.name} (${mb(f.size)})`;
    const x = document.createElement("button");
    x.className = "btn-close"; x.setAttribute("aria-label", `Remove ${f.name}`);
    x.onclick = () => { state.files.splice(i, 1); renderFiles(); };
    row.append(n, x);
    return row;
  }));
  $("uploadBtn").disabled = !state.files.length || state.uploading;
}

function sendFiles(files) {
  return new Promise((resolve, reject) => {
    if (!navigator.onLine) return reject(new ApiError("You are offline. Check your connection.", "offline"));
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/upload");
    xhr.timeout = CFG.TIMEOUT.upload;
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) $("uploadBar").style.width = (e.loaded / e.total) * 100 + "%"; };
    xhr.onload = () => {
      let d = null; try { d = JSON.parse(xhr.responseText); } catch { /* not JSON */ }
      if (xhr.status >= 200 && xhr.status < 300 && d) resolve(d);
      else reject(new ApiError((d && d.error) || STATUS_MSG[xhr.status] || `Upload failed (HTTP ${xhr.status}).`, "http", xhr.status));
    };
    xhr.onerror = () => reject(new ApiError("Network error during upload.", "network"));
    xhr.ontimeout = () => reject(new ApiError("Upload timed out. Try fewer or smaller files.", "timeout"));
    xhr.onabort = () => reject(new ApiError("Upload cancelled.", "abort"));
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f, f.name));
    xhr.send(fd);
  });
}

async function upload() {
  if (!state.files.length) return;
  state.uploading = true; setBusy($("uploadBtn"), true);
  $("uploadProgress").classList.remove("d-none"); $("uploadBar").style.width = "0";
  showMsg("uploadMsg", "");
  try {
    const r = await sendFiles(state.files);
    state.fileCount += r.saved;
    $("fileCount").textContent = state.fileCount;
    state.files = []; renderFiles();
    showMsg("uploadMsg", `Uploaded ${r.saved} file(s).`, "success");
    toast("Upload complete.", "ok");
  } catch (e) { fail(e, "uploadMsg", upload); }
  finally {
    state.uploading = false; setBusy($("uploadBtn"), false);
    $("uploadBtn").disabled = !state.files.length;
    setTimeout(() => $("uploadProgress").classList.add("d-none"), 600);
  }
}

/* ---------- Step 2: training + status polling ---------- */
function setModelReady(ready) {
  state.modelReady = ready;
  const p = $("modelPill");
  p.textContent = ready ? "model ready" : "no model yet";
  p.classList.toggle("ready", ready);
}

function readEpochs() {
  const inp = $("epochs"), raw = inp.value.trim();
  const n = Number(raw);
  let err = "";
  if (!raw) err = "Enter the number of epochs.";
  else if (!Number.isInteger(n)) err = "Epochs must be a whole number.";
  else if (n < 1 || n > 300) err = "Epochs must be between 1 and 300.";
  inp.classList.toggle("is-invalid", !!err);
  $("epochsErr").textContent = err;
  return err ? null : n;
}

let pollTimer = null;
function poll(fails = 0) {
  clearTimeout(pollTimer);
  pollTimer = setTimeout(async () => {
    try {
      const s = await api("/status");
      setModelReady(s.model_ready);
      if (s.error) { endTraining(); return fail(new ApiError("Training failed: " + s.error, "http", 500), "trainMsg"); }
      if (s.running) { showMsg("trainMsg", s.message, "info"); return poll(0); }
      endTraining();
      showMsg("trainMsg", s.message, "success");
      toast("Training finished.", "ok");
    } catch (e) {
      if (fails + 1 >= CFG.POLL_MAX_FAILS) {
        endTraining();
        return fail(new ApiError("Lost contact with the server while training. It may still be running.", "network"), "trainMsg", () => { startPolling(); });
      }
      showMsg("trainMsg", `Reconnecting… (${fails + 1}/${CFG.POLL_MAX_FAILS})`, "warning");
      poll(fails + 1);
    }
  }, CFG.POLL_MS * (1 + fails));
}
function startPolling() {
  state.training = true; setBusy($("trainBtn"), true);
  $("trainProgress").classList.remove("d-none");
  showMsg("trainMsg", "Training in progress…", "info");
  poll(0);
}
function endTraining() {
  clearTimeout(pollTimer); state.training = false; setBusy($("trainBtn"), false);
  $("trainProgress").classList.add("d-none");
}

async function train() {
  const epochs = readEpochs();
  if (epochs === null) return;
  if (state.fileCount === 0) { showMsg("trainMsg", "Upload at least one MIDI file first.", "warning"); return toast("No training data yet.", "warn"); }
  setBusy($("trainBtn"), true);
  try {
    await api("/train", { method: "POST", body: { epochs } });
    startPolling();
  } catch (e) {
    if (e.status === 409) return startPolling(); // already running -> just follow it
    setBusy($("trainBtn"), false); fail(e, "trainMsg", train);
  }
}

/* ---------- Step 3: generation + player ---------- */
async function loadMidi(url) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), CFG.TIMEOUT.midi);
  try {
    const r = await fetch(url, { signal: ctrl.signal });
    if (!r.ok) throw new ApiError("The generated file could not be downloaded.", "http", r.status);
    const buf = await r.arrayBuffer();
    if (String.fromCharCode(...new Uint8Array(buf.slice(0, 4))) !== "MThd")
      throw new ApiError("The generated file is not valid MIDI. Try again.", "parse");
    return URL.createObjectURL(new Blob([buf], { type: "audio/midi" }));
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError(ctrl.signal.aborted ? "Downloading the music timed out." : "Network error while fetching the music.", "network");
  } finally { clearTimeout(t); }
}

let blobUrl = null, loadTimer = null;
async function generate() {
  if (!state.modelReady) { showMsg("genMsg", "Train a model first (step 2).", "warning"); return toast("No trained model yet.", "warn"); }
  const body = { length: Number($("length").value), temperature: Number($("temp").value), step: Number($("step").value) };
  if (Object.values(body).some((v) => !Number.isFinite(v))) return showMsg("genMsg", "Invalid settings. Reset the sliders.", "danger");
  setBusy($("genBtn"), true); $("eq").classList.add("on"); showMsg("genMsg", "Composing…", "info");
  try {
    const r = await api("/generate", { method: "POST", body, timeout: CFG.TIMEOUT.generate });
    const url = await loadMidi(r.midi);
    if (blobUrl) URL.revokeObjectURL(blobUrl);
    blobUrl = url;
    showResult(r);
    showMsg("genMsg", "Done! Press play.", "success");
  } catch (e) { fail(e, "genMsg", generate); }
  finally { setBusy($("genBtn"), false); $("eq").classList.remove("on"); }
}

function showResult(r) {
  $("result").classList.remove("d-none");
  $("dlMidi").href = r.midi;
  const wav = $("wavPlayer"), dl = $("dlWav");
  wav.classList.toggle("d-none", !r.wav); dl.classList.toggle("d-none", !r.wav);
  if (r.wav) { wav.src = r.wav; dl.href = r.wav; }

  const player = $("player");
  if (!window.customElements || !customElements.get("midi-player")) {
    player.classList.add("d-none");
    return toast("MIDI player failed to load. Download the file to listen.", "warn");
  }
  player.classList.remove("d-none");
  clearTimeout(loadTimer);
  loadTimer = setTimeout(() => toast("Player is slow to load (it needs internet for the sound font). You can download the MIDI instead.", "warn"), CFG.PLAYER_LOAD_MS);
  player.addEventListener("load", () => clearTimeout(loadTimer), { once: true });
  player.src = blobUrl;
  $("result").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

$("wavPlayer").addEventListener("error", () => {
  const code = $("wavPlayer").error ? $("wavPlayer").error.code : 0;
  const why = { 1: "was aborted", 2: "had a network problem", 3: "could not be decoded", 4: "is not supported by this device" }[code] || "failed";
  toast(`Audio playback ${why}. Use the MIDI player or download the file.`, "err");
});

/* ---------- Look & feel: theme, reveal, floating notes ---------- */
function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  document.documentElement.dataset.bsTheme = t;
  $("themeBtn").innerHTML = `<i class="bi bi-${t === "dark" ? "moon-stars" : "sun"}"></i>`;
  store.set("theme", t);
}

function initEffects() {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const items = document.querySelectorAll(".reveal");
  if (reduce || !("IntersectionObserver" in window)) items.forEach((el) => el.classList.add("in"));
  else {
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { threshold: 0.1 });
    items.forEach((el) => io.observe(el));
  }
  const lowEnd = (navigator.hardwareConcurrency || 4) <= 2 || (navigator.connection && navigator.connection.saveData);
  if (reduce || lowEnd) return; // save battery / CPU
  const chars = ["♪", "♫", "♩", "♬"], host = $("notes");
  for (let i = 0; i < 12; i++) {
    const n = document.createElement("span");
    n.className = "note"; n.textContent = chars[i % 4];
    n.style.cssText = `left:${Math.random() * 100}%;font-size:${16 + Math.random() * 26}px;animation-duration:${12 + Math.random() * 14}s;animation-delay:${-Math.random() * 20}s`;
    host.append(n);
  }
}

/* ---------- Init ---------- */
function init() {
  state.modelReady = document.body.dataset.modelReady === "true";
  state.fileCount = Number(document.body.dataset.fileCount) || 0;
  setModelReady(state.modelReady);
  applyTheme(store.get("theme") || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"));
  setOnline(); initEffects();
  if (!checkCompat()) return;
  window.addEventListener("load", checkLibraries);

  const dz = $("dropzone");
  $("files").addEventListener("change", (e) => { addFiles([...e.target.files]); e.target.value = ""; });
  ["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("over"); }));
  ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("over"); }));
  dz.addEventListener("drop", (e) => addFiles([...(e.dataTransfer ? e.dataTransfer.files : [])]));
  // stop the browser from opening a MIDI file dropped outside the zone
  ["dragover", "drop"].forEach((ev) => window.addEventListener(ev, (e) => e.preventDefault()));

  $("uploadBtn").onclick = upload;
  $("trainBtn").onclick = train;
  $("genBtn").onclick = generate;
  $("epochs").addEventListener("input", readEpochs);
  $("epochs").addEventListener("keydown", (e) => { if (e.key === "Enter") train(); });
  $("themeBtn").onclick = () => applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
  [["length", "lengthVal"], ["temp", "tempVal"], ["step", "stepVal"]].forEach(([i, o]) =>
    $(i).addEventListener("input", () => ($(o).textContent = $(i).value)));

  // resume progress display if the server is already training (e.g. page refresh)
  api("/status").then((s) => { setModelReady(s.model_ready); if (s.running) startPolling(); }).catch(() => {});
}

document.addEventListener("DOMContentLoaded", init);
})();
