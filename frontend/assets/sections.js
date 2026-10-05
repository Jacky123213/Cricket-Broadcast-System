/* Folding controls never disables forms or reparents active media on toggle. */
(function () {
  'use strict';
  const sections = new Map();
  const namespace = 'cricket.sections.v1.' + location.pathname + '.';
  function remembered(key, fallback) {
    try { const value = localStorage.getItem(namespace + key); return value === null ? fallback : value === 'open'; }
    catch { return fallback; }
  }
  function persist(key, open) {
    try { localStorage.setItem(namespace + key, open ? 'open' : 'closed'); }
    catch { /* Restricted browser storage does not prevent folding. */ }
  }
  function init(root = document) {
    // Desktop settings and hardware-guide cards use the same folding controls.
    root.querySelectorAll('.settings-grid > article').forEach((card, index) => {
      if (!card.dataset.collapsible) card.dataset.collapsible = 'settings-card-' + index;
    });
    root.querySelectorAll('[data-collapsible]').forEach(section => {
      if (sections.has(section)) return;
      const key = section.dataset.collapsible;
      if (!key) return;
      if (section.tagName === 'DETAILS') {
        section.open = remembered(key, section.open);
        section.addEventListener('toggle', () => persist(key, section.open));
        sections.set(section, open => { section.open = open; persist(key, open); });
        return;
      }
      const heading = [...section.children].find(child => child.matches('h2, .section-title, .source-heading'));
      const title = heading?.matches('h2') ? heading : heading?.querySelector('h2');
      if (!title) return;
      const header = heading === title ? document.createElement('div') : heading;
      header.classList.add('section-collapse-header');
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'section-toggle'; button.textContent = title.textContent;
      button.setAttribute('aria-label', title.textContent);
      title.replaceChildren(button);
      if (header !== heading) header.append(title);
      const content = document.createElement('div');
      content.className = 'section-content';
      content.id = 'section-content-' + key;
      button.setAttribute('aria-controls', content.id);
      [...section.childNodes].filter(node => node !== header && node !== heading).forEach(node => content.append(node));
      section.append(header, content);
      section.classList.add('section-collapsible');
      const setOpen = (open, save = true) => {
        content.hidden = !open;
        button.setAttribute('aria-expanded', String(open));
        button.title = (open ? 'Minimise ' : 'Expand ') + button.textContent;
        section.classList.toggle('section-folded', !open);
        if (save) persist(key, open);
      };
      setOpen(remembered(key, section.dataset.collapseDefault !== 'closed'), false);
      button.addEventListener('click', () => setOpen(content.hidden));
      sections.set(section, setOpen);
    });
  }
  function open(target) {
    const element = typeof target === 'string' ? document.getElementById(target.replace(/^#/, '')) : target;
    if (!element) return;
    for (let section = element; section; section = section.parentElement) sections.get(section)?.(true);
  }
  function openHash() {
    try { open(decodeURIComponent(location.hash.slice(1))); } catch { /* Ignore malformed anchors. */ }
  }
  window.CricketSections = {init, open};
  document.addEventListener('click', event => {
    const link = event.target.closest?.('a[href]');
    if (!link) return;
    const url = new URL(link.href, location.href);
    if (url.origin === location.origin && url.pathname === location.pathname && url.hash) {
      try { open(decodeURIComponent(url.hash.slice(1))); } catch { /* Ignore malformed anchors. */ }
    }
  });
  window.addEventListener('hashchange', openHash);
  const start = () => { init(); openHash(); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
}());
