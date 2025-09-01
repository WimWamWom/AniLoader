const overviewEl = document.getElementById('overviewContainer');
const logBox = document.getElementById('logBox');
const autoScrollChk = document.getElementById('autoScroll');
const copyLogsBtn = document.getElementById('copyLogs');
const lastUpdated = document.getElementById('lastUpdated');
const refreshBtn = document.getElementById('refreshBtn');
const logFilter = document.getElementById('logFilter');
const clearFilter = document.getElementById('clearFilter');
const dbBody = document.getElementById('db-table-body');
const dbRefresh = document.getElementById('db-refresh');
const dbSearch = document.getElementById('db-search');
const dbComplete = document.getElementById('db-complete');
const dbDeutsch = document.getElementById('db-deutsch');
const dbSort = document.getElementById('db-sort');
const dbOrder = document.getElementById('db-order');

const startDefault = document.getElementById('start-default');
const startNew = document.getElementById('start-new');
const startGerman = document.getElementById('start-german');
const startMissing = document.getElementById('start-missing');


const downloadStatus = document.getElementById('download-status');
// removed current card; info now shown in overview card
const logCount = document.getElementById('log-count');
// Cache for per-season counts to avoid flicker while updating
const countsCache = {};

function setStartButtonsDisabled(disabled) {
  [startDefault, startNew, startGerman, startMissing].forEach(btn => {
    if (btn) btn.disabled = !!disabled;
  });
}
// stop button removed

async function apiGet(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error('API error ' + res.status);
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error('API error ' + res.status);
  return res.json();
}

async function fetchStatus() {
  try {
    const s = await apiGet('/status');
    const status = s.status || 'idle';
    if (status === 'kein-speicher') {
      downloadStatus.innerHTML = `Status: <span class="badge text-bg-danger">Kein Speicher</span>${s.mode ? ' • ' + s.mode : ''}`;
    } else {
      downloadStatus.textContent = `Status: ${status}${s.mode ? ' • ' + s.mode : ''}`;
    }
  // Disable start buttons while running
  setStartButtonsDisabled(status === 'running');
  // no separate current card anymore
  } catch(e) {
    console.error(e);
  }
}

