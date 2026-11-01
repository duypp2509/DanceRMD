'use strict';

/* DanceRMD dashboard: polls /api/state and drives the local-only settings API (dancermd/server/dashboard.py). */

const $ = (sel) => document.querySelector(sel);
const T = (key, params) => I18N.t(key, params);
const REFRESH_MS = 2000;
const PHONE_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
  + 'stroke-linejoin="round" aria-hidden="true"><rect x="6" y="2" width="12" height="20" rx="2.5"/><path d="M11 18h2"/></svg>';

let state = null;
let selectedIp = null;
let shownUrl = null;
let revealed = false;
let lastTunnelUrl = null;
let adminBusy = false;
let language = null;

class ApiError extends Error {
  constructor(payload) {
    super(I18N.message(payload));
    this.payload = payload;
  }
}

async function api(path, body) {
  const opts = body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  };
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(data.error || T('dash.http_error', { status: res.status }));
  return data;
}

async function refresh() {
  try {
    state = await api('/api/state');
    render();
    setStatus(true);
  } catch {
    setStatus(false);
  }
}

function setStatus(ok) {
  $('#status').classList.toggle('off', !ok);
  $('#status-text').textContent = ok ? T('dash.status.running', { port: state.port }) : T('dash.status.lost');
}

/* The dashboard follows the language chosen in the app (shared with the tray menu) */
function syncLanguage() {
  if (language === state.language) return;
  language = state.language;
  I18N.setLanguage(language);
  shownUrl = null;  // re-render the address hint
}

function render() {
  syncLanguage();
  const tunnel = state.tunnel;
  const links = state.links.map((l) => ({ ...l, label: T(`addr.${l.kind}`) }));
  if (tunnel.status === 'on' && tunnel.link) {
    const host = new URL(tunnel.url).host;
    links.unshift({ kind: 'remote', label: T('addr.remote'), ip: host, url: tunnel.link, qr: tunnel.qr });
    if (lastTunnelUrl !== tunnel.url) selectedIp = host;  // just turned on: show the remote QR code
  }
  lastTunnelUrl = tunnel.status === 'on' ? tunnel.url : null;
  renderTunnel(tunnel);
  renderInstall(state.installed);
  renderAdmin(state.admin);
  const current = links.find((l) => l.ip === selectedIp) || links[0];
  selectedIp = current.ip;

  const sel = $('#addr');
  const options = links.map((l) => `${l.label} — ${l.ip}`).join('|');
  if (sel.dataset.options !== options) {
    sel.dataset.options = options;
    sel.replaceChildren(...links.map((l) => new Option(`${l.label} — ${l.ip}`, l.ip)));
  }
  sel.value = selectedIp;

  if (shownUrl !== current.url) {  // redraw the QR code only when the link changes (no flicker)
    shownUrl = current.url;
    $('#qr').innerHTML = current.qr;
    $('#url').textContent = current.url;
    $('#addr-hint').textContent = T(`addr.hint.${current.kind}`);
  }

  $('#token').textContent = revealed ? state.token : '•'.repeat(state.token.length);
  $('#reveal').textContent = T(revealed ? 'dash.hide' : 'dash.show');
  $('#autostart').checked = state.autostart;
  $('#language').value = state.language_setting;
  $('#sub').textContent = T('dash.subtitle', { host: state.host });
  $('#footer').textContent = T('dash.footer', {
    version: state.version, capture: state.gpu.capture, encoder: state.gpu.encoder || T('dash.no_h264'),
    dir: state.data_dir,
  });
  renderDevices(state.devices);
}

function renderTunnel(tunnel) {
  $('#tunnel').checked = state.tunnel_enabled;
  const box = $('#tunnel-status');
  box.hidden = tunnel.status === 'off';
  box.className = `tunnel-status ${tunnel.status}`;
  $('#tunnel-text').textContent = {
    starting: I18N.message(tunnel.message) || T('tunnel.starting'),
    on: T('dash.tunnel.on', { url: tunnel.url }),
    error: I18N.message(tunnel.message) || T('dash.tunnel.error'),
  }[tunnel.status] || '';
}

function renderAdmin(admin) {
  $('#admin-row').hidden = !admin.available;
  if (!admin.available || adminBusy) return;
  $('#admin').checked = admin.enabled;
  const desc = $('#admin-desc');
  desc.classList.toggle('warn', admin.enabled && !admin.elevated);
  desc.textContent = T(admin.enabled && admin.elevated ? 'dash.admin_active'
    : admin.enabled ? 'dash.admin_pending' : 'dash.admin_desc');
}

