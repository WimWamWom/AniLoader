const overviewEl = document.getElementById('overviewContainer');
const logBox = document.getElementById('logBox');
const lastUpdated = document.getElementById('lastUpdated');
const refreshBtn = document.getElementById('refreshBtn');
const logFilter = document.getElementById('logFilter');
const clearFilter = document.getElementById('clearFilter');
const dbBody = document.getElementById('db-table-body');
const dbRefresh = document.getElementById('db-refresh');
const dbSearch = document.getElementById('db-search');
const dbComplete = document.getElementById('db-complete');
const dbSort = document.getElementById('db-sort');
const dbOrder = document.getElementById('db-order');

const startDefault = document.getElementById('start-default');
const startNew = document.getElementById('start-new');
const startGerman = document.getElementById('start-german');
const startMissing = document.getElementById('start-missing');


const downloadStatus = document.getElementById('download-status');
const currentCard = document.getElementById('current-card');
const logCount = document.getElementById('log-count');

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
    if (s.current_title) {
      currentCard.innerHTML = `
        <div class="card mb-3">
          <div class="card-body">
            <h5 class="card-title">${s.current_title}</h5>
            <div class="small text-secondary">Index: ${s.current_index ?? '-'}</div>
            <div class="mt-2 small">Gestartet: ${s.started_at ? new Date(s.started_at*1000).toLocaleString() : '-'}</div>
          </div>
        </div>`;
    } else {
      currentCard.innerHTML = '';
    }
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
    const pct = episodes ? 100 : 0;
    const card = document.createElement('div');
    card.className = 'col-12';
    card.innerHTML = `
      <div class="card">
        <div class="card-body">
          <div class="d-flex justify-content-between">
            <div>
              <h5 class="card-title mb-0">${item.title || '(kein Titel)'}</h5>
              <div class="small text-secondary">ID: ${item.id} • ${item.url}</div>
            </div>
            <div class="text-end">
              ${item.complete ? '<span class="badge text-bg-success">Komplett</span>' : '<span class="badge text-bg-warning">Läuft</span>'}
              ${item.deutsch_komplett ? '<span class="badge text-bg-primary">Deutsch komplett</span>' : '<span class="badge text-bg-secondary">Deutsch fehlend</span>'}
              ${item.deleted ? '<span class="badge text-bg-danger">Deleted</span>' : ''}
            </div>
          </div>
          <div class="mt-3">
            <div class="d-flex justify-content-between small mb-1">
              <div>Staffeln: <strong>${seasons}</strong> • Episoden: <strong>${episodes}</strong></div>
              <div>Filme: <strong>${films}</strong></div>
            </div>
            <div class="progress"><div class="progress-bar" role="progressbar" style="width:${pct}%;"></div></div>
          </div>
        </div>
      </div>
    `;
    overviewEl.appendChild(card);
  });
}

async function fetchOverview() {
  try {
    // Get current status to determine which anime is currently downloading
    const s = await apiGet('/status');
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
    const sort_by = dbSort.value;
    const order = dbOrder.value;
    const url = `/database?q=${q}&complete=${complete}&sort_by=${sort_by}&order=${order}`;
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
    logBox.textContent = lines.join('\n') || 'Noch keine Logs...';
    logBox.scrollTop = logBox.scrollHeight;
    logCount.textContent = lines.length;
  } catch(e) {}
}

async function fetchDisk() {
  try {
    const data = await apiGet('/disk');
    const el = document.getElementById('disk-free');
    if (!el) return;
    if (data && typeof data.free_gb === 'number') {
      el.textContent = `Freier Speicher: ${data.free_gb} GB`;
    } else if (data && data.free_gb === null) {
      el.textContent = `Freier Speicher: n/a`;
    }
  } catch(e) {
    console.error('fetchDisk', e);
  }
}


async function startDownload(mode) {
  try {
    await apiPost(`/start_download`, { mode });
    downloadStatus.textContent = `Status: starting (${mode})`;
  } catch(e) {
    console.error(e);
    downloadStatus.textContent = `Status: error`;
  }
}

/* Event listeners */
startDefault.addEventListener('click', () => startDownload('default'));
startNew.addEventListener('click', () => startDownload('new'));
startGerman.addEventListener('click', () => startDownload('german'));
startMissing.addEventListener('click', () => startDownload('check-missing'));
refreshBtn.addEventListener('click', () => { fetchOverview(); fetchDatabase(); fetchStatus(); });
clearFilter.addEventListener('click', () => { logFilter.value=''; });
dbRefresh.addEventListener('click', fetchDatabase);
dbSearch.addEventListener('keyup', (e) => { if (e.key === 'Enter') fetchDatabase(); });
dbComplete.addEventListener('change', fetchDatabase);
dbSort.addEventListener('change', fetchDatabase);
dbOrder.addEventListener('change', fetchDatabase);

/* start polling */
fetchOverview();
fetchDatabase();
fetchStatus();
fetchLogs();
fetchDisk();
setInterval(fetchOverview, 4000);
setInterval(fetchDatabase, 6000);
setInterval(fetchStatus, 2000);
setInterval(fetchLogs, 1000);
setInterval(fetchDisk, 5000);
