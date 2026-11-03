'use strict';

/* DanceRMD dashboard: polls /api/state and drives the local-only settings API (dancermd/server/dashboard.py).
   Two pages, switched by the URL hash: #connect (QR code, phones, remote access) and #settings. */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];
const T = (key, params) => I18N.t(key, params);
const REFRESH_MS = 2000;
const PAGES = ['connect', 'settings'];
const THEME_KEY = 'dancermd.theme';
const systemDark = window.matchMedia('(prefers-color-scheme: dark)');

let state = null;
let mode = 'lan';           // QR code on screen: 'lan' (same Wi-Fi) or 'remote' (Internet tunnel)
let selectedIp = null;      // chosen network adapter in 'lan' mode
let shownQr = null;         // link drawn as the QR code, so it is redrawn only when it changes
let copyUrl = null;         // link copied by "Copy connection link"
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
    setStatus('ready');
  } catch {
    setStatus('lost');
  }
}

function setStatus(value) {
  const node = $('#status');
  node.dataset.state = value;
  const text = T(`dash.status.${value}`);
  $('#status-text').textContent = text;
  node.title = text;  // the text is visually hidden in the narrow sidebar
}

/* ---------- Theme ---------- */

function applyTheme(setting) {
  const dark = setting === 'system' ? systemDark.matches : setting !== 'light';
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  try { localStorage.setItem(THEME_KEY, setting); } catch { /* storage blocked: the server keeps the setting */ }
}

systemDark.addEventListener('change', () => {
  if (state?.theme === 'system') applyTheme('system');
});

/* ---------- Pages ---------- */

function currentPage() {
  const page = location.hash.slice(1);
  return PAGES.includes(page) ? page : 'connect';
}

