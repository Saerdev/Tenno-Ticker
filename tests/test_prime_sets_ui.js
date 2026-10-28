/* Lightweight DOM test for the Prime Sets table; no browser package required. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const snapshot = JSON.parse(fs.readFileSync(path.join(root, 'site/data/prime-sets.json'), 'utf8'));
const script = fs.readFileSync(path.join(root, 'site/prime-sets.js'), 'utf8');
const handlers = new Map();
const elements = new Map();
const headers = ['name', 'medianClosedPrice', 'volume'].map((sort) => ({
  dataset: { sort },
  setAttribute() {},
  querySelector() { return { textContent: '' }; },
}));

function element(id) {
  if (!elements.has(id)) elements.set(id, {
    value: id === 'prime-sort' ? 'name' : '',
    checked: false,
    innerHTML: '',
    textContent: '',
    hidden: false,
    disabled: false,
    addEventListener(type, handler) { handlers.set(`${id}:${type}`, handler); },
    querySelectorAll() { return id === 'prime-head' ? headers : []; },
  });
  return elements.get(id);
}

function renderedNames() {
  return [...element('prime-body').innerHTML.matchAll(/<tr><td>([^<]+)<\/td>/g)]
    .map((match) => match[1]);
}

async function main() {
  vm.runInNewContext(script, {
    document: { getElementById: element },
    fetch: async () => ({ ok: true, json: async () => snapshot }),
    Date, Number, String, Object, Array,
  });
  // The initial fetch/render uses async microtasks.
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(renderedNames().length, snapshot.sets.length);
  assert.equal((element('prime-body').innerHTML.match(/<td>/g) || []).length,
    snapshot.sets.length * 3);

  const escapeHtml = (value) => value.replace(/[&<>"']/g, (char) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
  const byName = new Map(snapshot.sets.map((row) => [escapeHtml(row.name), row]));
  function clickHeader(sort) {
    handlers.get('prime-head:click')({ target: { closest: () => ({ dataset: { sort } }) } });
    return renderedNames().map((name) => byName.get(name));
  }
  const descendingMedian = clickHeader('medianClosedPrice');
  assert.ok(descendingMedian.every((row, i) => !i ||
    row.medianClosedPrice <= descendingMedian[i - 1].medianClosedPrice));
  const ascendingMedian = clickHeader('medianClosedPrice');
  assert.ok(ascendingMedian.every((row, i) => !i ||
    row.medianClosedPrice >= ascendingMedian[i - 1].medianClosedPrice));
  const descendingVolume = clickHeader('volume');
  assert.ok(descendingVolume.every((row, i) => !i || row.volume <= descendingVolume[i - 1].volume));
  console.log(`Prime Sets UI: ${snapshot.sets.length} rows, 3 cells per row, median/volume sorting passed`);
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
