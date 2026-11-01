/* DanceRMD i18n: dictionary-based translations shared by the phone client and the dashboard.

   Markup  data-i18n="key"                       textContent
           data-i18n-html="key"                  innerHTML (only for trusted dictionary strings)
           data-i18n-attr="aria-label:key; title:key2"
   Script  I18N.t('key', { name: 'value' })      plain text
           I18N.fill(el, 'key', { name: node })  sentence whose placeholders are DOM nodes
           I18N.message(payload)                 server {code, params, message} payload

   Dictionaries are registered by locales/<lang>.js through I18N.define(). */
'use strict';

(() => {
  const dictionaries = {};
  let current = 'en';

  function define(lang, strings) {
    dictionaries[lang] = { ...dictionaries[lang], ...strings };
  }

  /* 'auto' follows the browser languages; otherwise use the requested language if it exists. */
  function detect(setting) {
    if (setting && setting !== 'auto' && dictionaries[setting]) return setting;
    for (const tag of navigator.languages?.length ? navigator.languages : [navigator.language || 'en']) {
      const base = String(tag).toLowerCase().split('-')[0];
      if (dictionaries[base]) return base;
    }
    return 'en';
  }

  function lookup(key) {
    return dictionaries[current]?.[key] ?? dictionaries.en?.[key];
  }

  function t(key, params) {
    const template = lookup(key);
    if (template === undefined) return key;
    if (!params) return template;
    return template.replace(/\{(\w+)\}/g, (match, name) => (name in params ? String(params[name]) : match));
  }

  function fill(el, key, nodes) {
    const parts = t(key).split(/(\{\w+\})/);
    el.replaceChildren(...parts.map((part) => {
      const name = part.match(/^\{(\w+)\}$/)?.[1];
      if (!name || !(name in nodes)) return document.createTextNode(part);
      const value = nodes[name];
      return value instanceof Node ? value : document.createTextNode(String(value));
    }));
  }

  /* Messages from the server carry a translation code and an English fallback. */
  function message(payload) {
    if (!payload) return '';
    if (typeof payload === 'string') return payload;
    return lookup(payload.code) !== undefined ? t(payload.code, payload.params) : (payload.message || payload.code);
  }

  function apply(root = document) {
    root.querySelectorAll('[data-i18n]').forEach((el) => { el.textContent = t(el.dataset.i18n); });
    root.querySelectorAll('[data-i18n-html]').forEach((el) => { el.innerHTML = t(el.dataset.i18nHtml); });
    root.querySelectorAll('[data-i18n-attr]').forEach((el) => {
      for (const pair of el.dataset.i18nAttr.split(';')) {
        const [attr, key] = pair.split(':').map((s) => s.trim());
        if (attr && key) el.setAttribute(attr, t(key));
      }
    });
    document.documentElement.lang = current;
  }

  function setLanguage(setting) {
    current = detect(setting);
    apply();
    return current;
  }

  window.I18N = {
    define, detect, t, fill, message, apply, setLanguage,
    get language() { return current; },
  };
})();
