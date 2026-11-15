/* Local display preferences only. Match settings and output colours live on the server. */
window.CricketPreferences = (() => {
  'use strict';
  const key = 'cricket.appearance.v1', liveKey = 'cricket.local-live-views.v1';
  const media = window.matchMedia?.('(prefers-color-scheme: light)');
  let current = {theme: 'dark', text: 'normal'};
  function read() {try {const value = JSON.parse(localStorage.getItem(key) || '{}'); current = {theme: ['dark','light','system'].includes(value.theme) ? value.theme : 'dark', text: value.text === 'large' ? 'large' : 'normal'};} catch { /* Restricted storage keeps defaults. */ }}
  function apply() {const root = document.documentElement; root.dataset.theme = current.theme === 'system' ? (media?.matches ? 'light' : 'dark') : current.theme; root.dataset.text = current.text; root.style.colorScheme = root.dataset.theme; window.dispatchEvent(new CustomEvent('cricket-appearance', {detail: {...current}}));}
  function save(value) {current = {...current, ...value}; if (!['dark','light','system'].includes(current.theme)) current.theme = 'dark'; current.text = current.text === 'large' ? 'large' : 'normal'; try {localStorage.setItem(key, JSON.stringify(current));} catch {} apply();}
  function live(enabled) {try {localStorage.setItem(liveKey, enabled ? 'on' : 'off');} catch {} window.dispatchEvent(new CustomEvent('cricket-live-views', {detail: enabled})); if (window.parent !== window) window.parent.postMessage({type: 'cricket-live-views', enabled}, location.origin);}
  function liveEnabled() {try {return localStorage.getItem(liveKey) !== 'off';} catch {return true;}}
  window.addEventListener('storage', event => {if (event.key === key) {read(); apply();} if (event.key === liveKey) window.dispatchEvent(new CustomEvent('cricket-live-views', {detail: liveEnabled()}));});
  media?.addEventListener?.('change', apply); read(); apply();
  return {get: () => ({...current}), save, live, liveEnabled};
})();
