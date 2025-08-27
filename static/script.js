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
    downloadStatus.textContent = `Status: ${s.status}${s.mode ? ' • ' + s.mode : ''}`;
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
setInterval(fetchOverview, 4000);
setInterval(fetchDatabase, 6000);
setInterval(fetchStatus, 2000);
setInterval(fetchLogs, 1000);
