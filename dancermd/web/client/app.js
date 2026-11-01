'use strict';

/* DanceRMD phone client: renders the PC screen, turns touches into mouse and keyboard input,
   and drives the window switcher and system controls. Protocol: docs/protocol.md. */

/* =========================================================================
   Utilities
   ========================================================================= */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const T = (key, params) => I18N.t(key, params);
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
const midpoint = (a, b) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });
const buzz = (ms = 10) => { try { navigator.vibrate?.(ms); } catch { /* unsupported */ } };

// localStorage may be unavailable (private mode, blocked storage), so every access is guarded
const STORE_PREFIX = 'drmd.';
const LEGACY_PREFIX = 'rl.';  // "Remote Laptop" 1.x
const store = {
  get(key, fallback) {
    try { const v = localStorage.getItem(STORE_PREFIX + key); return v === null ? fallback : JSON.parse(v); } catch { return fallback; }
  },
  set(key, value) { try { localStorage.setItem(STORE_PREFIX + key, JSON.stringify(value)); } catch { /* ignore */ } },
  del(key) { try { localStorage.removeItem(STORE_PREFIX + key); } catch { /* ignore */ } },
  migrate() {  // keep the paired token and preferences from version 1.x (same origin)
    try {
      for (const key of Object.keys(localStorage)) {
        if (!key.startsWith(LEGACY_PREFIX)) continue;
        const name = key.slice(LEGACY_PREFIX.length);
        if (localStorage.getItem(STORE_PREFIX + name) === null) localStorage.setItem(STORE_PREFIX + name, localStorage.getItem(key));
        localStorage.removeItem(key);
      }
    } catch { /* ignore */ }
  },
};
store.migrate();

const settings = {
  mode: store.get('mode', 'touchpad'),  // 'touchpad' | 'direct'
  quality: store.get('quality', 'medium'),
  stream: store.get('stream', true),
  monitor: store.get('monitor', 0),     // 0 = the PC's primary display
  speed: store.get('speed', 1.6),
  live: store.get('live', true),
  codec: store.get('codec', 'auto'),    // 'auto' = H.264 when possible, 'jpeg'
  lang: store.get('lang', 'auto'),
};
function setSetting(key, value) { settings[key] = value; store.set(key, value); }

I18N.setLanguage(settings.lang);

const appEl = $('#app');
const surface = $('#surface');
const canvas = $('#screen');
const ctx = canvas.getContext('2d');

/* =========================================================================
   WebSocket connection
   ========================================================================= */
const CLOSE_AUTH_FAILED = 4001;
const CLOSE_KICKED = 4002;
const CLOSE_TOKEN_CHANGED = 4003;
let ws = null;
let authed = false;
let retryDelay = 500;
let retryTimer = null;
let monitors = [];
let currentMonitor = 1;
let hostName = '';
let connState = 'connecting';
let pingMs = null;

