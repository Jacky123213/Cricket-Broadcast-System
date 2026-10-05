const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('frontend/assets/battery.js', 'utf8');
function setup(navigator = {}) {
  const context = {window: {}, navigator};
  vm.runInNewContext(source, context);
  return context.window.DRSBattery;
}
const flush = () => new Promise(resolve => setImmediate(resolve));
test('battery reports percentage, charging changes and cleans up listeners', async () => {
  const listeners = new Map();
  const manager = {level: .456, charging: false,
    addEventListener: (name, fn) => listeners.set(name, fn),
    removeEventListener: (name, fn) => { assert.equal(listeners.get(name), fn); listeners.delete(name); }};
  const api = setup({getBattery: async () => manager});
  const reports = [];
  const stop = api.watch(value => reports.push(value));
  await flush();
  assert.equal(reports[0], null);
  assert.equal(reports.at(-1).level, 46);
  assert.equal(api.describe(reports.at(-1)).label, '46%');
  manager.level = .1; listeners.get('levelchange')();
  assert.equal(api.describe(reports.at(-1)).state, 'low');
  manager.charging = true; listeners.get('chargingchange')();
  assert.equal(api.describe(reports.at(-1)).label, '⚡ 10%');
  assert.equal(api.describe(reports.at(-1)).state, 'charging');
  const count = reports.length;
  stop(); assert.equal(listeners.size, 0);
  assert.equal(reports.length, count);
});
test('unsupported, denied and invalid battery readings stay unavailable', async () => {
  for (const navigator of [{}, {getBattery: () => {throw Error('denied');}},
    {getBattery: async () => {throw Error('blocked');}},
    {getBattery: async () => ({level: NaN, charging: false, addEventListener() {}, removeEventListener() {}})}]) {
    const api = setup(navigator), reports = [];
    const stop = api.watch(value => reports.push(value)); await flush();
    assert.ok(reports.every(value => value === null));
    assert.equal(api.describe(reports.at(-1)).label, 'Battery unavailable'); stop();
  }
  const api = setup();
  for (const level of [-1, 101, '50', 12.5]) assert.equal(api.describe({level, charging: false}).state, 'unavailable');
  assert.equal(api.describe({level: 0, charging: false}).label, '0%');
});
test('late battery discovery after closing the camera cannot send telemetry', async () => {
  let resolve;
  const reports = [];
  const api = setup({getBattery: () => new Promise(r => {resolve = r;})});
  const stop = api.watch(value => reports.push(value)); await flush(); stop();
  resolve({level: 1, charging: true, addEventListener() {throw Error('must not subscribe');}});
  await flush(); assert.deepEqual(reports, [null]);
});