function showPage({ focus = false } = {}) {
  const page = currentPage();
  for (const name of PAGES) $(`#page-${name}`).hidden = name !== page;
  $$('.nav-item').forEach((link) => {
    if (link.dataset.page === page) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  window.scrollTo(0, 0);
  if (focus) $(`#page-${page} h1`).focus();
}

window.addEventListener('hashchange', () => showPage({ focus: true }));

/* ---------- Rendering ---------- */

/* The dashboard follows the language chosen in the app (shared with the tray menu) */
function syncLanguage() {
  if (language === state.language) return;
  language = state.language;
  I18N.setLanguage(language);
  shownQr = null;
}

function render() {
  syncLanguage();
  applyTheme(state.theme);
  const tunnel = state.tunnel;
  const tunnelUrl = tunnel.status === 'on' && tunnel.link ? tunnel.url : null;
  if (tunnelUrl && tunnelUrl !== lastTunnelUrl) mode = 'remote';  // just turned on: show the remote QR code
  lastTunnelUrl = tunnelUrl;

  $('#connect-sub').textContent = T('dash.connect.sub', { host: state.host });
  $('#version').textContent = T('dash.version', { version: state.version });
  renderScan(tunnel);
  renderTunnel(tunnel);
  renderDevices(state.devices);
  renderSettings();
}

function renderScan(tunnel) {
  $$('#scan-tabs [role="tab"]').forEach((tab) => {
    const selected = tab.dataset.mode === mode;
    tab.setAttribute('aria-selected', String(selected));
    tab.tabIndex = selected ? 0 : -1;
  });
  $('#scan-panel').setAttribute('aria-labelledby', `tab-${mode}`);

  let link = null;
  if (mode === 'lan') {
    const current = state.links.find((l) => l.ip === selectedIp) || state.links[0];
    selectedIp = current.ip;
    renderAdapters(state.links);
    link = { url: current.url, qr: current.qr, address: `${current.ip}:${state.port}`, hint: T(`addr.hint.${current.kind}`) };
  } else if (tunnel.status === 'on' && tunnel.link) {
    link = { url: tunnel.link, qr: tunnel.qr, address: new URL(tunnel.url).host, hint: T('addr.hint.remote') };
  }

  $('#adapter-field').hidden = mode !== 'lan' || state.links.length < 2;
  $('#qr').hidden = !link;
  $('#qr-off').hidden = Boolean(link);
  $('#link-info').hidden = !link;
  $('#copy-link').hidden = !link;
  copyUrl = link ? link.url : null;
  if (!link) {
    shownQr = null;
    renderRemoteOff(tunnel);
    return;
  }
  if (shownQr !== link.url) {
    shownQr = link.url;
    $('#qr').innerHTML = link.qr;  // SVG generated by the server
  }
  $('#link-address').textContent = link.address;
  $('#link-hint').textContent = link.hint;
}

function renderAdapters(links) {
  const select = $('#adapter');
  const options = links.map((l) => `${T(`addr.${l.kind}`)} · ${l.ip}`);
  if (select.dataset.options !== options.join('|')) {
    select.dataset.options = options.join('|');
    select.replaceChildren(...links.map((l, i) => new Option(options[i], l.ip)));
  }
  select.value = selectedIp;
}

/* "Over the Internet" without a link yet: remote access is off, starting or failed */
function renderRemoteOff(tunnel) {
  const error = tunnel.status === 'error';
  const starting = !error && state.tunnel_enabled;
  const view = error ? 'error' : starting ? 'starting' : 'off';
  $('#qr-off').dataset.state = view;
  $('#qr-off-title').textContent = T({ off: 'dash.remote_off.title', starting: 'dash.remote_wait.title',
    error: 'dash.remote_error.title' }[view]);
  $('#qr-off-text').textContent = {
    off: T('dash.remote_off.text'),
    starting: I18N.message(tunnel.message) || T('tunnel.starting'),
    error: I18N.message(tunnel.message) || T('dash.tunnel.error'),
  }[view];
  const action = $('#qr-off-action');
  action.hidden = view === 'starting';
  action.querySelector('span').textContent = T(error ? 'dash.retry' : 'dash.remote_off.action');
}

function renderTunnel(tunnel) {
  const toggle = $('#tunnel');
  if (!toggle.disabled) toggle.checked = state.tunnel_enabled;
  const box = $('#tunnel-status');
  const view = tunnel.status === 'off' && state.tunnel_enabled ? 'starting' : tunnel.status;
  box.hidden = view === 'off';
  box.dataset.state = view;
  $('#tunnel-text').textContent = {
    starting: I18N.message(tunnel.message) || T('tunnel.starting'),
    on: tunnel.url ? T('dash.tunnel.on', { host: new URL(tunnel.url).host }) : '',
    error: I18N.message(tunnel.message) || T('dash.tunnel.error'),
  }[view] || '';
}

function ago(since) {
  const min = Math.floor((Date.now() / 1000 - since) / 60);
  if (min < 1) return T('dash.ago.now');
  if (min < 60) return T('dash.ago.minutes', { m: min });
  return T('dash.ago.hours', { h: Math.floor(min / 60), m: min % 60 });
}

function icon(name) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'i');
  svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', `#i-${name}`);
  svg.append(use);
  return svg;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderDevices(devices) {
  const count = $('#dev-count');
  count.textContent = devices.length;
  count.classList.toggle('live', devices.length > 0);
  const badge = $('#nav-count');
  badge.hidden = devices.length === 0;
  badge.textContent = devices.length;
  badge.title = T('dash.devices_count', { count: devices.length });
  $('#dev-empty').hidden = devices.length > 0;
  $('#devices').replaceChildren(...devices.map((d) => {
    const item = el('li', 'device');
    const iconBox = el('span', 'device-icon');
    iconBox.append(icon('phone'));
    const text = el('div', 'device-text');
    const meta = el('p', 'device-meta');
    meta.append(el('span', '', `${d.ip} · ${ago(d.since)}`), el('span', 'device-live', T('dash.device_live')));
    text.append(el('p', 'device-name', T(`device.${d.device}`)), meta);
    const kick = el('button', 'btn');
    kick.type = 'button';
    kick.title = T('dash.disconnect_title');
    kick.append(icon('unplug'), el('span', '', T('dash.disconnect')));
    kick.addEventListener('click', async () => {
      setBusy(kick, true);
      try {
        await api('/api/kick', { id: d.id });
      } catch (e) {
        toast(e.message, true);
        setBusy(kick, false);
      }
      setTimeout(refresh, 300);
    });
    item.append(iconBox, text, kick);
    return item;
  }));
}

function renderSettings() {
  $('#autostart').checked = state.autostart;
  $('#language').value = state.language_setting;
  $$('#theme [role="radio"]').forEach((option) => {
    const checked = option.dataset.value === state.theme;
    option.setAttribute('aria-checked', String(checked));
    option.tabIndex = checked ? 0 : -1;
  });
  renderInstall(state.installed);
  renderAdmin(state.admin);

  $('#token').textContent = revealed ? state.token : '•'.repeat(state.token.length);
  const reveal = $('#reveal');
  reveal.setAttribute('aria-pressed', String(revealed));
  reveal.querySelector('use').setAttribute('href', revealed ? '#i-eye-off' : '#i-eye');
  reveal.querySelector('span').textContent = T(revealed ? 'dash.hide' : 'dash.show');

  $('#firewall-desc').textContent = T('dash.firewall_desc', { port: state.port });
  $('#help-firewall-text').textContent = T('dash.help.firewall_text', { port: state.port });
  $('#spec-version').textContent = state.version;
  $('#spec-port').textContent = state.port;
  $('#spec-capture').textContent = state.gpu.capture;
  $('#spec-encoder').textContent = state.gpu.encoder || T('dash.no_h264');
  $('#spec-data').textContent = state.data_dir;
}

function renderInstall(installed) {
  // null: running from source, nothing to install
  $('#install-row').hidden = installed === null;
  $('#install').hidden = installed !== false;
  $('#installed-badge').hidden = installed !== true;
  $('#install-desc').textContent = T(installed ? 'dash.installed_desc' : 'dash.install_desc');
}

function renderAdmin(admin) {
  $('#group-admin').hidden = !admin.available;
  if (!admin.available || adminBusy) return;
  $('#admin').checked = admin.enabled;
  const note = $('#admin-note');
  const [tone, key] = admin.enabled && admin.elevated ? ['ok', 'dash.admin_active']
    : admin.enabled ? ['warn', 'dash.admin_pending'] : ['warn', 'dash.admin_note'];
  note.dataset.tone = tone;
  note.querySelector('use').setAttribute('href', tone === 'ok' ? '#i-check-circle' : '#i-alert');
  $('#admin-note-text').textContent = T(key);
}

/* ---------- Actions ---------- */

function setBusy(button, busy) {
  button.disabled = busy;
  button.setAttribute('aria-busy', String(busy));
}

/* Toggle a switch through the API; the switch flips back if the request fails */
function bindSwitch(selector, path, onDone) {
  $(selector).addEventListener('change', async (e) => {
    const input = e.target;
    const enabled = input.checked;
    input.disabled = true;
    try {
      state = await api(path, { enabled });
      onDone?.(enabled);
      render();
    } catch (err) {
      input.checked = !enabled;
      toast(err.message, true);
    } finally {
      input.disabled = false;
    }
  });
}

async function startRemoteAccess(button) {
  if (button) setBusy(button, true);
  try {
    state = await api('/api/tunnel', { enabled: true });
    mode = 'remote';
    render();
    toast(T('dash.remote_starting'));
  } catch (err) {
    toast(err.message, true);
  } finally {
    if (button) setBusy(button, false);
  }
}

/* Arrow keys move between the options of a tab list or radio group (roving tabindex) */
function arrowKeys(container, selector, choose) {
  container.addEventListener('keydown', (e) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!step) return;
    const items = $$(selector);
    const next = items[(items.indexOf(document.activeElement) + step + items.length) % items.length];
    e.preventDefault();
    next.focus();
    choose(next);
  });
}

