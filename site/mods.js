(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const els = {
    body: $('mod-body'), head: $('mod-head'), search: $('mod-search'), sort: $('mod-sort'),
    direction: $('mod-direction'), priced: $('mod-priced'), refresh: $('mod-refresh'),
    count: $('mod-count'), total: $('mod-total'), footer: $('mod-footer-count'),
    status: $('mod-status'), error: $('mod-error'), more: $('mod-more'), tooltip: $('mod-tooltip'),
  };
  const state = {
    items: [], bySlug: new Map(), rank: 'rank0', sort: 'name', direction: 'asc',
    sourceDate: null, comparisonDate: null, loading: false, limit: 200, tooltipSlug: null,
  };
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const num = (v) => typeof v === 'number' && Number.isFinite(v) ? v : null;
  const rankStats = (item) => item[state.rank] || {};
  const safeWiki = (url, name) =>
    typeof url === 'string' && /^https:\/\/wiki\.warframe\.com\/w\//.test(url)
      ? url : 'https://wiki.warframe.com/w/' + encodeURIComponent(name.replaceAll(' ', '_'));
  function shownPrice(value) {
    const n = num(value);
    return n === null || n < 0 ? '<span class="prime-missing">—</span>'
      : '<span class="prime-trade">' + Math.floor(n).toLocaleString('en-US') + '</span><span class="prime-pt">p</span>';
  }
  function shownVolume(value) {
    const n = num(value);
    return n === null || n < 0 ? '<span class="prime-missing">—</span>' : n.toLocaleString('en-US');
  }
  function shownChange(value) {
    const n = num(value);
    if (n === null) return '<span class="prime-missing">—</span>';
    const cls = n > 0 ? 'prime-change-up' : n < 0 ? 'prime-change-down' : 'prime-change-flat';
    const prefix = n > 0 ? '↑ +' : n < 0 ? '↓ −' : '';
    return '<span class="prime-change ' + cls + '" title="Comparison: ' + esc(state.comparisonDate) + ' to ' + esc(state.sourceDate) + '">' + prefix + Math.abs(n).toFixed(1) + '%</span>';
  }
  function visible() {
    const query = els.search.value.trim().toLowerCase();
    return state.items.filter((item) => (!query || item.name.toLowerCase().includes(query))
      && (!els.priced.checked || num(rankStats(item).medianClosedPrice) !== null))
      .sort((a, b) => {
        const field = state.sort;
        const aVal = field === 'name' ? a.name.toLowerCase() : num(rankStats(a)[field]);
        const bVal = field === 'name' ? b.name.toLowerCase() : num(rankStats(b)[field]);
        if (aVal === null) return bVal === null ? a.name.localeCompare(b.name) : 1;
        if (bVal === null) return -1;
        const diff = typeof aVal === 'string' ? aVal.localeCompare(bVal) : aVal - bVal;
        return diff ? (state.direction === 'asc' ? diff : -diff) : a.name.localeCompare(b.name);
      });
  }
  function row(item) {
    const s = rankStats(item);
    const wiki = safeWiki(item.wikiUrl, item.name);
    return `<tr><td><a class="mod-name" data-mod="${esc(item.slug)}" href="https://warframe.market/items/${encodeURIComponent(item.slug)}" target="_blank" rel="noopener noreferrer" aria-describedby="mod-tooltip">${esc(item.name)}</a><span class="mod-name-sub">MAX RANK ${esc(item.maxRank)}</span></td>
      <td>${shownPrice(s.medianClosedPrice)}</td><td>${shownVolume(s.volume)}</td><td>${shownChange(s.change7dPct)}</td>
      <td class="action-cell"><div class="action-group"><a class="wiki-link" href="${esc(wiki)}" target="_blank" rel="noopener noreferrer" aria-label="View ${esc(item.name)} on the Warframe Wiki">Wiki ↗</a></div></td></tr>`;
  }
  function render() {
    hideTooltip();
    const items = visible();
    els.body.innerHTML = items.length ? items.slice(0, state.limit).map(row).join('') :
      '<tr><td colspan="5" class="empty-state">No mods match these filters.</td></tr>';
    els.count.textContent = `${items.length.toLocaleString()} of ${state.items.length.toLocaleString()} mods match`;
    els.footer.textContent = `Showing ${Math.min(items.length, state.limit).toLocaleString()} of ${items.length.toLocaleString()} matching mods`;
    els.total.textContent = state.items.length.toLocaleString();
    els.more.hidden = items.length <= state.limit;
    els.head.querySelectorAll('th[data-sort]').forEach((th) => {
      const on = th.dataset.sort === state.sort;
      th.setAttribute('aria-sort', on ? (state.direction === 'asc' ? 'ascending' : 'descending') : 'none');
      th.querySelector('.prime-sort-arrow').textContent = on ? (state.direction === 'asc' ? '↑' : '↓') : '↕';
    });
    els.direction.textContent = state.direction === 'asc' ? 'A–Z / ↑' : 'Z–A / ↓';
  }
  function tooltipHtml(item) {
    const sources = Array.isArray(item.sources) ? item.sources : [];
    const list = sources.map((s) => `<li><span>${esc(s.location)}</span>${typeof s.chance === 'number' ? '<span class="acquisition-chance">' + esc(s.chance.toLocaleString('en-US', { maximumFractionDigits: 3 })) + '%</span>' : ''}</li>`).join('');
    const wiki = safeWiki(item.wikiUrl, item.name);
    return `<div class="acquisition-heading"><span>MOD ACQUISITION</span><strong>${esc(item.name)}</strong></div>
      ${list ? '<ul class="acquisition-list">' + list + '</ul>' : '<p class="acquisition-empty">No drop or vendor location is documented in the mod catalog for this item. Check the Wiki for acquisition methods.</p>'}
      <div class="acquisition-footer"><span>Documented sources: ${sources.length}</span><a href="${esc(wiki)}" target="_blank" rel="noopener noreferrer">Open Wiki ↗</a></div>`;
  }
  function hideTooltip() {
    state.tooltipSlug = null;
    els.tooltip.hidden = true;
  }
  function showTooltip(trigger) {
    const item = state.bySlug.get(trigger.dataset.mod);
    if (!item || state.tooltipSlug === item.slug) return;
    state.tooltipSlug = item.slug;
    els.tooltip.innerHTML = tooltipHtml(item);
    els.tooltip.hidden = false;
    positionTooltip(trigger);
  }
  function positionTooltip(trigger) {
    const rect = trigger.getBoundingClientRect();
    const box = els.tooltip.getBoundingClientRect();
    const margin = 12;
    const right = rect.right + margin;
    let left = right + box.width <= innerWidth - margin ? right : rect.left - box.width - margin;
    if (left < margin) left = Math.max(margin, Math.min(rect.left, innerWidth - box.width - margin));
    let top = Math.min(rect.top, innerHeight - box.height - margin);
    top = Math.max(margin, top);
    els.tooltip.style.left = left + 'px';
    els.tooltip.style.top = top + 'px';
  }
  function showError(msg) { els.error.hidden = false; els.error.textContent = msg; }
  async function load() {
    if (state.loading) return;
    state.loading = true;
    els.refresh.disabled = true;
    els.error.hidden = true;
    try {
      const response = await fetch('./data/mods.json?t=' + Date.now(), { cache: 'no-store' });
      if (!response.ok) throw new Error('HTTP ' + response.status);
      const data = await response.json();
      if (data.schemaVersion !== 1 || data.category !== 'mod' || !Array.isArray(data.items))
        throw new Error('Unsupported Mod data');
      state.items = data.items.filter((i) => i && typeof i.name === 'string' && typeof i.slug === 'string');
      state.bySlug = new Map(state.items.map((i) => [i.slug, i]));
      state.sourceDate = data.sourceDate;
      state.comparisonDate = data.comparisonDate;
      els.status.textContent = 'Latest published snapshot · ' + data.sourceDate;
      const age = Math.floor((Date.now() - Date.parse(data.sourceDate + 'T00:00:00Z')) / 86400000);
      if (Number.isFinite(age) && age > 2) showError('The most recent reported Mod prices are ' + age + ' days old.');
    } catch (error) {
      showError('Could not load Mod prices: ' + error.message);
      els.status.textContent = 'Mod prices unavailable';
    } finally {
      state.loading = false;
      els.refresh.disabled = false;
      render();
    }
  }
  function resetRender() { state.limit = 200; render(); }
  function setSort(field) {
    if (!['name', 'medianClosedPrice', 'volume', 'change7dPct'].includes(field)) return;
    if (state.sort === field) state.direction = state.direction === 'asc' ? 'desc' : 'asc';
    else { state.sort = field; state.direction = field === 'name' ? 'asc' : 'desc'; }
    els.sort.value = field;
    resetRender();
  }
  els.search.addEventListener('input', resetRender);
  els.priced.addEventListener('change', resetRender);
  document.querySelectorAll('input[name="mod-rank"]').forEach((radio) => radio.addEventListener('change', () => {
    if (radio.checked) { state.rank = radio.value; resetRender(); }
  }));
  els.sort.addEventListener('change', () => setSort(els.sort.value));
  els.head.addEventListener('click', (e) => {
    const button = e.target.closest('button[data-sort]');
    if (button) setSort(button.dataset.sort);
  });
  els.direction.addEventListener('click', () => { state.direction = state.direction === 'asc' ? 'desc' : 'asc'; resetRender(); });
  els.more.addEventListener('click', () => { state.limit += 200; render(); });
  els.refresh.addEventListener('click', load);
  els.body.addEventListener('pointerover', (e) => {
    const link = e.target.closest('[data-mod]');
    if (link) showTooltip(link);
  });
  els.body.addEventListener('pointerout', (e) => {
    const link = e.target.closest('[data-mod]');
    if (link && !link.contains(e.relatedTarget) && !els.tooltip.contains(e.relatedTarget)) hideTooltip();
  });
  els.body.addEventListener('focusin', (e) => {
    const link = e.target.closest('[data-mod]');
    if (link) showTooltip(link);
  });
  els.body.addEventListener('focusout', (e) => {
    if (!els.tooltip.contains(e.relatedTarget)) hideTooltip();
  });
  els.tooltip.addEventListener('pointerleave', hideTooltip);
  window.addEventListener('scroll', hideTooltip, true);
  window.addEventListener('resize', hideTooltip);
  load();
})();