function renderOverview(items) {
  overviewEl.innerHTML = '';
  if (!Array.isArray(items)) return;
  items.forEach(item => {
    const seasons = item.last_season || 0;
    const episodes = item.last_episode || 0;
    const films = item.last_film || 0;
  // Show current item while running
  const isRunning = (window.__status_status === 'running');
  const curSeason = window.__status_current_season;
  const curEpisode = window.__status_current_episode;
  const curIsFilm = window.__status_current_is_film;
  const card = document.createElement('div');
    card.className = 'col-12';
    // Include current run meta (index + started_at) if a download is active and matches this item
    const startedAt = window.__status_started_at ? new Date(window.__status_started_at*1000).toLocaleString() : null;
    const idxInfo = (typeof window.__status_current_index === 'number') ? `Index: ${window.__status_current_index}` : '';
  const countsText = countsCache[item.id] || '';
  card.innerHTML = `
      <div class="card">
        <div class="card-body">
          <div class="d-flex justify-content-between">
            <div>
              <h5 class="card-title mb-0">${item.title || '(kein Titel)'}</h5>
              <div class="small text-secondary">ID: ${item.id} • ${item.url ? `<a href="${item.url}" target="_blank" rel="noreferrer">${item.url}</a>` : ''}</div>
              ${(startedAt || idxInfo) ? `<div class="small mt-1 text-secondary">${idxInfo}${(idxInfo && startedAt) ? ' • ' : ''}${startedAt ? 'Gestartet: ' + startedAt : ''}</div>` : ''}
            </div>
            <div class="text-end">
              ${item.complete ? '<span class="badge text-bg-success">Komplett</span>' : '<span class="badge text-bg-warning">Läuft</span>'}
              ${item.deutsch_komplett ? '<span class="badge text-bg-primary">Deutsch komplett</span>' : '<span class="badge text-bg-secondary">Deutsch fehlend</span>'}
              ${item.deleted ? '<span class="badge text-bg-danger">Deleted</span>' : ''}
            </div>
          </div>
          <div class="mt-3">
            ${isRunning
              ? `<div class="fw-bold">Lädt runter: ${curIsFilm ? `Film ${curEpisode}` : `Staffel ${curSeason} • Episode ${curEpisode}`}</div>`
              : `<div class=\"d-flex justify-content-between small mb-1\">\n                <div>Staffeln: <strong>${seasons}</strong> • Episoden: <strong>${episodes}</strong></div>\n                <div>Filme: <strong>${films}</strong></div>\n              </div>`}
      <div class="small mt-2 text-secondary" id="counts-${item.id}">${countsText}</div>
          </div>
        </div>
      </div>
    `;
    overviewEl.appendChild(card);

    // Load per-season counts for this series
    (async () => {
      try {
        const counts = await apiGet(`/counts?id=${encodeURIComponent(item.id)}`);
        const tgt = document.getElementById(`counts-${item.id}`);
        if (!counts || !counts.per_season) return; // keep old
        const entries = Object.keys(counts.per_season).sort((a,b)=>Number(a)-Number(b)).map(s => `S${String(s).padStart(2,'0')}: ${counts.per_season[s]} Ep.`);
        const filmsTxt = typeof counts.films === 'number' && counts.films > 0 ? ` • Filme: ${counts.films}` : '';
        const txt = entries.length ? `Geladen pro Staffel: ${entries.join(' | ')}${filmsTxt}` : (filmsTxt ? `Geladen pro Staffel: -${filmsTxt}` : '');
        if (txt) {
          countsCache[item.id] = txt;
          if (tgt) tgt.textContent = txt;
        }
      } catch (e) {
        // keep existing text; do not overwrite
      }
    })();
  });
}

async function fetchOverview() {
  try {
    // Get current status to determine which anime is currently downloading
    const s = await apiGet('/status');
  // cache some status meta for renderOverview
  window.__status_started_at = s.started_at || null;
  window.__status_current_index = (typeof s.current_index === 'number') ? s.current_index : null;
  window.__status_current_title = s.current_title || null;
  window.__status_status = s.status || null;
  window.__status_current_season = (typeof s.current_season === 'number' || typeof s.current_season === 'string') ? s.current_season : null;
  window.__status_current_episode = (typeof s.current_episode === 'number' || typeof s.current_episode === 'string') ? s.current_episode : null;
  window.__status_current_is_film = !!s.current_is_film;
    const data = await apiGet('/database');
    let items = data.map(it => ({
      id: it.id,
      title: it.title,
      url: it.url,
      complete: it.complete,
      deutsch_komplett: it.deutsch_komplett,
      deleted: it.deleted,
      fehlende: it.fehlende,
      last_season: it.last_season || 0,
      last_episode: it.last_episode || 0,
      last_film: it.last_film || 0
    }));

    // If there's an active download, show only that anime in the overview.
    // Match by title first, fall back to id or url if provided by the status.
    if (s && (s.current_title || s.current_id || s.current_url)) {
      const match = items.find(i =>
        (s.current_title && i.title === s.current_title) ||
        (s.current_id && i.id === s.current_id) ||
        (s.current_url && i.url === s.current_url)
      );
      items = match ? [match] : [];
    } else {
      // No active download -> show nothing on the Download tab
      items = [];
    }

    renderOverview(items);
    lastUpdated.textContent = 'Stand: ' + new Date().toLocaleTimeString('de-DE');
  } catch(e) { console.error(e); }
}

/* ---------- Settings (config) ---------- */
const langList = document.getElementById('lang-list');
const minFreeInput = document.getElementById('min-free');
const saveConfigBtn = document.getElementById('save-config');
const resetConfigBtn = document.getElementById('reset-config');

async function fetchConfig() {
  try {
    const cfg = await apiGet('/config');
    renderLangList(cfg.languages || []);
    minFreeInput.value = cfg.min_free_gb ?? '';
  } catch(e) { console.error('fetchConfig', e); }
}

function renderLangList(langs) {
  langList.innerHTML = '';
  langs.forEach((l, idx) => {
    const li = document.createElement('li');
    li.className = 'list-group-item d-flex align-items-center justify-content-between';
    li.draggable = true;
    li.dataset.index = idx;
    // number badge + label
    const left = document.createElement('div');
    left.className = 'd-flex align-items-center gap-2';
    const num = document.createElement('span');
    num.className = 'badge rounded-pill text-bg-secondary';
    num.textContent = (idx + 1) + '.';
    const label = document.createElement('span');
    label.className = 'lang-label';
    label.textContent = l;
    left.appendChild(num);
    left.appendChild(label);
    const dragHint = document.createElement('span');
    dragHint.className = 'small text-secondary';
    dragHint.textContent = '⠿';
    li.appendChild(left);
    li.appendChild(dragHint);

    li.addEventListener('dragstart', onDragStart);
    li.addEventListener('dragover', onDragOver);
    li.addEventListener('drop', onDrop);
    li.addEventListener('dragend', onDragEnd);
    langList.appendChild(li);
  });
  renumberLangItems();
}

function renumberLangItems() {
  Array.from(langList.children).forEach((li, i) => {
    const num = li.querySelector('.badge');
    if (num) num.textContent = (i + 1) + '.';
  });
}

let dragSrc = null;
function onDragStart(e) {
  dragSrc = e.currentTarget;
  e.dataTransfer.effectAllowed = 'move';
}

function onDragOver(e) {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
}

function onDrop(e) {
  e.preventDefault();
  const target = e.currentTarget;
  if (dragSrc && target !== dragSrc) {
    const nodes = Array.from(langList.children);
    const srcIndex = nodes.indexOf(dragSrc);
    const tgtIndex = nodes.indexOf(target);
    if (srcIndex < tgtIndex) {
      langList.insertBefore(dragSrc, target.nextSibling);
    } else {
      langList.insertBefore(dragSrc, target);
    }
  }
  renumberLangItems();
}

function onDragEnd() { dragSrc = null; }

async function saveConfig() {
  const langs = Array.from(langList.children).map(li => {
    const label = li.querySelector('.lang-label');
    return (label ? label.textContent : li.textContent).trim();
  });
  const min_free_gb = parseFloat(minFreeInput.value) || 0;
  try {
    await apiPost('/config', { languages: langs, min_free_gb });
    alert('Einstellungen gespeichert');
  } catch(e) { alert('Speichern fehlgeschlagen'); console.error(e); }
}

function resetConfig() {
  fetchConfig();
}

saveConfigBtn?.addEventListener('click', saveConfig);
resetConfigBtn?.addEventListener('click', resetConfig);

// load config initially
fetchConfig();

// Datenbank-Filter mit Deleted
async function fetchDatabase() {
  try {
    const q = encodeURIComponent(dbSearch.value.trim());
    const complete = dbComplete.value; // jetzt enthält auch 'deleted'
  const deutsch = dbDeutsch ? dbDeutsch.value : '';
    const sort_by = dbSort.value;
    const order = dbOrder.value;
  const url = `/database?q=${q}&complete=${complete}&sort_by=${sort_by}&order=${order}${deutsch !== '' ? `&deutsch=${deutsch}` : ''}`;
    const data = await apiGet(url);
    dbBody.innerHTML = '';
    data.forEach(row => {
      const fehl = Array.isArray(row.fehlende) ? row.fehlende.join(', ') : (row.fehlende || '');
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${row.id}</td>
        <td>${row.title}</td>
        <td><a href="${row.url}" target="_blank" rel="noreferrer">${row.url}</a></td>
        <td>${row.complete ? "✅" : "❌"}</td>
        <td>${row.deutsch_komplett ? "✅" : "❌"}</td>
        <td>${row.deleted ? "✅" : "❌"}</td>
        <td class="mono small"><div class="cell-scroll">${fehl}</div></td>
        <td>${row.last_season || 0}/${row.last_episode || 0}/${row.last_film || 0}</td>
      `;
      dbBody.appendChild(tr);
    });
  } catch(e) { console.error(e); }
}