function chooseMode(tab) {
  mode = tab.dataset.mode;
  if (state) render();
}
$$('#scan-tabs [role="tab"]').forEach((tab) => tab.addEventListener('click', () => chooseMode(tab)));
arrowKeys($('#scan-tabs'), '#scan-tabs [role="tab"]', chooseMode);

$('#adapter').addEventListener('change', (e) => { selectedIp = e.target.value; render(); });

$('#copy-link').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(copyUrl);
    toast(T('dash.copied'));
  } catch {
    toast(T('dash.copy_failed'), true);
  }
});

$('#qr-off-action').addEventListener('click', (e) => startRemoteAccess(e.currentTarget));
$('#help-remote').addEventListener('click', async (e) => {
  await startRemoteAccess(e.currentTarget);
  $('#scan').scrollIntoView({ behavior: 'smooth', block: 'start' });
  $('#tab-remote').focus();
});

bindSwitch('#tunnel', '/api/tunnel', (enabled) => {
  if (!enabled) return;
  mode = 'remote';
  toast(T('dash.remote_starting'));
});
bindSwitch('#autostart', '/api/autostart', (enabled) => toast(T(enabled ? 'dash.autostart_on' : 'dash.autostart_off')));

$('#admin').addEventListener('change', async (e) => {
  const input = e.target;
  const enabled = input.checked;
  adminBusy = true;
  input.disabled = true;
  if (enabled) toast(T('dash.admin_uac'));
  try {
    await api('/api/admin', { enabled });
    toast(T('dash.restarting'));
  } catch (err) {
    input.checked = !enabled;
    toast(err.message, true);
  } finally {
    adminBusy = false;
    input.disabled = false;
  }
});

