"use strict";

// XUSB button bits (same values the virtual Xbox 360 controller uses).
const BITS = {
  UP: 0x0001, DOWN: 0x0002, LEFT: 0x0004, RIGHT: 0x0008,
  START: 0x0010, BACK: 0x0020, LS: 0x0040, RS: 0x0080,
  LB: 0x0100, RB: 0x0200, GUIDE: 0x0400,
  A: 0x1000, B: 0x2000, X: 0x4000, Y: 0x8000,
};
const PLAYER_COLORS = ["#4f8cff", "#e8574f", "#5ac85a", "#f2c230"];
const DOUBLE_TAP_MS = 300;
const AXIS_MAX = 32767;

const $ = (s) => document.querySelector(s);
const pad = $("#pad");
const overlay = $("#overlay");
const isIOS = /iPhone|iPad|iPod/.test(navigator.userAgent) ||
  (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
const standalone = navigator.standalone === true ||
  matchMedia("(display-mode: standalone), (display-mode: fullscreen)").matches;

// ---- touch tracking -------------------------------------------------------

// pointerId -> { kind: "btn", name } | { kind: "stick", which, ox, oy, x, y, click, t0 } | { kind: "dpad", bits }
const pointers = new Map();
const lastTap = { L: 0, R: 0 };
let prevButtons = 0;

// Face buttons get a touch area bigger than the drawn circle: a touch picks the
// closest of A/B/X/Y if it lands within FACE_REACH button-widths of its center.
const FACE_REACH = 0.85;
function faceHit(x, y) {
  let best = null, bestD = Infinity;
  for (const el of document.querySelectorAll("#face [data-btn]")) {
    const r = el.getBoundingClientRect();
    const d = Math.hypot(x - (r.left + r.width / 2), y - (r.top + r.height / 2));
    if (d < r.width * FACE_REACH && d < bestD) { best = el; bestD = d; }
  }
  return best;
}

function stickRadius() { return window.innerHeight * 0.13; }

function dpadBits(x, y) {
  const r = $("#dpad").getBoundingClientRect();
  const dx = x - (r.left + r.width / 2);
  const dy = y - (r.top + r.height / 2);
  const mag = Math.hypot(dx, dy);
  if (mag < r.width * 0.1) return 0;
  const cx = dx / mag, cy = dy / mag;
  // 0.38 ~= cos(67.5deg): each direction covers 135deg, so diagonals overlap by 45deg.
  let b = 0;
  if (cx > 0.38) b |= BITS.RIGHT;
  if (cx < -0.38) b |= BITS.LEFT;
  if (cy < -0.38) b |= BITS.UP;
  if (cy > 0.38) b |= BITS.DOWN;
  return b;
}

function placeBase(which, x, y) {
  const zone = which === "L" ? $("#lzone") : $("#rzone");
  const base = zone.querySelector(".base");
  if (x == null) {
    base.style.left = base.style.top = "";
  } else {
    const r = zone.getBoundingClientRect();
    base.style.left = (x - r.left) + "px";
    base.style.top = (y - r.top) + "px";
  }
}

function moveKnob(which, x, y) {
  const zone = which === "L" ? $("#lzone") : $("#rzone");
  const knob = zone.querySelector(".knob");
  const r = stickRadius();
  knob.style.transform = `translate(${x * r}px, ${-y * r}px)`;
}

pad.addEventListener("pointerdown", (e) => {
  e.preventDefault();
  const t = e.target;
  // A direct hit on any button wins; otherwise the enlarged face-button areas apply.
  const btn = t.closest("[data-btn]") || faceHit(e.clientX, e.clientY);
  const stick = t.closest("[data-stick]");
  const dpad = t.closest("[data-dpad]");
  if (btn) {
    pointers.set(e.pointerId, { kind: "btn", name: btn.dataset.btn });
  } else if (stick) {
    const which = stick.dataset.stick;
    const click = performance.now() - lastTap[which] < DOUBLE_TAP_MS;
    pointers.set(e.pointerId, { kind: "stick", which, ox: e.clientX, oy: e.clientY, x: 0, y: 0, moved: 0, click, t0: performance.now() });
    placeBase(which, e.clientX, e.clientY);
  } else if (dpad) {
    pointers.set(e.pointerId, { kind: "dpad", bits: dpadBits(e.clientX, e.clientY) });
  } else {
    return;
  }
  try { pad.setPointerCapture(e.pointerId); } catch (_) {}
  changed();
});

pad.addEventListener("pointermove", (e) => {
  const p = pointers.get(e.pointerId);
  if (!p) return;
  if (p.kind === "stick") {
    const r = stickRadius();
    let x = (e.clientX - p.ox) / r, y = -(e.clientY - p.oy) / r;
    const m = Math.hypot(x, y);
    if (m > 1) { x /= m; y /= m; }
    p.x = x; p.y = y; p.moved = Math.max(p.moved, Math.min(m, 1));
  } else if (p.kind === "dpad") {
    p.bits = dpadBits(e.clientX, e.clientY);
  } else if (p.kind === "btn") {
    // Let a thumb roll between face buttons, like on a real pad.
    const btn = faceHit(e.clientX, e.clientY);
    const fromFace = $("#face").contains(document.querySelector(`[data-btn="${p.name}"]`));
    if (btn && fromFace) p.name = btn.dataset.btn;
  }
  changed();
});

function endPointer(e) {
  const p = pointers.get(e.pointerId);
  if (!p) return;
  pointers.delete(e.pointerId);
  if (p.kind === "stick") {
    const quick = performance.now() - p.t0 < 200 && p.moved < 0.3;
    lastTap[p.which] = quick && !p.click ? performance.now() : 0;
    placeBase(p.which, null);
  }
  changed();
}
pad.addEventListener("pointerup", endPointer);
pad.addEventListener("pointercancel", endPointer);
pad.addEventListener("lostpointercapture", endPointer);
pad.addEventListener("contextmenu", (e) => e.preventDefault());
document.addEventListener("gesturestart", (e) => e.preventDefault());

function releaseAll() {
  pointers.clear();
  placeBase("L", null); placeBase("R", null);
  changed();
  flush(true);
}
document.addEventListener("visibilitychange", () => { if (document.hidden) releaseAll(); });
window.addEventListener("blur", releaseAll);

// ---- state ---------------------------------------------------------------

function computeState() {
  let b = 0, lt = 0, rt = 0;
  const sticks = { L: [0, 0], R: [0, 0] };
  for (const p of pointers.values()) {
    if (p.kind === "btn") {
      if (p.name === "LT") lt = 255;
      else if (p.name === "RT") rt = 255;
      else b |= BITS[p.name];
    } else if (p.kind === "dpad") {
      b |= p.bits;
    } else {
      sticks[p.which] = [p.x, p.y];
      if (p.click) b |= p.which === "L" ? BITS.LS : BITS.RS;
    }
  }
  const ax = (v) => Math.round(v * AXIS_MAX);
  return [b, lt, rt, ax(sticks.L[0]), ax(sticks.L[1]), ax(sticks.R[0]), ax(sticks.R[1])];
}

let state = computeState();
let dirty = false;
let lastTriggers = [0, 0];

function changed() {
  state = computeState();
  render();
  const pressed = state[0] & ~prevButtons;
  if ((pressed || (state[1] && !lastTriggers[0]) || (state[2] && !lastTriggers[1])) && navigator.vibrate) {
    navigator.vibrate(8);
  }
  const buttonsChanged = state[0] !== prevButtons || state[1] !== lastTriggers[0] || state[2] !== lastTriggers[1];
  prevButtons = state[0];
  lastTriggers = [state[1], state[2]];
  dirty = true;
  // Buttons go out right away so even a very quick tap registers; stick motion is batched per frame.
  if (buttonsChanged) flush(true);
}

function render() {
  const [b, lt, rt] = state;
  document.querySelectorAll("[data-btn]").forEach((el) => {
    const n = el.dataset.btn;
    const on = n === "LT" ? lt > 0 : n === "RT" ? rt > 0 : (b & BITS[n]) !== 0;
    el.classList.toggle("on", on);
  });
  for (const [cls, bit] of [["up", BITS.UP], ["down", BITS.DOWN], ["left", BITS.LEFT], ["right", BITS.RIGHT]]) {
    $("#dpad ." + cls).classList.toggle("on", (b & bit) !== 0);
  }
  for (const which of ["L", "R"]) {
    const p = [...pointers.values()].find((q) => q.kind === "stick" && q.which === which);
    const zone = which === "L" ? $("#lzone") : $("#rzone");
    zone.classList.toggle("active", !!p);
    zone.classList.toggle("click", !!(p && p.click));
    moveKnob(which, p ? p.x : 0, p ? p.y : 0);
  }
}

// ---- network -------------------------------------------------------------

// localStorage can be missing or throw (private browsing); everything works without it.
function load(key) {
  try { return localStorage.getItem(key); } catch (_) { return null; }
}
function save(key, value) {
  try { localStorage.setItem(key, value); } catch (_) {}
}

let clientId = load("seidr-id");
if (!clientId) { clientId = Math.random().toString(36).slice(2); save("seidr-id", clientId); }

let myName = load("seidr-name") || "";

function showName(name) {
  myName = name || "";
  save("seidr-name", myName);
  const el = $("#pname");
  el.textContent = myName || "tap to name";
  el.classList.toggle("unset", !myName);
}
showName(myName);

$("#pname").addEventListener("pointerdown", (e) => e.stopPropagation()); // not a controller input
$("#pname").addEventListener("click", () => {
  const name = prompt("Name this controller", myName);
  if (name === null) return;
  showName(name.trim().slice(0, 16));
  send({ setname: myName });
});

let ws = null;
let started = false;
let paused = false; // game full, or this controller moved to another tab/app: don't auto-reconnect

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

function flush(force) {
  if (dirty || force) { send({ s: state }); dirty = false; }
}

function loop() { flush(false); requestAnimationFrame(loop); }
requestAnimationFrame(loop);
setInterval(() => flush(true), 1000); // keepalive, and heals any lost update
let latency = null;
setInterval(() => send({ ping: performance.now(), lat: latency }), 2000);

function setPlayer(n) {
  $("#player").textContent = "P" + n;
  document.documentElement.style.setProperty("--accent", PLAYER_COLORS[(n - 1) % 4]);
}

function connect() {
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onopen = () => {
    send({ hello: clientId, standalone, name: myName });
    send({ ping: performance.now() });
  };
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.full) {
      paused = true;
      showOverlay("Game is full", "4 phones are already connected. Tap to try again when someone leaves.");
    }
    if (m.replaced) {
      paused = true;
      releaseAll();
      showOverlay("Opened somewhere else", "This controller is now open in another tab or app. Tap to use it here instead.");
    }
    if (typeof m.name === "string" && (m.name || !m.slot)) showName(m.name);
    if (m.slot) {
      setPlayer(typeof m.led === "number" && m.led < 4 ? m.led + 1 : m.slot);
      $("#net").textContent = "connected";
      if (started) hideOverlay();
      flush(true);
    }
    if (typeof m.led === "number" && m.led < 4 && !m.slot) setPlayer(m.led + 1);
    if (m.pong) {
      latency = Math.round(performance.now() - m.pong);
      $("#net").textContent = latency + " ms";
    }
    if (m.r && navigator.vibrate) navigator.vibrate(Math.max(m.r[0], m.r[1]) > 20 ? 10000 : 0);
  };
  ws.onclose = () => {
    ws = null;
    $("#net").textContent = "reconnecting";
    if (navigator.vibrate) navigator.vibrate(0);
    if (started && !paused) showOverlay("Reconnecting", "Check that this phone is on the same Wi-Fi as the PC.");
    setTimeout(() => { if (!paused) connect(); }, 1500);
  };
}

// ---- start / full screen -------------------------------------------------

function showOverlay(title, text) {
  $("#ov-title").textContent = title;
  $("#ov-text").textContent = text;
  overlay.hidden = false;
}
function hideOverlay() { overlay.hidden = true; }

if (isIOS && !standalone) $("#ov-ios").hidden = false;

overlay.addEventListener("click", async () => {
  if (paused) { paused = false; started = true; if (!ws) connect(); showOverlay("Connecting", ""); return; }
  started = true;
  if (ws && ws.readyState === WebSocket.OPEN) hideOverlay();
  else showOverlay("Connecting", "Check that this phone is on the same Wi-Fi as the PC.");
  const el = document.documentElement;
  try {
    if (el.requestFullscreen && !document.fullscreenElement) await el.requestFullscreen({ navigationUI: "hide" });
    if (screen.orientation && screen.orientation.lock) await screen.orientation.lock("landscape");
  } catch (_) { /* iPhone Safari has neither; Home Screen mode covers it */ }
});

render();
connect();