let lastLogs = [];
async function fetchLogs() {
  try {
    const data = await apiGet('/logs');
    if (!Array.isArray(data)) return;
    let lines = data.slice(-2000);
    const filterVal = logFilter.value.trim();
    if (filterVal) {
      try {
        const rx = new RegExp(filterVal, 'i');
        lines = lines.filter(l => rx.test(l));
      } catch(e) {}
    }
    if (lines.join('\n') === lastLogs.join('\n')) return;
    lastLogs = lines;
    // Build colorized log lines with [TAG] badges
    const frag = document.createDocumentFragment();
    if (lines.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'log-line';
      empty.textContent = 'Noch keine Logs...';
      frag.appendChild(empty);
    } else {
    for (const ln of lines) {
        const row = document.createElement('div');
        row.className = 'log-line';
        const m = ln.match(/^\s*\[([^\]]+)\]\s*(.*)$/);
        if (m) {
          const tag = m[1].trim();
          const rest = m[2] || '';
          const tagSpan = document.createElement('span');
      // Map tag variants to canonical categories for consistent colors
      const up = tag.toUpperCase();
      let category = 'INFO';
      if (up.includes('ERROR') || up.includes('FEHLER')) category = 'ERROR';
      else if (up.includes('WARN')) category = 'WARN';
      else if (up.includes('OK') || up.includes('SUCCESS')) category = 'OK';
      else if (up.includes('DB')) category = 'DB';
      else if (up.includes('CONFIG')) category = 'CONFIG';
      else if (up.includes('SYSTEM')) category = 'SYSTEM';
      else if (up.includes('DEL')) category = 'WARN';
      tagSpan.className = 'log-tag tag-' + category;
          tagSpan.textContent = tag;
          row.appendChild(tagSpan);
          row.appendChild(document.createTextNode(rest));
        } else {
          row.textContent = ln;
        }
        frag.appendChild(row);
      }
    }
    logBox.innerHTML = '';
    logBox.appendChild(frag);
    if (!autoScrollChk || autoScrollChk.checked) {
      logBox.scrollTop = logBox.scrollHeight;
    }
    logCount.textContent = lines.length;
  } catch(e) {}
}