function renderInstall(installed) {
  // null: running from source, nothing to install
  $('#install-row').hidden = installed === null;
  $('#install').hidden = installed !== false;
  $('#install-desc').textContent = T(installed ? 'dash.installed_desc' : 'dash.install_desc');
}

function ago(since) {
  const min = Math.floor((Date.now() / 1000 - since) / 60);
  if (min < 1) return T('dash.ago.now');
  if (min < 60) return T('dash.ago.minutes', { m: min });
  return T('dash.ago.hours', { h: Math.floor(min / 60), m: min % 60 });
}

function renderDevices(devices) {
  const count = $('#dev-count');
  count.textContent = devices.length;
  count.classList.toggle('live', devices.length > 0);
  $('#dev-empty').hidden = devices.length > 0;
  $('#devices').replaceChildren(...devices.map((d) => {
    const li = document.createElement('li');
    li.className = 'device';
    li.innerHTML = PHONE_ICON;
    const text = document.createElement('div');
    text.className = 'device-text';
    const name = document.createElement('b');
    name.textContent = `${T(`device.${d.device}`)} · ${d.ip}`;
    const when = document.createElement('span');
    when.className = 'muted small';
    when.textContent = ago(d.since);
    text.append(name, when);
    const kick = document.createElement('button');
    kick.type = 'button';
    kick.className = 'btn';
    kick.textContent = T('dash.disconnect');
    kick.title = T('dash.disconnect_title');
    kick.addEventListener('click', async () => {
      kick.disabled = true;
      await api('/api/kick', { id: d.id }).catch((e) => toast(e.message, true));
      setTimeout(refresh, 300);
    });
    li.append(text, kick);
    return li;
  }));
}

/* Toggle a switch through the API; the switch flips back if the request fails */
function bindSwitch(selector, path, onDone) {
  $(selector).addEventListener('change', async (e) => {
    const enabled = e.target.checked;
    try {
      state = await api(path, { enabled });
      render();
      onDone?.(enabled);
    } catch (err) {
      e.target.checked = !enabled;
      toast(err.message, true);
    }
  });
}

$('#addr').addEventListener('change', (e) => { selectedIp = e.target.value; render(); });

$('#copy-link').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(shownUrl);
    toast(T('dash.copied'));
  } catch {
    toast(T('dash.copy_failed'), true);
  }
});

$('#reveal').addEventListener('click', (e) => {
  revealed = !revealed;
  e.target.setAttribute('aria-pressed', String(revealed));
  if (state) render();
});

$('#rotate').addEventListener('click', async () => {
  if (!confirm(T('dash.rotate_confirm'))) return;
  try {
    state = await api('/api/token', {});
    render();
    toast(T('dash.rotated'));
  } catch (e) { toast(e.message, true); }
});

bindSwitch('#autostart', '/api/autostart', (enabled) => toast(T(enabled ? 'dash.autostart_on' : 'dash.autostart_off')));
bindSwitch('#tunnel', '/api/tunnel', (enabled) => { if (enabled) toast(T('dash.remote_starting')); });

$('#admin').addEventListener('change', async (e) => {
  const enabled = e.target.checked;
  adminBusy = true;
  e.target.disabled = true;
  if (enabled) toast(T('dash.admin_uac'));
  try {
    await api('/api/admin', { enabled });
    toast(T('dash.restarting'));
  } catch (err) {
    e.target.checked = !enabled;
    toast(err.message, true);
  } finally {
    adminBusy = false;
    e.target.disabled = false;
  }
});

$('#install').addEventListener('click', async (e) => {
  e.target.disabled = true;
  try {
    await api('/api/install', {});
    toast(T('dash.installed'));
  } catch (err) {
    toast(err.message, true);
    e.target.disabled = false;
  }
});

$('#firewall').addEventListener('click', async (e) => {
  const btn = e.target;
  btn.disabled = true;
  try {
    await api('/api/firewall', {});
    toast(T('dash.firewall_done'));
  } catch (err) {
    toast(err.message, true);
  } finally {
    btn.disabled = false;
  }
});

$('#language').addEventListener('change', async (e) => {
  try {
    state = await api('/api/language', { language: e.target.value });
    render();
  } catch (err) {
    toast(err.message, true);
  }
});

let toastTimer = null;
function toast(msg, error = false) {
  const node = $('#toast');
  node.textContent = msg;
  node.classList.toggle('error', error);
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { node.hidden = true; }, error ? 4500 : 3000);
}

I18N.setLanguage('auto');
refresh();
setInterval(refresh, REFRESH_MS);
