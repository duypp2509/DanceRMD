/* DanceRMD landing page — progressive enhancements only; the page works without this file. */
'use strict';

/** The single place to change when the repository moves. */
const REPO_URL = 'https://github.com/duypham-dev/DanceRMD';

const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

/** Point every `[data-repo]` link at REPO_URL (the value is the path suffix, e.g. "/releases"). */
function wireRepoLinks() {
  document.querySelectorAll('a[data-repo]').forEach((link) => {
    link.href = REPO_URL + link.dataset.repo;
  });
}

/** Mobile navigation: toggle button, Escape to close, close on link click or outside click. */
function setupNavigation() {
  const header = document.querySelector('.site-header');
  const toggle = header?.querySelector('.nav-toggle');
  const nav = document.getElementById('site-nav');
  if (!header || !toggle || !nav) return;

  const setOpen = (open, { restoreFocus = false } = {}) => {
    header.classList.toggle('nav-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    if (open) nav.querySelector('a')?.focus();
    else if (restoreFocus) toggle.focus();
  };

  toggle.addEventListener('click', () => setOpen(!header.classList.contains('nav-open')));
  nav.addEventListener('click', (event) => {
    if (event.target.closest('a')) setOpen(false);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && header.classList.contains('nav-open')) setOpen(false, { restoreFocus: true });
  });
  document.addEventListener('click', (event) => {
    if (header.classList.contains('nav-open') && !header.contains(event.target)) setOpen(false);
  });
  window.matchMedia('(min-width: 900px)').addEventListener('change', (event) => {
    if (event.matches) setOpen(false);
  });

  const onScroll = () => header.classList.toggle('is-scrolled', window.scrollY > 8);
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
}

/** Fade sections in as they enter the viewport. */
function setupReveal() {
  const items = document.querySelectorAll('.reveal');
  if (prefersReducedMotion.matches || !('IntersectionObserver' in window)) {
    items.forEach((item) => item.classList.add('is-visible'));
    return;
  }
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-visible');
      observer.unobserve(entry.target);
    });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.12 });
  items.forEach((item) => observer.observe(item));
}

/** Decorative "code rain" behind the hero visual, echoing the mascot artwork. */
function setupCodeRain() {
  const host = document.querySelector('[data-rain]');
  if (!host) return;
  const glyphs = '0123456789ABCDEF{}[]<>=;:/*+#$';
  const columns = Math.max(6, Math.min(18, Math.round(host.clientWidth / 42)));
  const rows = 34;
  const fragment = document.createDocumentFragment();
  for (let c = 0; c < columns; c += 1) {
    let text = '';
    for (let r = 0; r < rows; r += 1) text += glyphs[Math.floor(Math.random() * glyphs.length)] + '\n';
    const column = document.createElement('span');
    column.className = 'rain-col';
    column.textContent = text + text; // doubled so the scroll animation loops seamlessly
    column.style.setProperty('--dur', `${14 + Math.random() * 16}s`);
    column.style.setProperty('--delay', `${-Math.random() * 20}s`);
    fragment.append(column);
  }
  host.append(fragment);
}

function setYear() {
  document.querySelectorAll('[data-year]').forEach((node) => {
    node.textContent = String(new Date().getFullYear());
  });
}

wireRepoLinks();
setupNavigation();
setupReveal();
setupCodeRain();
setYear();