async function fetchDisk() {
  try {
    const data = await apiGet('/disk');
    const el = document.getElementById('disk-free');
    if (!el) return;
    if (data && typeof data.free_gb === 'number') {
      // Backend returns GB as number; convert to appropriate unit
      const gb = data.free_gb;
      let value = gb;
      let unit = 'GB';
      if (gb >= 1024) {
        value = (gb / 1024);
        unit = 'TB';
      } else if (gb < 1) {
        value = (gb * 1024);
        unit = 'MB';
      }
      const shown = (unit === 'MB') ? Math.round(value) : (Math.round(value * 10) / 10);
      el.textContent = `Freier Speicher: ${shown} ${unit}`;
    } else if (data && data.free_gb === null) {
      el.textContent = `Freier Speicher: n/a`;
    }
  } catch(e) {
    console.error('fetchDisk', e);
  }
}


async function startDownload(mode) {
  try {
  // immediately disable to prevent double click until status polling updates
  setStartButtonsDisabled(true);
    await apiPost(`/start_download`, { mode });
    downloadStatus.textContent = `Status: starting (${mode})`;
    
  } catch(e) {
    console.error(e);
    downloadStatus.textContent = `Status: error`;
  setStartButtonsDisabled(false);
    
  }
}

// stop removed

/* Event listeners */
startDefault.addEventListener('click', () => startDownload('default'));
startNew.addEventListener('click', () => startDownload('new'));
startGerman.addEventListener('click', () => startDownload('german'));
startMissing.addEventListener('click', () => startDownload('check-missing'));
// no stop button
refreshBtn.addEventListener('click', () => { fetchOverview(); fetchDatabase(); fetchStatus(); });
clearFilter.addEventListener('click', () => { logFilter.value=''; });
dbRefresh.addEventListener('click', fetchDatabase);
dbSearch.addEventListener('keyup', (e) => { if (e.key === 'Enter') fetchDatabase(); });
dbComplete.addEventListener('change', fetchDatabase);
dbDeutsch?.addEventListener('change', fetchDatabase);
dbSort.addEventListener('change', fetchDatabase);
dbOrder.addEventListener('change', fetchDatabase);

/* start polling */
fetchOverview();
fetchDatabase();
fetchStatus();
fetchLogs();
fetchDisk();
setInterval(fetchOverview, 60000);
setInterval(fetchDatabase, 60000);
setInterval(fetchStatus, 60000);
setInterval(fetchLogs, 60000);
setInterval(fetchDisk, 60000);

// Logs toolbar actions
copyLogsBtn?.addEventListener('click', async () => {
  try {
    const text = Array.isArray(lastLogs) && lastLogs.length ? lastLogs.join('\n') : (logBox.textContent || '');
    await navigator.clipboard.writeText(text);
  } catch (e) {
    console.error('copy logs failed', e);
  }
});
