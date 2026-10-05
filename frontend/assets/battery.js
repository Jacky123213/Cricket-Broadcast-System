/* Optional browser telemetry. Safari/iOS and denied access remain unavailable. */
(() => {
  'use strict';
  function watch(report) {
    let stopped = false, manager = null;
    const update = () => {
      if (stopped) return;
      const valid = Number.isFinite(manager?.level) && manager.level >= 0 && manager.level <= 1 &&
        typeof manager.charging === 'boolean';
      report(valid ? {level: Math.round(manager.level * 100), charging: manager.charging} : null);
    };
    report(null);
    if (typeof navigator.getBattery === 'function') {
      Promise.resolve().then(() => navigator.getBattery()).then(battery => {
        if (stopped) return;
        manager = battery;
        manager.addEventListener('levelchange', update);
        manager.addEventListener('chargingchange', update);
        update();
      }).catch(() => { if (!stopped) report(null); });
    }
    return () => {
      stopped = true;
      manager?.removeEventListener('levelchange', update);
      manager?.removeEventListener('chargingchange', update);
    };
  }
  function describe(battery) {
    if (!battery || !Number.isInteger(battery.level) || battery.level < 0 || battery.level > 100 ||
        typeof battery.charging !== 'boolean') {
      return {label: 'Battery unavailable', title: 'This camera browser does not report battery status', state: 'unavailable'};
    }
    return {label: `${battery.charging ? '⚡ ' : ''}${battery.level}%`,
      title: `Battery ${battery.level}% · ${battery.charging ? 'charging' : 'not charging'}`,
      state: battery.charging ? 'charging' : battery.level <= 20 ? 'low' : 'normal'};
  }
  window.DRSBattery = {watch, describe};
})();