function takeTokenFromUrl() {
  const m = location.hash.match(/[#&]k=([^&]+)/);
  if (m) {
    store.set('token', decodeURIComponent(m[1]));
    history.replaceState(null, '', location.pathname);  // keep the token out of the address bar
  }
}

function connect() {
  clearTimeout(retryTimer);
  const token = store.get('token', '');
  if (!token) { showLogin(); return; }
  setStatus('connecting');
  const sock = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`);
  ws = sock;
  sock.binaryType = 'arraybuffer';
  sock.onopen = () => sock.send(JSON.stringify({ t: 'auth', token }));
  sock.onmessage = (e) => {
    if (sock !== ws) return;
    if (typeof e.data === 'string') onMessage(JSON.parse(e.data));
    else onBinary(e.data);
  };
  sock.onclose = (e) => {
    if (sock !== ws) return;
    authed = false;
    if (e.code === CLOSE_AUTH_FAILED) return;  // the sign-in screen is already showing
    if (e.code === CLOSE_KICKED) {             // disconnected from the dashboard: don't reconnect
      setStatus('kicked');
      $('#kicked').hidden = false;
      return;
    }
    if (e.code === CLOSE_TOKEN_CHANGED) {
      store.del('token');
      showLogin(T('token_changed'));
      return;
    }
    setStatus('offline');
    retryTimer = setTimeout(connect, retryDelay);
    retryDelay = Math.min(retryDelay * 2, 5000);
  };
}

function send(msg) {
  if (authed && ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
}

function onMessage(m) {
  switch (m.t) {
    case 'hello':
      authed = true;
      retryDelay = 500;
      hostName = m.host;
      $('#login').hidden = true;
      setStatus('online');
      setMonitors(m.monitors, m.monitor);
      setBattery(m.battery);
      startStream();
      send({ t: 'windows', on: true });  // feed the quick-switch strip
      break;
    case 'auth_fail':
      store.del('token');
      showLogin(I18N.message(m.reason));
      break;
    case 'monitors':
      setMonitors(m.monitors, m.monitor);
      break;
    case 'cursor':
      cursor = { x: m.x, y: m.y };
      followCursor();
      scheduleRender();
      break;
    case 'sys':
      setBattery(m.battery);
      break;
    case 'brightness':
      setBrightness(m.value);
      break;
    case 'clipboard':
      receiveClipboard(m.text);
      break;
    case 'toast':
      toast(I18N.message(m), m.error);
      break;
    case 'pong':
      pingMs = Math.round(performance.now() - m.ts);
      updateConnInfo();
      break;
    case 'video':  // the H.264 encoder (re)started; a keyframe follows
      if (h264Supported) setupDecoder(m.config);
      break;
    case 'stream':
      streamInfo = m;
      updateCodecInfo();
      if (m.monitor && m.monitor !== currentMonitor) {  // followed a window to another display
        currentMonitor = m.monitor;
        $('#opt-monitor').value = m.monitor;
        view.z = 1;
        updateZoomBadge();
        updateMonitorBadge();
        toast(T('monitor.switched', { n: m.monitor }));
      }
      break;
    case 'windows':
      win.list = m.list;
      win.multi = m.multi;
      Object.assign(win.icons, m.icons);
      renderStrip();
      if (!switcherEl.hidden) { renderGrid(); requestThumbs(); }
      break;
    case 'thumb':
      win.thumbs[m.id] = m.data;
      if (!switcherEl.hidden) renderGrid();
      break;
    case 'activated':
      $$('.win-chip.pending, .win-card.pending').forEach((n) => n.classList.remove('pending'));
      if (!m.ok) toast(I18N.message(m.reason) || T('windows.switch_failed'), true);
      else if (!showingScreen()) toast(T('windows.switched', { title: m.title }));
      break;
    case 'uipi':  // an elevated window blocks input (null title = no longer blocked)
      uipi = m.title ? m : null;
      renderUipi();
      if (uipi) buzz(30);
      break;
  }
}

const STATUS_TEXT = { online: 'status.online', connecting: 'status.connecting', offline: 'status.offline', kicked: 'status.kicked' };

function setStatus(state) {
  connState = state;
  const cls = 'status ' + (state === 'kicked' ? 'offline' : state);
  const dot = $('#status');
  dot.className = cls;
  dot.title = T(STATUS_TEXT[state] || 'status.offline');
  $('#status-rail').className = cls;  // copy on the landscape rail
  $('#host').textContent = state === 'online' ? hostName
    : state === 'connecting' ? T('status.connecting')
    : state === 'kicked' ? T('status.kicked')
    : state === 'signed_out' ? T('status.not_connected') : T('status.retrying');
  updateHint();
}

function showLogin(error) {
  setStatus('signed_out');
  $('#login').hidden = false;
  $('#login-error').textContent = error || '';
}

$('#login-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const value = $('#login-token').value.trim();
  if (!value) return;
  const fromUrl = value.match(/[#&]k=([^&\s]+)/);  // a pasted link works too
  store.set('token', fromUrl ? decodeURIComponent(fromUrl[1]) : value);
  $('#login-error').textContent = '';
  connect();
});

$('#reconnect').addEventListener('click', () => {
  $('#kicked').hidden = true;
  connect();
});

let battery = null;
function setBattery(b) {
  battery = b;
  const el = $('#battery');
  el.hidden = !b;
  const rail = $('#battery-rail');
  rail.textContent = b ? `${b.percent}%` : '';
  rail.className = b && b.charging ? 'charging' : b && b.percent <= 20 ? 'low' : '';
  if (!b) return;
  $('#battery-text').textContent = `${b.percent}%`;
  $('#battery-bolt').hidden = !b.charging;
  el.classList.toggle('low', b.percent <= 20 && !b.charging);
  el.title = T(b.charging ? 'battery.charging' : 'battery.label');
}

function monitorName(m) { return m.name || T('monitor.name', { n: m.index }); }

function setMonitors(list, serverDefault) {
  monitors = list;
  const sel = $('#opt-monitor');
  sel.replaceChildren(...list.map((m) => {
    const opt = document.createElement('option');
    opt.value = m.index;
    opt.textContent = `${m.index}. ${monitorName(m)} — ${m.width}×${m.height}${m.primary ? T('monitor.primary') : ''}`;
    return opt;
  }));
  currentMonitor = list.some((m) => m.index === settings.monitor) ? settings.monitor : serverDefault;
  sel.value = currentMonitor;
  $('#monitor-field').hidden = list.length < 2;
  updateMonitorBadge();
}

function selectMonitor(index) {
  currentMonitor = index;
  setSetting('monitor', index);
  $('#opt-monitor').value = index;
  view.z = 1;
  updateZoomBadge();
  updateMonitorBadge();
  send({ t: 'stream', monitor: index });
}

function updateMonitorBadge() {
  const badge = $('#mon-badge');
  badge.hidden = monitors.length < 2 || !settings.stream;
  $('span', badge).textContent = T('monitor.badge', { n: currentMonitor, total: monitors.length });
}

function startStream() {
  send({ t: 'stream', on: settings.stream && !document.hidden, monitor: currentMonitor,
         quality: settings.quality, codec: wantedCodec() });
}

document.addEventListener('visibilitychange', () => {
  if (!authed) {
    if (!document.hidden && (!ws || ws.readyState === WebSocket.CLOSED) && store.get('token', '')) connect();
    return;
  }
  send({ t: 'stream', on: settings.stream && !document.hidden });
});

setInterval(() => send({ t: 'ping', ts: performance.now() }), 5000);

/* =========================================================================
   Screen rendering
   ========================================================================= */
const view = { img: null, iw: 16, ih: 9, z: 1, x: 0, y: 0 };
let cursor = null;
let renderQueued = false;

/* Binary frames start with a type byte: 1 JPEG, 2 H.264 keyframe, 3 H.264 delta frame.
   H.264 is decoded by WebCodecs (the phone's hardware decoder), which requires HTTPS. */
const FRAME_JPEG = 1;
const FRAME_H264_KEY = 2;
let h264Supported = false;
let decoder = null;
let needKey = true;
let keyRequested = false;
let chunkTs = 0;
let streamInfo = null;

async function detectH264() {
  if (!window.isSecureContext || !('VideoDecoder' in window)) return false;
  try {
    return !!(await VideoDecoder.isConfigSupported({ codec: 'avc1.4D4028', optimizeForLatency: true })).supported;
  } catch {
    return false;
  }
}

function wantedCodec() { return settings.codec === 'auto' && h264Supported ? 'h264' : 'jpeg'; }

function setupDecoder(codec) {
  try { decoder?.close(); } catch { /* already closed */ }
  needKey = true;
  keyRequested = false;
  decoder = new VideoDecoder({
    output: (frame) => { if (settings.stream) showImage(frame); else frame.close(); },
    error: (err) => {
      console.warn('H.264 decode error:', err);
      decoder = null;
      h264Supported = false;  // fall back to JPEG until the page reloads
      toast(T('h264.decode_failed'), true);
      send({ t: 'stream', codec: 'jpeg' });
    },
  });
  decoder.configure({ codec, optimizeForLatency: true });
}

function onBinary(buf) {
  const kind = new Uint8Array(buf, 0, 1)[0];
  const data = new Uint8Array(buf, 1);
  if (kind === FRAME_JPEG) {
    createImageBitmap(new Blob([data], { type: 'image/jpeg' }))
      .then((bmp) => { if (settings.stream) showImage(bmp); else bmp.close(); })
      .catch(() => { /* corrupt frame: skip */ })
      .finally(() => { if (!document.hidden) send({ t: 'next' }); });  // ask for more once drawn: matches network speed
    return;
  }
  if (!document.hidden) send({ t: 'next' });  // H.264 decodes quickly: acknowledge right away
  const key = kind === FRAME_H264_KEY;
  if (!decoder || decoder.state !== 'configured') return;
  if (needKey && !key) {
    if (!keyRequested) { keyRequested = true; send({ t: 'keyframe' }); }
    return;
  }
  needKey = false;
  chunkTs += 33333;
  try {
    decoder.decode(new EncodedVideoChunk({ type: key ? 'key' : 'delta', timestamp: chunkTs, data }));
  } catch {
    needKey = true;
    keyRequested = false;
  }
}

function showImage(img) {
  const w = img.displayWidth ?? img.width;
  const h = img.displayHeight ?? img.height;
  view.img?.close();
  view.img = img;
  if (w !== view.iw || h !== view.ih) {
    view.iw = w;
    view.ih = h;
    clampView();
    updateHint();
  }
  scheduleRender();
}

function updateCodecInfo() {
  const el = $('#codec-info');
  if (!streamInfo) { el.textContent = ''; return; }
  const what = streamInfo.codec === 'h264' ? `H.264 · ${streamInfo.encoder}` : 'JPEG';
  let note = '';
  if (streamInfo.codec !== 'h264' && settings.codec === 'auto') {
    note = T(window.isSecureContext ? 'codec.no_browser' : 'codec.needs_https');
  }
  el.textContent = T('codec.using', { what, capture: streamInfo.capture }) + note;
}

function surfaceSize() { return { w: surface.clientWidth, h: surface.clientHeight }; }

function displayRect() {
  const { w, h } = surfaceSize();
  const fit = Math.min(w / view.iw, h / view.ih);
  return { x: view.x, y: view.y, w: view.iw * fit * view.z, h: view.ih * fit * view.z };
}

function clampView() {
  const { w, h } = surfaceSize();
  const r = displayRect();
  view.x = r.w <= w ? (w - r.w) / 2 : clamp(view.x, w - r.w, 0);
  view.y = r.h <= h ? (h - r.h) / 2 : clamp(view.y, h - r.h, 0);
}

function toNorm(p) {
  const r = displayRect();
  return { x: (p.x - r.x) / r.w, y: (p.y - r.y) / r.h };
}

function scheduleRender() {
  if (!renderQueued) { renderQueued = true; requestAnimationFrame(render); }
}

function render() {
  renderQueued = false;
  const dpr = window.devicePixelRatio || 1;
  const { w, h } = surfaceSize();
  const cw = Math.round(w * dpr), ch = Math.round(h * dpr);
  if (canvas.width !== cw || canvas.height !== ch) { canvas.width = cw; canvas.height = ch; }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  if (!showingScreen()) return;
  const r = displayRect();
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(view.img, r.x, r.y, r.w, r.h);
  if (cursor && cursor.x >= 0 && cursor.x <= 1 && cursor.y >= 0 && cursor.y <= 1) {
    drawCursor(r.x + cursor.x * r.w, r.y + cursor.y * r.h);
  }
}

function drawCursor(x, y) {
  ctx.save();
  ctx.translate(x, y);
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.lineTo(0, 17);
  ctx.lineTo(4.5, 13);
  ctx.lineTo(7.5, 19.5);
  ctx.lineTo(10.2, 18.4);
  ctx.lineTo(7.3, 12);
  ctx.lineTo(12.5, 12);
  ctx.closePath();
  ctx.lineJoin = 'round';
  ctx.lineWidth = 1.6;
  ctx.strokeStyle = '#000';
  ctx.fillStyle = '#fff';
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

function showingScreen() { return settings.stream && !!view.img; }

function updateHint() {
  const hint = $('#hint');
  hint.hidden = showingScreen() && authed;
  if (hint.hidden) return;
  $('#hint-title').textContent = !authed ? T(connState === 'connecting' ? 'status.connecting' : 'status.not_connected')
    : T(settings.stream ? 'hint.loading' : 'hint.touchpad');
}

/* While zoomed in touchpad mode, pan so the pointer stays visible */
function followCursor() {
  if (view.z <= 1 || isDirect() || !cursor) return;
  const { w, h } = surfaceSize();
  const r = displayRect();
  const margin = 48;
  const cx = r.x + cursor.x * r.w, cy = r.y + cursor.y * r.h;
  if (cx < margin) view.x += margin - cx; else if (cx > w - margin) view.x -= cx - (w - margin);
  if (cy < margin) view.y += margin - cy; else if (cy > h - margin) view.y -= cy - (h - margin);
  clampView();
}

function updateZoomBadge() {
  const badge = $('#zoom-badge');
  badge.hidden = view.z <= 1.01;
  badge.textContent = T('zoom.badge', { z: view.z.toFixed(1) });
}

$('#zoom-badge').addEventListener('click', () => {
  view.z = 1;
  clampView();
  updateZoomBadge();
  scheduleRender();
});

$('#mon-badge').addEventListener('click', () => {
  if (monitors.length > 1) selectMonitor((currentMonitor % monitors.length) + 1);
});

new ResizeObserver(() => { clampView(); scheduleRender(); }).observe(surface);

/* =========================================================================
   Pointer output, batched per animation frame so the network isn't flooded
   ========================================================================= */
const SCROLL_GAIN = 3;  // wheel units per swiped pixel (120 = one notch)
const pending = { mx: 0, my: 0, sx: 0, sy: 0, abs: null };
let flushQueued = false;

function queueFlush() {
  if (!flushQueued) { flushQueued = true; requestAnimationFrame(flush); }
}

function flush() {
  flushQueued = false;
  if (pending.abs) {
    send({ t: 'moveto', x: +pending.abs.x.toFixed(5), y: +pending.abs.y.toFixed(5) });
    pending.abs = null;
  }
  const mx = Math.trunc(pending.mx), my = Math.trunc(pending.my);
  if (mx || my) { send({ t: 'move', dx: mx, dy: my }); pending.mx -= mx; pending.my -= my; }
  const sx = Math.trunc(pending.sx), sy = Math.trunc(pending.sy);
  if (sx || sy) { send({ t: 'scroll', dx: sx, dy: sy }); pending.sx -= sx; pending.sy -= sy; }
}

// Clicks and key presses must follow any queued pointer movement
function sendNow(msg) { flush(); send(msg); }
function queueMove(dx, dy) { pending.mx += dx; pending.my += dy; queueFlush(); }
function queueScroll(dx, dy) { pending.sx -= dx * SCROLL_GAIN; pending.sy += dy * SCROLL_GAIN; queueFlush(); }
function moveAbs(p) {
  const n = toNorm(p);
  pending.abs = { x: clamp(n.x, 0, 1), y: clamp(n.y, 0, 1) };
  queueFlush();
}

/* =========================================================================
   Gestures on the screen surface
   ========================================================================= */
const TAP_MS = 260;
const TAP_SLOP = 10;
const LONG_MS = 480;
const DOUBLE_TAP_MS = 320;
const SWIPE3_MIN = 50;
const pointers = new Map();
let g = null;  // gesture in progress
let lastTap = { t: 0, x: 0, y: 0 };

function isDirect() { return settings.mode === 'direct' && showingScreen(); }

function localPos(e) {
  const r = surface.getBoundingClientRect();
  return { x: e.clientX - r.left, y: e.clientY - r.top };
}

surface.addEventListener('pointerdown', (e) => {
  if (e.target.closest('.surface-ui > *') || (e.pointerType === 'mouse' && e.button !== 0)) return;
  surface.setPointerCapture(e.pointerId);
  pointers.set(e.pointerId, localPos(e));
  if (pointers.size === 1) startOne(localPos(e));
  else if (pointers.size === 2) startTwo();
  else if (g) {
    g.fingers = Math.max(g.fingers, pointers.size);
    if (pointers.size === 3) g.tri = centroid();  // a three-finger gesture starts
  }
});

surface.addEventListener('pointermove', (e) => {
  if (!pointers.has(e.pointerId)) return;
  const prev = pointers.get(e.pointerId);
  const p = localPos(e);
  pointers.set(e.pointerId, p);
  if (!g) return;
  if (g.kind === 'one') moveOne(p, prev, e.timeStamp);
  else if (pointers.size === 2) moveTwo();
  else if (pointers.size >= 3) moveThree();
});

function centroid() {
  const pts = [...pointers.values()];
  return { x: pts.reduce((s, p) => s + p.x, 0) / pts.length, y: pts.reduce((s, p) => s + p.y, 0) / pts.length };
}

/* Like a Windows precision touchpad: three fingers sideways = previous window, up = window list */
function moveThree() {
  if (!g.tri || g.triDone) return;
  const c = centroid();
  const dx = c.x - g.tri.x, dy = c.y - g.tri.y;
  if (Math.hypot(dx, dy) < SWIPE3_MIN) return;
  g.triDone = true;
  g.moved = true;  // not a three-finger tap (middle click)
  if (Math.abs(dx) > Math.abs(dy)) switchToPrevious();
  else if (dy < 0) openSwitcher();
}

function endPointer(e) {
  if (!pointers.delete(e.pointerId)) return;
  if (pointers.size === 0 && g) {
    finishGesture(e.type === 'pointercancel');
    g = null;
  }
}
surface.addEventListener('pointerup', endPointer);
surface.addEventListener('pointercancel', endPointer);
surface.addEventListener('contextmenu', (e) => e.preventDefault());

function startOne(p) {
  const now = performance.now();
  g = {
    kind: 'one', fingers: 1, t0: now, lastT: now, start: p,
    moved: false, long: false, dragging: false,
    afterTap: now - lastTap.t < DOUBLE_TAP_MS && dist(p, lastTap) < 45,
  };
  const gesture = g;
  gesture.longTimer = setTimeout(() => {
    if (g === gesture && !gesture.moved) { gesture.long = true; buzz(25); }
  }, LONG_MS);
}

function moveOne(p, prev, t) {
  if (!g.moved) {
    if (dist(p, g.start) < TAP_SLOP) return;
    g.moved = true;
    clearTimeout(g.longTimer);
  }
  const dx = p.x - prev.x, dy = p.y - prev.y;
  if (isDirect()) {
    if (g.long) {                      // hold, then drag = drag and drop from the touched point
      if (!g.dragging) {
        g.dragging = true;
        moveAbs(g.start);
        sendNow({ t: 'button', button: 'left', down: true });
      }
      moveAbs(p);
    } else {                           // one-finger drag pans the zoomed image
      view.x += dx;
      view.y += dy;
      clampView();
      scheduleRender();
    }
  } else {
    if ((g.afterTap || g.long) && !g.dragging) {
      g.dragging = true;
      sendNow({ t: 'button', button: 'left', down: true });
    }
    // Acceleration: fast swipes travel further, slow ones stay precise
    const speed = Math.hypot(dx, dy) / Math.max(1, t - g.lastT);
    const gain = settings.speed * (1 + Math.min(speed, 2.5) * 1.2);
    queueMove(dx * gain, dy * gain);
  }
  g.lastT = t;
}

function startTwo() {
  if (g?.kind === 'one') {
    clearTimeout(g.longTimer);
    if (g.dragging) sendNow({ t: 'button', button: 'left', down: false });
  }
  const [a, b] = [...pointers.values()];
  g = {
    kind: 'two', fingers: 2, t0: g?.t0 ?? performance.now(),
    mid0: midpoint(a, b), midLast: midpoint(a, b), d0: dist(a, b), mode: null, moved: false,
  };
}

function moveTwo() {
  const [a, b] = [...pointers.values()];
  const m = midpoint(a, b);
  const d = dist(a, b);
  if (!g.mode) {
    const pinch = Math.abs(d - g.d0);
    const pan = dist(m, g.mid0);
    if (Math.max(pinch, pan) < 14) return;
    g.moved = true;
    g.mode = pinch > pan * 1.2 && showingScreen() ? 'pinch' : 'scroll';
    if (g.mode === 'pinch') {
      g.z0 = view.z;
      g.pd0 = d;
      g.anchor = toNorm(m);
      g.midLast = m;
    }
  }
  if (g.mode === 'scroll') {
    queueScroll(m.x - g.midLast.x, m.y - g.midLast.y);
  } else {
    view.z = clamp(g.z0 * d / g.pd0, 1, 6);
    const r = displayRect();
    view.x = m.x - g.anchor.x * r.w;  // keep the point between the fingers under the fingers
    view.y = m.y - g.anchor.y * r.h;
    clampView();
    updateZoomBadge();
    scheduleRender();
  }
  g.midLast = m;
}

function finishGesture(cancelled) {
  clearTimeout(g.longTimer);
  const quick = performance.now() - g.t0 < 400;
  if (g.kind === 'one') {
    if (g.dragging) { sendNow({ t: 'button', button: 'left', down: false }); return; }
    if (cancelled || g.moved) return;
    if (isDirect()) moveAbs(g.start);
    if (g.long) {
      sendNow({ t: 'click', button: 'right' });
    } else if (isDirect() || performance.now() - g.t0 < TAP_MS || g.afterTap) {
      sendNow({ t: 'click', button: 'left' });
      lastTap = { t: performance.now(), x: g.start.x, y: g.start.y };
      buzz(6);
    }
  } else if (!cancelled && !g.moved && quick) {
    if (g.fingers === 2) {
      if (isDirect()) moveAbs(g.mid0);
      sendNow({ t: 'click', button: 'right' });
      buzz(12);
    } else if (g.fingers === 3) {
      sendNow({ t: 'click', button: 'middle' });
    }
  }
}

/* =========================================================================
   Buttons: hold to repeat (arrows, backspace, volume…)
   ========================================================================= */
// A quick tap fires on release, so scrolling across a button doesn't press it. Holding 0.4 s repeats.
function holdButton(btn, action, repeat) {
  let timer = null;
  let held = false;
  const stop = () => {
    clearTimeout(timer);
    clearInterval(timer);
    timer = null;
    btn.classList.remove('pressed');
  };
  btn.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    e.preventDefault();  // keep focus in the text box so the phone keyboard stays open
    held = false;
    btn.classList.add('pressed');
    if (repeat) {
      timer = setTimeout(() => {
        held = true;
        action();
        buzz(6);
        timer = setInterval(action, 70);
      }, 400);
    }
  });
  btn.addEventListener('pointerup', stop);
  btn.addEventListener('pointercancel', stop);
  btn.addEventListener('pointerleave', stop);
  btn.addEventListener('click', () => {
    if (held) { held = false; return; }
    action();
    buzz(6);
  });
}

// Left/right buttons: holding keeps the button down (drag with another finger on the touchpad)
for (const btn of $$('[data-mouse]')) {
  const button = btn.dataset.mouse;
  const release = () => {
    if (!btn.classList.contains('pressed')) return;
    btn.classList.remove('pressed');
    sendNow({ t: 'button', button, down: false });
  };
  btn.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    btn.classList.add('pressed');
    sendNow({ t: 'button', button, down: true });
    buzz(8);
  });
  btn.addEventListener('pointerup', release);
  btn.addEventListener('pointercancel', release);
  btn.addEventListener('contextmenu', (e) => e.preventDefault());
}

/* =========================================================================
   Keyboard
   ========================================================================= */
const mods = new Set();

function clearMods() {
  mods.clear();
  $$('[data-mod]').forEach((b) => b.setAttribute('aria-pressed', 'false'));
}

function pressKeys(keys, { sticky = true } = {}) {
  const combo = sticky ? [...new Set([...mods, ...keys])] : keys;
  if (sticky && mods.size) clearMods();
  sendNow({ t: 'keys', keys: combo });
}

$$('[data-mod]').forEach((b) => {
  b.addEventListener('pointerdown', (e) => e.preventDefault());
  b.addEventListener('click', () => {
    const key = b.dataset.mod;
    if (mods.has(key)) mods.delete(key); else mods.add(key);
    b.setAttribute('aria-pressed', String(mods.has(key)));
  });
});
$$('[data-key]').forEach((b) => holdButton(b, () => pressKeys(b.dataset.key.split('+')), b.hasAttribute('data-repeat')));
$$('[data-combo]').forEach((b) => holdButton(b, () => pressKeys(b.dataset.combo.split('+'), { sticky: false }),
  b.hasAttribute('data-repeat')));

/* Text box. Live typing diffs the content before and after each input event and sends only the
   difference (characters removed, text added), so phone IMEs, suggestions and autocorrect all work. */
const typeInput = $('#type-input');
const SENTINEL = '​';  // invisible character, so the phone's backspace always has something to delete
let mirror = [];

function resetTyping() {
  typeInput.value = settings.live ? SENTINEL : '';
  mirror = Array.from(typeInput.value);
  autoGrow();
}

function autoGrow() {
  typeInput.style.height = 'auto';
  typeInput.style.height = `${Math.min(typeInput.scrollHeight + 2, 120)}px`;
}

function updateTypeUi() {
  $('#live').checked = settings.live;
  $('#type-send').textContent = T(settings.live ? 'keys.enter' : 'keys.send');
  $('#type-help').textContent = T(settings.live ? 'keys.live_help' : 'keys.compose_help');
  typeInput.placeholder = settings.live ? '' : T('keys.compose_placeholder');
}

typeInput.addEventListener('input', () => {
  autoGrow();
  if (!settings.live) return;
  const next = Array.from(typeInput.value);
  let i = 0;
  while (i < mirror.length && i < next.length && mirror[i] === next[i]) i++;
  const removed = mirror.length - i;
  const added = next.slice(i).join('').replaceAll(SENTINEL, '');
  if (mods.size && removed === 0 && Array.from(added).length === 1 && added !== '\n') {
    pressKeys([added.toLowerCase()]);  // e.g. Ctrl toggled, then "c" typed = Ctrl+C
    typeInput.value = mirror.join('');
    return;
  }
  if (removed) sendNow({ t: 'keys', keys: ['backspace'], repeat: removed });
  if (added) sendNow({ t: 'text', text: added });
  mirror = next;
  if (!next.length || added.endsWith('\n')) resetTyping();
});

// Hardware keyboards (Bluetooth) on phones and tablets: forward navigation keys and shortcuts
const KEYMAP = {
  ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right', Escape: 'esc', Tab: 'tab',
  Delete: 'delete', Home: 'home', End: 'end', PageUp: 'pageup', PageDown: 'pagedown',
};
typeInput.addEventListener('keydown', (e) => {
  if (!settings.live || e.isComposing) return;
  const combo = [];
  if (e.ctrlKey) combo.push('ctrl');
  if (e.altKey) combo.push('alt');
  if (e.metaKey) combo.push('win');
  const name = KEYMAP[e.key] || (combo.length && e.key.length === 1 ? e.key.toLowerCase() : null);
  if (!name) return;
  e.preventDefault();
  if (e.shiftKey) combo.push('shift');
  pressKeys([...combo, name]);
});

typeInput.addEventListener('focus', () => {
  if (settings.live) requestAnimationFrame(() => typeInput.setSelectionRange(typeInput.value.length, typeInput.value.length));
});

$('#type-send').addEventListener('pointerdown', (e) => e.preventDefault());
$('#type-send').addEventListener('click', () => {
  if (settings.live) { pressKeys(['enter']); return; }
  const text = typeInput.value;
  if (!text) return;
  sendNow({ t: 'text', text });
  resetTyping();
});

$('#live').addEventListener('change', (e) => {
  setSetting('live', e.target.checked);
  updateTypeUi();
  resetTyping();
});

/* =========================================================================
   System: brightness, clipboard, links, power
   ========================================================================= */
const bright = $('#bright');
let brightnessLoaded = false;

function setBrightness(value) {
  const unsupported = value === null || value === undefined;
  bright.hidden = unsupported;
  $('#bright-note').hidden = !unsupported;
  $('#bright-val').textContent = unsupported ? '' : `${value}%`;
  if (!unsupported) bright.value = value;
}
bright.addEventListener('input', () => { $('#bright-val').textContent = `${bright.value}%`; });
bright.addEventListener('change', () => send({ t: 'brightness', value: Number(bright.value) }));

$('#clip-get').addEventListener('click', () => send({ t: 'clipboard_get' }));
$('#clip-set').addEventListener('click', () => {
  const text = $('#clip-text').value;
  if (!text) { toast(T('clipboard.empty_input'), true); return; }
  send({ t: 'clipboard_set', text });
});

async function receiveClipboard(text) {
  const box = $('#clip-text');
  box.value = text;
  if (!text) { toast(T('clipboard.pc_empty')); return; }
  let copied = false;
  try { await navigator.clipboard.writeText(text); copied = true; } catch { /* needs HTTPS: try the legacy way */ }
  if (!copied) {
    // A hidden read-only box, so the phone keyboard doesn't pop up
    const tmp = document.createElement('textarea');
    tmp.value = text;
    tmp.setAttribute('readonly', '');
    tmp.style.cssText = 'position:fixed;top:0;left:0;opacity:0;pointer-events:none';
    document.body.append(tmp);
    tmp.select();
    tmp.setSelectionRange(0, text.length);
    try { copied = document.execCommand('copy'); } catch { copied = false; }
    tmp.remove();
  }
  toast(T(copied ? 'clipboard.copied' : 'clipboard.received'));
}

$('#url-form').addEventListener('submit', (e) => {
  e.preventDefault();
  let url = $('#url-input').value.trim();
  if (!url) return;
  if (!/^https?:\/\//i.test(url)) url = 'https://' + url;
  send({ t: 'open_url', url });
});

// Actions that need confirmation, and whether the confirm button is destructive
const POWER_CONFIRM = { lock: false, sleep: false, hibernate: false, restart: true, shutdown: true };

$$('[data-power]').forEach((b) => b.addEventListener('click', async () => {
  const action = b.dataset.power;
  if (action in POWER_CONFIRM) {
    const ok = await confirmDialog(T(`confirm.${action}.title`), T(`confirm.${action}.text`),
      T(`power.${action}_btn`), POWER_CONFIRM[action]);
    if (!ok) return;
  }
  send({ t: 'power', action });
}));

/* =========================================================================
   Windows on the PC (like Alt+Tab): quick-switch strip + switcher with thumbnails
   ========================================================================= */
const win = { list: null, icons: {}, thumbs: {}, multi: false };
const stripEl = $('#win-strip');
const gridEl = $('#win-grid');
const switcherEl = $('#switcher');
const chipCache = new Map();
const cardCache = new Map();
let thumbsAsked = new Set();
let switcherReturnFocus = null;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// "server.py - dancermd - Visual Studio Code" -> "server.py - dancermd": drop the trailing app name
function shortTitle(w) {
  const parts = w.title.split(/\s+[-—|]\s+/);
  if (parts.length > 1) {
    const last = parts[parts.length - 1].toLowerCase();
    if (w.app.toLowerCase().split(/\s+/).some((word) => word.length > 2 && last.includes(word))) parts.pop();
  }
  return parts.join(' - ') || w.title;
}

function windowLabel(w) {
  return `${shortTitle(w)} — ${w.app}${w.fg ? T('windows.in_use') : ''}${w.min ? T('windows.minimized') : ''}`;
}

function windowIcon(w, className) {
  const src = w.icon && win.icons[w.icon];
  if (src) {
    const img = el('img', className);
    img.src = src;
    img.alt = '';
    return img;
  }
  const avatar = el('span', `${className} win-avatar`, (w.app || w.title || '?').trim().charAt(0).toUpperCase());
  avatar.setAttribute('aria-hidden', 'true');
  return avatar;
}

/* Update in place by id: the list refreshes about every second, and replacing the buttons
   would make a tap land on a different window. */
function keyedRender(container, items, cache, create, update, fixed = []) {
  const nodes = items.map((item) => {
    let node = cache.get(item.id);
    if (!node) {
      node = create();
      cache.set(item.id, node);
    }
    update(node, item);
    return node;
  });
  const keep = new Set(items.map((item) => item.id));
  for (const [id, node] of cache) {
    if (!keep.has(id)) { node.remove(); cache.delete(id); }
  }
  const current = [...container.children].slice(fixed.length);
  if (current.length !== nodes.length || current.some((node, i) => node !== nodes[i])) {
    container.replaceChildren(...fixed, ...nodes);
  }
}

function createChip() {
  const chip = el('button', 'win-chip');
  chip.type = 'button';
  chip.addEventListener('click', () => activateWindow(chip.w, chip));
  return chip;
}

function updateChip(chip, w) {
  chip.w = w;
  const key = [I18N.language, w.title, w.app, w.icon, w.min, w.fg].join('|') + (win.icons[w.icon] ? '+' : '');
  if (chip.key === key) return;
  chip.key = key;
  chip.className = `win-chip${w.min ? ' min' : ''}`;
  if (w.fg) chip.setAttribute('aria-current', 'true'); else chip.removeAttribute('aria-current');
  chip.setAttribute('aria-label', windowLabel(w));
  chip.replaceChildren(windowIcon(w, 'ic'), el('span', 't', shortTitle(w)));
}

function renderStrip() {
  const allButton = $('#win-all');
  if (!win.list) {  // nothing received yet: placeholders
    chipCache.clear();
    stripEl.replaceChildren(allButton, ...[1, 2, 3].map(() => el('span', 'win-chip placeholder')));
    return;
  }
  keyedRender(stripEl, win.list, chipCache, createChip, updateChip, [allButton]);
}

function createCard() {
  const card = el('div', 'win-card');
  card.setAttribute('role', 'listitem');
  const main = el('button', 'win-card-main');
  main.type = 'button';
  main.addEventListener('click', () => activateWindow(card.w, card));
  const close = el('button', 'win-close');
  close.type = 'button';
  close.innerHTML = '<svg class="i" aria-hidden="true"><use href="#i-x"/></svg>';
  close.addEventListener('click', () => closeWindow(card.w, card));
  card.append(main, close);
  return card;
}

function updateCard(card, w) {
  card.w = w;
  const shot = win.thumbs[w.id];
  const key = [I18N.language, w.title, w.app, w.icon, w.min, w.fg, w.mon, win.multi, shot ? shot.length : 0].join('|');
  if (card.key === key) return;
  card.key = key;
  card.classList.remove('pending');
  if (w.fg) card.setAttribute('aria-current', 'true'); else card.removeAttribute('aria-current');
  const [main, close] = card.children;
  main.setAttribute('aria-label', T('windows.switch_to', { label: windowLabel(w) }));
  close.setAttribute('aria-label', T('windows.close', { title: shortTitle(w) }));

  const thumb = el('span', 'win-thumb');
  if (shot) {
    const img = el('img', 'shot');
    img.src = shot;
    img.alt = '';
    thumb.append(img);
  } else {
    thumb.append(windowIcon(w, 'big'));
  }
  const tags = el('span', 'win-badges');
  if (w.fg) tags.append(el('span', 'tag accent', T('tag.in_use')));
  if (w.min) tags.append(el('span', 'tag', T('tag.minimized')));
  if (win.multi && w.mon) tags.append(el('span', 'tag', T('tag.display', { n: w.mon })));
  thumb.append(tags);

  const app = el('span', 'win-app');
  app.append(windowIcon(w, 'ic'), el('span', '', w.app));
  const info = el('span', 'win-info');
  info.append(app, el('span', 'win-title', shortTitle(w)));
  main.replaceChildren(thumb, info);
}

function skeletonCard() {
  const card = el('div', 'win-card skeleton');
  card.setAttribute('aria-hidden', 'true');
  const info = el('span', 'win-info');
  info.append(el('span', 'win-title'));
  card.append(el('span', 'win-thumb'), info);
  return card;
}

function renderGrid() {
  $('#win-count').textContent = win.list ? win.list.length : '';
  $('#win-empty').hidden = !win.list || win.list.length > 0;
  if (!win.list) {
    cardCache.clear();
    gridEl.replaceChildren(...[1, 2, 3, 4].map(skeletonCard));
    return;
  }
  keyedRender(gridEl, win.list, cardCache, createCard, updateCard);
}

function requestThumbs() {
  if (!win.list) return;
  const ids = win.list.filter((w) => !w.min && !thumbsAsked.has(w.id)).map((w) => w.id);
  ids.forEach((id) => thumbsAsked.add(id));
  if (ids.length) send({ t: 'thumbs', ids });
}

function openSwitcher() {
  if (!authed) { toast(T('not_connected'), true); return; }
  if (!switcherEl.hidden) return;
  switcherReturnFocus = document.activeElement;
  switcherEl.hidden = false;
  $('#tab-windows').setAttribute('aria-expanded', 'true');
  thumbsAsked = new Set();  // fresh thumbnails every time the switcher opens
  renderGrid();
  send({ t: 'windows', on: true });
  requestThumbs();
  requestAnimationFrame(() => {
    const first = gridEl.querySelector('.win-card-main') || switcherEl.querySelector('[data-close]');
    first.focus({ preventScroll: true });
  });
}

function closeSwitcher() {
  if (switcherEl.hidden) return;
  switcherEl.hidden = true;
  $('#tab-windows').setAttribute('aria-expanded', 'false');
  switcherReturnFocus?.focus?.({ preventScroll: true });
}

function activateWindow(w, node) {
  if (!w) return;
  node?.classList.add('pending');
  sendNow({ t: 'activate', id: w.id });
  buzz(10);
  closeSwitcher();
}

function closeWindow(w, card) {
  if (!w) return;
  card.classList.add('pending');
  sendNow({ t: 'close_window', id: w.id });
  buzz(10);
}

function switchToPrevious() {
  if (!authed) return;
  sendNow({ t: 'switch_prev' });
  buzz(10);
}

$('#win-all').addEventListener('click', openSwitcher);
$('#tab-windows').addEventListener('click', openSwitcher);
$('#btn-windows-float').addEventListener('click', openSwitcher);
$('#rail-prev').addEventListener('click', switchToPrevious);
$('#win-desktop').addEventListener('click', () => {
  pressKeys(['win', 'd'], { sticky: false });
  closeSwitcher();
});
switcherEl.addEventListener('click', (e) => {
  if (e.target === switcherEl || e.target.closest('[data-close]')) closeSwitcher();
});
switcherEl.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    e.preventDefault();
    closeSwitcher();
  } else if (e.key === 'Tab') {  // keep focus inside the dialog
    const items = $$('button', switcherEl).filter((b) => b.offsetParent !== null);
    const i = items.indexOf(document.activeElement);
    const next = e.shiftKey ? (i <= 0 ? items.length - 1 : i - 1) : (i === items.length - 1 ? 0 : i + 1);
    e.preventDefault();
    items[next]?.focus();
  }
});
renderStrip();

/* Banner shown while an elevated window blocks input */
let uipi = null;
function renderUipi() {
  $('#uipi').hidden = !uipi;
  if (!uipi) return;
  I18N.fill($('#uipi-text'), 'uipi.blocked', { title: Object.assign(document.createElement('b'), { textContent: `“${uipi.title}”` }) });
  $('#uipi-hint').textContent = T(uipi.hint);
}

/* =========================================================================
   Shell: tabs, settings, dialogs, toasts, full screen
   ========================================================================= */
/* Portrait: one panel is always open below the screen. Landscape: panels are drawers over the screen,
   closed by default so the PC screen gets the full width; tapping the active tab closes it. */
const landscapeMq = window.matchMedia('(orientation: landscape) and (max-height: 560px)');
const dockEl = $('#dock');
const TAB_TITLES = { mouse: 'tab.mouse', keys: 'tab.keys', system: 'tab.system' };
let activeTab = 'mouse';

function showTab(name) {
  if (landscapeMq.matches && name === activeTab && !dockEl.classList.contains('closed')) name = null;
  if (!name && !landscapeMq.matches) name = activeTab;
  if (name) activeTab = name;
  dockEl.classList.toggle('closed', !name);
  $$('.tabbar [data-tab]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.tab === name)));
  $$('.panel').forEach((p) => { p.hidden = p.dataset.panel !== activeTab; });
  $('#dock-title').textContent = T(TAB_TITLES[activeTab]);
  if (name === 'system' && !brightnessLoaded && authed) {
    brightnessLoaded = true;
    send({ t: 'brightness' });
  }
  requestAnimationFrame(() => { clampView(); scheduleRender(); });
}
$$('.tabbar [data-tab]').forEach((b) => b.addEventListener('click', () => showTab(b.dataset.tab)));
$('#dock-close').addEventListener('click', () => showTab(null));
landscapeMq.addEventListener('change', () => showTab(landscapeMq.matches ? null : activeTab));
if (landscapeMq.matches) showTab(null);
else $('#dock-title').textContent = T(TAB_TITLES[activeTab]);

function setupSeg(container, value, onChange) {
  const buttons = $$('button', container);
  const sync = (v) => buttons.forEach((b) => b.setAttribute('aria-checked', String(b.dataset.value === v)));
  buttons.forEach((b) => {
    b.setAttribute('role', 'radio');
    b.addEventListener('click', () => { sync(b.dataset.value); onChange(b.dataset.value); });
  });
  sync(value);
}

setupSeg($('#mode-seg'), settings.mode, (v) => {
  setSetting('mode', v);
  if (v === 'direct' && !showingScreen()) toast(T('mode.direct_needs_stream'), true);
  else toast(T(v === 'direct' ? 'mode.direct_on' : 'mode.touchpad_on'));
});

setupSeg($('#opt-quality'), settings.quality, (v) => {
  setSetting('quality', v);
  send({ t: 'stream', quality: v });
});

setupSeg($('#opt-codec'), settings.codec, (v) => {
  setSetting('codec', v);
  send({ t: 'stream', codec: wantedCodec() });
});

const optStream = $('#opt-stream');
optStream.checked = settings.stream;
optStream.addEventListener('change', () => {
  setSetting('stream', optStream.checked);
  if (!settings.stream) { view.img?.close(); view.img = null; }
  send({ t: 'stream', on: settings.stream && !document.hidden });
  updateHint();
  updateMonitorBadge();
  scheduleRender();
});

$('#opt-monitor').addEventListener('change', (e) => selectMonitor(Number(e.target.value)));

const optSpeed = $('#opt-speed');
optSpeed.value = settings.speed;
$('#speed-val').textContent = `${Number(settings.speed).toFixed(1)}×`;
optSpeed.addEventListener('input', () => {
  setSetting('speed', Number(optSpeed.value));
  $('#speed-val').textContent = `${Number(optSpeed.value).toFixed(1)}×`;
});

const optLang = $('#opt-lang');
optLang.value = settings.lang;
optLang.addEventListener('change', () => {
  setSetting('lang', optLang.value);
  applyLanguage();
});

function updateConnInfo() {
  const host = Object.assign(document.createElement('b'), { textContent: hostName || '—' });
  I18N.fill($('#conn-info'), 'settings.connected_to', { host, ping: pingMs === null ? '—' : `${pingMs} ms` });
}

const settingsEl = $('#settings');
function openSettings() { settingsEl.hidden = false; }
$('#btn-settings').addEventListener('click', openSettings);
$('#rail-settings').addEventListener('click', openSettings);
settingsEl.addEventListener('click', (e) => {
  if (e.target === settingsEl || e.target.closest('[data-close]')) settingsEl.hidden = true;
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !settingsEl.hidden) settingsEl.hidden = true;
});

$('#logout').addEventListener('click', () => {
  store.del('token');
  settingsEl.hidden = true;
  authed = false;
  ws?.close();
  showLogin();
});

function confirmDialog(title, text, okLabel, danger) {
  const box = $('#confirm');
  const ok = $('#confirm-ok');
  $('#confirm-title').textContent = title;
  $('#confirm-text').textContent = text;
  ok.textContent = okLabel;
  ok.classList.toggle('danger', danger);
  ok.classList.toggle('primary', !danger);
  box.hidden = false;
  ok.focus();
  return new Promise((resolve) => {
    const done = (answer) => {
      box.hidden = true;
      box.removeEventListener('click', onClick);
      document.removeEventListener('keydown', onKey);
      resolve(answer);
    };
    const onClick = (e) => {
      const btn = e.target.closest('[data-answer]');
      if (btn) done(btn.dataset.answer === 'yes');
      else if (e.target === box) done(false);
    };
    const onKey = (e) => { if (e.key === 'Escape') done(false); };
    box.addEventListener('click', onClick);
    document.addEventListener('keydown', onKey);
  });
}

let toastTimer = null;
function toast(msg, error = false) {
  const node = $('#toast');
  node.textContent = msg;
  node.classList.toggle('error', !!error);
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { node.hidden = true; }, error ? 4000 : 2200);
}

function setImmersive(on) {
  document.body.classList.toggle('immersive', on);
  try {
    if (on) document.documentElement.requestFullscreen?.({ navigationUI: 'hide' })?.catch?.(() => {});
    else if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  } catch { /* iPhone has no Fullscreen API: the toolbars are still hidden */ }
}
$('#btn-full').addEventListener('click', () => setImmersive(true));
$('#rail-full').addEventListener('click', () => setImmersive(true));
$('#btn-exit-full').addEventListener('click', () => setImmersive(false));
document.addEventListener('fullscreenchange', () => {
  if (!document.fullscreenElement) document.body.classList.remove('immersive');
});

// The on-screen keyboard covers the page on iOS/Android: fit the app to the visible viewport
if (window.visualViewport) {
  const fit = () => {
    appEl.style.height = `${visualViewport.height}px`;
    appEl.style.transform = `translateY(${visualViewport.offsetTop}px)`;
  };
  visualViewport.addEventListener('resize', fit);
  visualViewport.addEventListener('scroll', fit);
  fit();
}
document.addEventListener('gesturestart', (e) => e.preventDefault());  // stop Safari's page zoom

/* Re-render every text built in script after a language change (static markup is handled by I18N) */
function applyLanguage() {
  I18N.setLanguage(settings.lang);
  setStatus(connState);
  setBattery(battery);
  if (monitors.length) setMonitors(monitors, currentMonitor);
  updateZoomBadge();
  updateCodecInfo();
  updateConnInfo();
  updateTypeUi();
  renderUipi();
  $('#dock-title').textContent = T(TAB_TITLES[activeTab]);
  if (win.list) { renderStrip(); renderGrid(); }
}

/* =========================================================================
   Start-up
   ========================================================================= */
takeTokenFromUrl();
updateTypeUi();
updateConnInfo();
resetTyping();
updateHint();
connect();
detectH264().then((ok) => {
  h264Supported = ok;
  if (authed && ok && settings.codec === 'auto') send({ t: 'stream', codec: 'h264' });
});