$('#install').addEventListener('click', async (e) => {
  const button = e.currentTarget;
  setBusy(button, true);
  try {
    await api('/api/install', {});
    toast(T('dash.installed'));
  } catch (err) {
    toast(err.message, true);
    setBusy(button, false);
  }
});

$$('[data-action="firewall"]').forEach((button) => button.addEventListener('click', async () => {
  setBusy(button, true);
  try {
    await api('/api/firewall', {});
    toast(T('dash.firewall_done'));
  } catch (err) {
    toast(err.message, true);
  } finally {
    setBusy(button, false);
  }
}));

$('#language').addEventListener('change', async (e) => {
  try {
    state = await api('/api/language', { language: e.target.value });
    render();
  } catch (err) {
    e.target.value = state.language_setting;
    toast(err.message, true);
  }
});

async function chooseTheme(option) {
  const theme = option.dataset.value;
  if (!state || theme === state.theme) return;
  const previous = state.theme;
  state.theme = theme;
  render();  // apply right away; the server stores it
  try {
    state = await api('/api/theme', { theme });
    render();
  } catch (err) {
    state.theme = previous;
    render();
    toast(err.message, true);
  }
}
$$('#theme [role="radio"]').forEach((option) => option.addEventListener('click', () => chooseTheme(option)));
arrowKeys($('#theme'), '#theme [role="radio"]', chooseTheme);

$('#reveal').addEventListener('click', () => {
  revealed = !revealed;
  if (state) render();
});

$('#rotate').addEventListener('click', async (e) => {
  const button = e.currentTarget;  // read it before awaiting: it is null once the event is over
  const ok = await confirmDialog({
    title: T('dash.rotate_confirm.title'), text: T('dash.rotate_confirm.text'), action: T('dash.rotate'),
  });
  if (!ok) return;
  setBusy(button, true);
  try {
    state = await api('/api/token', {});
    render();
    toast(T('dash.rotated'));
  } catch (err) {
    toast(err.message, true);
  } finally {
    setBusy(button, false);
  }
});

/* ---------- Dialog and toast ---------- */

function confirmDialog({ title, text, action }) {
  const dialog = $('#confirm');
  $('#confirm-title').textContent = title;
  $('#confirm-text').textContent = text;
  $('#confirm-ok').textContent = action;
  dialog.returnValue = '';
  dialog.showModal();
  return new Promise((resolve) => {
    dialog.addEventListener('close', () => resolve(dialog.returnValue === 'ok'), { once: true });
  });
}

let toastTimer = null;
function toast(message, error = false) {
  const node = $('#toast');
  $('#toast-text').textContent = message;
  node.classList.toggle('error', error);
  node.querySelector('use').setAttribute('href', error ? '#i-alert' : '#i-check-circle');
  node.setAttribute('role', error ? 'alert' : 'status');
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { node.hidden = true; }, error ? 6000 : 3500);
}

I18N.setLanguage('en');
showPage();
refresh();
setInterval(refresh, REFRESH_MS);
