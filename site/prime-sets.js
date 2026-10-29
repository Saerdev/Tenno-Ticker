(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const els = {
    body: $('prime-body'), head: $('prime-head'), search: $('prime-search'), sort: $('prime-sort'),
    direction: $('prime-direction'), priced: $('prime-priced'), refresh: $('prime-refresh'),
    vaultedOnly: $('prime-vaulted-only'), unvaultedOnly: $('prime-unvaulted-only'),
    favorites: $('prime-favorites-only'),
    count: $('prime-count'), total: $('prime-total'),
    footerCount: $('prime-footer-count'), status: $('prime-status'),
    error: $('prime-error'), tradeNote: $('prime-data-note'), vaultChecked: $('prime-vault-checked'),
  };
  const FAVORITES_KEY = 'tenno-ticker-prime-watchlist';
  function readFavorites() {
    try {
      const saved = JSON.parse(localStorage.getItem(FAVORITES_KEY) || '[]');
      return new Set(Array.isArray(saved) ? saved.filter((name) => typeof name === 'string') : []);
    } catch { return new Set(); }
  }
  const state = {
    sets: [], sourceDate: null, comparisonDate: null, sort: 'name', direction: 'asc', loading: false,
    favorites: readFavorites(), favoritesOnly: false,
  };
  function persistFavorites() {
    try { localStorage.setItem(FAVORITES_KEY, JSON.stringify([...state.favorites])); } catch {}
  }
  function updateFavoritesFilter() {
    els.favorites.classList.toggle('active', state.favoritesOnly);
    els.favorites.setAttribute('aria-pressed', String(state.favoritesOnly));
    els.favorites.querySelector('span').textContent = state.favoritesOnly ? '★' : '☆';
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (char) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
  }
  function number(value) {
    return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;
  }
  function signedNumber(value) {
    return typeof value === 'number' && Number.isFinite(value) ? value : null;
  }
  function price(value, cls = '') {
    const n = number(value);
    return n === null ? '<span class="prime-missing">—</span>' :
      `<span class="${cls}">${Math.floor(n).toLocaleString('en-US')}</span><span class="prime-pt">p</span>`;
  }
  function volume(value) {
    const n = number(value);
    return n === null ? '<span class="prime-missing">—</span>' : escapeHtml(n.toLocaleString('en-US'));
  }
  function change7d(value) {
    const n = signedNumber(value);
    if (n === null) return '<span class="prime-missing">—</span>';
    const trend = n > 0 ? 'prime-change-up' : n < 0 ? 'prime-change-down' : 'prime-change-flat';
    const prefix = n > 0 ? '↑ +' : n < 0 ? '↓ −' : '';
    const period = `${state.comparisonDate} to ${state.sourceDate}`;
    return `<span class="prime-change ${trend}" title="Closed-order median change: ${escapeHtml(period)}">${prefix}${Math.abs(n).toFixed(1)}%</span>`;
  }
  function vaulted(value) {
    if (typeof value !== 'boolean') return '<span class="prime-missing">—</span>';
    const description = value ? 'No relics in normal drop tables' : 'At least one relic in normal drop tables';
    return `<span class="prime-vault prime-vault-${value ? 'yes' : 'no'}" title="${description}">${value ? 'Yes' : 'No'}</span>`;
  }
  function marketUrl(name) {
    const slug = name.toLowerCase().replace(/&/g, 'and')
      .replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
    return `https://warframe.market/items/${slug}`;
  }
  function wikiUrl(name) {
    const article = name.replace(/\s+Set$/i, '').replace(/\s+/g, '_');
    return `https://wiki.warframe.com/w/${encodeURIComponent(article)}`;
  }
  function ageInDays(date) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date || '')) return null;
    const ms = Date.parse(`${date}T00:00:00Z`);
    return Number.isFinite(ms) ? Math.max(0, Math.floor((Date.now() - ms) / 86400000)) : null;
  }
  function visible() {
    const query = els.search.value.trim().toLocaleLowerCase();
    const field = state.sort;
    const vaultFilter = els.vaultedOnly.checked ? true : els.unvaultedOnly.checked ? false : null;
    return state.sets.filter((item) =>
      (!state.favoritesOnly || state.favorites.has(item.name)) &&
      (!query || item.name.toLocaleLowerCase().includes(query)) &&
      (!els.priced.checked || number(item.medianClosedPrice) !== null) &&
      (vaultFilter === null || item.vaulted === vaultFilter)
    ).sort((a, b) => {
      const av = field === 'name' ? a.name.toLocaleLowerCase() :
        field === 'vaulted' ? (typeof a.vaulted === 'boolean' ? Number(a.vaulted) : null) :
        field === 'change7dPct' ? signedNumber(a[field]) : number(a[field]);
      const bv = field === 'name' ? b.name.toLocaleLowerCase() :
        field === 'vaulted' ? (typeof b.vaulted === 'boolean' ? Number(b.vaulted) : null) :
        field === 'change7dPct' ? signedNumber(b[field]) : number(b[field]);
      if (av === null) return bv === null ? a.name.localeCompare(b.name) : 1;
      if (bv === null) return -1;
      let comparison = typeof av === 'string' ? av.localeCompare(bv) : av - bv;
      if (!comparison) comparison = a.name.localeCompare(b.name);
      return state.direction === 'desc' ? -comparison : comparison;
    });
  }
  function row(item) {
    const itemTitle = item.name.replace(/\s+Set$/i, '');
    const favorite = state.favorites.has(item.name);
    return `<tr><td><a class="prime-market-link" href="${marketUrl(item.name)}" target="_blank" rel="noopener noreferrer" title="View ${escapeHtml(item.name)} on Warframe.market">${escapeHtml(item.name)}</a></td>
      <td>${price(item.medianClosedPrice, 'prime-trade')}</td>
      <td>${volume(item.volume)}</td>
      <td>${change7d(item.change7dPct)}</td>
      <td>${vaulted(item.vaulted)}</td>
      <td class="action-cell"><div class="action-group"><button type="button" class="favorite-btn${favorite ? ' active' : ''}" data-favorite="${escapeHtml(item.name)}" aria-label="${favorite ? 'Remove from' : 'Add to'} watchlist: ${escapeHtml(item.name)}" aria-pressed="${favorite}">${favorite ? '★' : '☆'}</button><a class="wiki-link" href="${wikiUrl(item.name)}" target="_blank" rel="noopener noreferrer" aria-label="View ${escapeHtml(itemTitle)} on the Warframe Wiki">Wiki ↗</a></div></td></tr>`;
  }
  function render() {
    const items = visible();
    els.body.innerHTML = items.length ? items.map(row).join('') :
      `<tr><td colspan="6" class="empty-state">${state.loading ? 'Loading Prime sets…' : state.favoritesOnly && !state.favorites.size ? 'Your watchlist is empty. Star a Prime set to save it here.' : 'No Prime sets match these filters.'}</td></tr>`;
    els.count.textContent = `${items.length.toLocaleString()} of ${state.sets.length.toLocaleString()} sets shown`;
    els.footerCount.textContent = `Showing ${items.length.toLocaleString()} Prime sets`;
    els.total.textContent = state.sets.length ? state.sets.length.toLocaleString() : '—';
    els.tradeNote.hidden = !state.sets.length || state.sets.some((item) =>
      number(item.medianClosedPrice) !== null || number(item.volume) !== null);
    els.head.querySelectorAll('th[data-sort]').forEach((header) => {
      const selected = header.dataset.sort === state.sort;
      header.setAttribute('aria-sort', selected ? (state.direction === 'asc' ? 'ascending' : 'descending') : 'none');
      header.querySelector('.prime-sort-arrow').textContent = selected ? (state.direction === 'asc' ? '↑' : '↓') : '↕';
    });
    els.direction.textContent = state.direction === 'asc' ? 'A–Z / ↑' : 'Z–A / ↓';
    els.direction.title = `Current sort: ${state.direction === 'asc' ? 'ascending' : 'descending'}. Click to reverse.`;
  }
  function showError(message) { els.error.hidden = false; els.error.textContent = message; }
  async function loadVaultCatalog() {
    const response = await fetch(`./data/prime-vault-status.json?t=${Date.now()}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const catalog = await response.json();
    if (!catalog || typeof catalog.sets !== 'object' || !catalog.sets ||
        typeof catalog.checkedAt !== 'string') throw new Error('Unsupported vault status catalog');
    return catalog;
  }
  async function load() {
    if (state.loading) return;
    state.loading = true;
    els.refresh.disabled = true;
    els.status.textContent = 'Checking published Prime set snapshot…';
    els.error.hidden = true;
    // A missing Wiki catalog must never prevent prices from loading.
    const vaultPromise = loadVaultCatalog().catch(() => null);
    try {
      const response = await fetch(`./data/prime-sets.json?t=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (data.schemaVersion !== 3 || data.source !== 'Relics.run/history' ||
          !Array.isArray(data.sets)) throw new Error('Unsupported Prime set snapshot');
      const vaultCatalog = await vaultPromise;
      state.sets = data.sets.filter((item) => item && typeof item.name === 'string' &&
        item.name.toLocaleLowerCase().endsWith(' prime set')).map((item) => {
        const wikiStatus = vaultCatalog?.sets[item.name];
        return { ...item, vaulted: typeof wikiStatus === 'boolean' ? wikiStatus : null };
      });
      const checked = vaultCatalog ? Date.parse(vaultCatalog.checkedAt) : NaN;
      els.vaultChecked.textContent = Number.isFinite(checked) ?
        `Last Wiki check: ${new Date(checked).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}.` :
        'Wiki vault status currently unavailable.';
      state.sourceDate = data.sourceDate;
      state.comparisonDate = data.comparisonDate;
      if (!state.sets.length) {
        showError('No Prime set prices have been published yet. The site owner can run Update prices & deploy in GitHub Actions.');
        els.status.textContent = 'Awaiting first Prime set scan';
      } else {
        const age = ageInDays(state.sourceDate);
        els.status.textContent = `Latest published snapshot · ${state.sourceDate}`;
        if (age === null) showError('The source date is missing or invalid. Check the published snapshot.');
        else if (age > 2) showError(`Relics.run's newest published source day is ${state.sourceDate} (${age} days old). These are historical prices, not current market quotes.`);
      }
    } catch (error) {
      showError(`Could not load Prime set prices: ${error.message}`);
      els.status.textContent = 'Prime set data unavailable';
    } finally {
      state.loading = false;
      els.refresh.disabled = false;
      render();
    }
  }
  function setSort(field) {
    if (!['name', 'medianClosedPrice', 'volume', 'change7dPct', 'vaulted'].includes(field)) return;
    if (state.sort === field) state.direction = state.direction === 'asc' ? 'desc' : 'asc';
    else {
      state.sort = field;
      state.direction = field === 'name' ? 'asc' : 'desc';
    }
    els.sort.value = state.sort;
    render();
  }
  els.search.addEventListener('input', render);
  els.priced.addEventListener('change', render);
  els.favorites.addEventListener('click', () => {
    state.favoritesOnly = !state.favoritesOnly;
    updateFavoritesFilter();
    render();
  });
  els.body.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-favorite]');
    if (!button) return;
    const name = button.dataset.favorite;
    if (state.favorites.has(name)) state.favorites.delete(name);
    else state.favorites.add(name);
    persistFavorites();
    render();
  });
  els.vaultedOnly.addEventListener('change', () => {
    if (els.vaultedOnly.checked) els.unvaultedOnly.checked = false;
    render();
  });
  els.unvaultedOnly.addEventListener('change', () => {
    if (els.unvaultedOnly.checked) els.vaultedOnly.checked = false;
    render();
  });
  els.sort.addEventListener('change', () => setSort(els.sort.value));
  els.head.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-sort]');
    if (button) setSort(button.dataset.sort);
  });
  els.direction.addEventListener('click', () => {
    state.direction = state.direction === 'asc' ? 'desc' : 'asc';
    render();
  });
  els.refresh.addEventListener('click', load);
  load();
})();
