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
const startFullCheck = document.getElementById('start-full-check');
const stopDownloadBtn = document.getElementById('stop-download');

const txtFileUpload = document.getElementById('txtFileUpload');
const uploadTxtBtn = document.getElementById('uploadTxtBtn');
const uploadStatus = document.getElementById('uploadStatus');

const directLinkInput = document.getElementById('directLinkInput');
const addLinkBtn = document.getElementById('addLinkBtn');
const linkAddStatus = document.getElementById('linkAddStatus');

const searchQuery = document.getElementById('searchQuery');
const searchBtn = document.getElementById('searchBtn');
const searchStatus = document.getElementById('searchStatus');
const searchResults = document.getElementById('searchResults');

const downloadStatus = document.getElementById('download-status');
// removed current card; info now shown in overview card
const logCount = document.getElementById('log-count');
// Cache for per-season counts to avoid flicker while updating
const countsCache = {};

// Queue elements
const queueBody = document.getElementById('queue-body');
const queueClearBtn = document.getElementById('queue-clear');

function setStartButtonsDisabled(disabled) {
  [startDefault, startNew, startGerman, startMissing, startFullCheck].forEach(btn => {
    if (btn) btn.disabled = !!disabled;
  });
  // Stop-Button zeigen/verstecken
  if (stopDownloadBtn) {
    stopDownloadBtn.style.display = disabled ? 'inline-block' : 'none';
  }
}

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
    // expose to other functions
    window.__status_started_at = s.started_at || null;
    window.__status_anime_started_at = s.anime_started_at || null;
    window.__status_episode_started_at = s.episode_started_at || null;
    window.__status_current_id = s.current_id || null;
    window.__status_current_url = s.current_url || null;
    if (status === 'kein-speicher') {
      downloadStatus.innerHTML = `Status: <span class="badge text-bg-danger">Kein Speicher</span>${s.mode ? ' • ' + s.mode : ''}${s.started_at ? ' • Start: ' + new Date(s.started_at*1000).toLocaleString() : ''}`;
    } else {
      const startedTxt = s.started_at ? ` • Start: ${new Date(s.started_at*1000).toLocaleString()}` : '';
      downloadStatus.textContent = `Status: ${status}${s.mode ? ' • ' + s.mode : ''}${startedTxt}`;
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
  const animeStartedAt = window.__status_anime_started_at ? new Date(window.__status_anime_started_at*1000).toLocaleString() : null;
  const episodeStartedAt = window.__status_episode_started_at ? new Date(window.__status_episode_started_at*1000).toLocaleTimeString() : null;
  const card = document.createElement('div');
    card.className = 'col-12';
    // Include current run meta (index + started_at) if a download is active and matches this item
    const startedAt = animeStartedAt; // per request: here show anime started time
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
              ? `<div class="fw-bold">Lädt runter: ${curIsFilm ? `Film ${curEpisode}` : `Staffel ${curSeason} • Episode ${curEpisode}`} ${episodeStartedAt ? `<span class='small text-secondary'>(Start Ep.: ${episodeStartedAt})</span>` : ''}</div>`
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
        const filmsTxt = typeof counts.films === 'number' && counts.films > 0 ? `${counts.films}` : '0';
        const totalFiles = (counts.total_episodes || 0) + (counts.films || 0);
        const txt = entries.length 
          ? `Dateien: ${totalFiles} (${entries.join(', ')} • Filme: ${filmsTxt})` 
          : (counts.films > 0 ? `Dateien: ${totalFiles} (Filme: ${filmsTxt})` : '');
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
  window.__status_anime_started_at = s.anime_started_at || null;
  window.__status_episode_started_at = s.episode_started_at || null;
  window.__status_current_index = (typeof s.current_index === 'number') ? s.current_index : null;
  window.__status_current_title = s.current_title || null;
  window.__status_status = s.status || null;
  window.__status_current_season = (typeof s.current_season === 'number' || typeof s.current_season === 'string') ? s.current_season : null;
  window.__status_current_episode = (typeof s.current_episode === 'number' || typeof s.current_episode === 'string') ? s.current_episode : null;
  window.__status_current_is_film = !!s.current_is_film;
  window.__status_current_id = s.current_id || null;
  window.__status_current_url = s.current_url || null;
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

/* ---------- Queue ---------- */
async function fetchQueue() {
  try {
    const list = await apiGet('/queue');
    if (!Array.isArray(list)) return;
    queueBody.innerHTML = '';
    list.forEach((q, idx) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${idx + 1}</td><td>${q.anime_id ?? ''}</td><td>${q.title || ''}</td><td><button class="btn btn-sm btn-outline-danger" data-qid="${q.id}">Entfernen</button></td>`;
      queueBody.appendChild(tr);
    });
    // attach remove handlers
    queueBody.querySelectorAll('button[data-qid]').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const qid = e.currentTarget.getAttribute('data-qid');
        if (!qid) return;
        await queueRemove(qid);
      });
    });
  } catch (e) { console.error('fetchQueue', e); }
}

async function queueAdd(animeId) {
  try {
    await apiPost('/queue', { anime_id: animeId });
    await fetchQueue();
  } catch (e) { console.error('queueAdd', e); }
}

async function queueClear() {
  try {
    await fetch('/queue', { method: 'DELETE' });
    await fetchQueue();
  } catch (e) { console.error('queueClear', e); }
}

async function queueRemove(queueId) {
  try {
    await fetch(`/queue?id=${encodeURIComponent(queueId)}`, { method: 'DELETE' });
    await fetchQueue();
  } catch (e) { console.error('queueRemove', e); }
}

/* ---------- Settings (config) ---------- */
const langList = document.getElementById('lang-list');
const minFreeInput = document.getElementById('min-free');
const autostartSelect = document.getElementById('autostart-mode');
const downloadPathInput = document.getElementById('download-path');
const chooseDownloadPathBtn = document.getElementById('choose-download-path');
const storageModeStandard = document.getElementById('storage-mode-standard');
const storageModeSeparate = document.getElementById('storage-mode-separate');
const moviesPathInput = document.getElementById('movies-path');
const seriesPathInput = document.getElementById('series-path');
const animePathInput = document.getElementById('anime-path');
const serienPathInput = document.getElementById('serien-path');
const animeSeparateMoviesChk = document.getElementById('anime-separate-movies');
const serienSeparateMoviesChk = document.getElementById('serien-separate-movies');
const animeMoviesPathInput = document.getElementById('anime-movies-path');
const serienMoviesPathInput = document.getElementById('serien-movies-path');
const chooseMoviesPathBtn = document.getElementById('choose-movies-path');
const chooseSeriesPathBtn = document.getElementById('choose-series-path');
const chooseAnimePathBtn = document.getElementById('choose-anime-path');
const chooseSerienPathBtn = document.getElementById('choose-serien-path');
const chooseAnimeMoviesPathBtn = document.getElementById('choose-anime-movies-path');
const chooseSerienMoviesPathBtn = document.getElementById('choose-serien-movies-path');
const dataFolderPathInput = document.getElementById('data-folder-path');
const chooseDataFolderBtn = document.getElementById('choose-data-folder');
const standardPathContainer = document.getElementById('standard-path-container');
const separatePathsContainer = document.getElementById('separate-paths-container');
const animeMoviesPathContainer = document.getElementById('anime-movies-path-container');
const serienMoviesPathContainer = document.getElementById('serien-movies-path-container');
const saveConfigBtn = document.getElementById('save-config');
const resetConfigBtn = document.getElementById('reset-config');
const refreshTitlesChk = document.getElementById('refresh-titles');

// Toggle path containers based on storage mode
function updateStorageModeVisibility() {
  const mode = storageModeStandard?.checked ? 'standard' : 'separate';
  if (standardPathContainer) {
    standardPathContainer.style.display = (mode === 'standard') ? 'block' : 'none';
  }
  if (separatePathsContainer) {
    separatePathsContainer.style.display = (mode === 'separate') ? 'block' : 'none';
  }
  // Update movie path visibility based on checkboxes
  updateMoviePathVisibility();
}

// Toggle movie path containers based on separate movie checkboxes
function updateMoviePathVisibility() {
  const mode = storageModeStandard?.checked ? 'standard' : 'separate';
  if (mode === 'separate') {
    if (animeMoviesPathContainer) {
      animeMoviesPathContainer.style.display = animeSeparateMoviesChk?.checked ? 'block' : 'none';
    }
    if (serienMoviesPathContainer) {
      serienMoviesPathContainer.style.display = serienSeparateMoviesChk?.checked ? 'block' : 'none';
    }
  } else {
    if (animeMoviesPathContainer) animeMoviesPathContainer.style.display = 'none';
    if (serienMoviesPathContainer) serienMoviesPathContainer.style.display = 'none';
  }
}

// Listen for storage mode changes
if (storageModeStandard) {
  storageModeStandard.addEventListener('change', updateStorageModeVisibility);
}
if (storageModeSeparate) {
  storageModeSeparate.addEventListener('change', updateStorageModeVisibility);
}

// Listen for separate movies checkbox changes
if (animeSeparateMoviesChk) {
  animeSeparateMoviesChk.addEventListener('change', updateMoviePathVisibility);
}
if (serienSeparateMoviesChk) {
  serienSeparateMoviesChk.addEventListener('change', updateMoviePathVisibility);
}

async function fetchConfig() {
  try {
    const cfg = await apiGet('/config');
    renderLangList(cfg.languages || []);
    minFreeInput.value = cfg.min_free_gb ?? '';
    if (autostartSelect) autostartSelect.value = (cfg.autostart_mode ?? '') || '';
    if (downloadPathInput) downloadPathInput.value = cfg.download_path || '';
    const storageMode = cfg.storage_mode || 'standard';
    if (storageModeStandard) storageModeStandard.checked = (storageMode === 'standard');
    if (storageModeSeparate) storageModeSeparate.checked = (storageMode === 'separate');
    if (moviesPathInput) moviesPathInput.value = cfg.movies_path || '';
    if (seriesPathInput) seriesPathInput.value = cfg.series_path || '';
    if (animePathInput) animePathInput.value = cfg.anime_path || '';
    if (serienPathInput) serienPathInput.value = cfg.serien_path || '';
    if (animeSeparateMoviesChk) animeSeparateMoviesChk.checked = !!cfg.anime_separate_movies;
    if (serienSeparateMoviesChk) serienSeparateMoviesChk.checked = !!cfg.serien_separate_movies;
    if (animeMoviesPathInput) animeMoviesPathInput.value = cfg.anime_movies_path || '';
    if (serienMoviesPathInput) serienMoviesPathInput.value = cfg.serien_movies_path || '';
    if (dataFolderPathInput) dataFolderPathInput.value = cfg.data_folder_path || '';
    if (refreshTitlesChk) refreshTitlesChk.checked = !!cfg.refresh_titles;
    updateStorageModeVisibility();
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
  const autostart_mode = autostartSelect ? (autostartSelect.value || null) : null;
  const download_path = downloadPathInput ? downloadPathInput.value.trim() : '';
  const storage_mode = storageModeStandard?.checked ? 'standard' : 'separate';
  const movies_path = moviesPathInput ? moviesPathInput.value.trim() : '';
  const series_path = seriesPathInput ? seriesPathInput.value.trim() : '';
  const anime_path = animePathInput ? animePathInput.value.trim() : '';
  const serien_path = serienPathInput ? serienPathInput.value.trim() : '';
  const anime_separate_movies = animeSeparateMoviesChk ? animeSeparateMoviesChk.checked : false;
  const serien_separate_movies = serienSeparateMoviesChk ? serienSeparateMoviesChk.checked : false;
  const anime_movies_path = animeMoviesPathInput ? animeMoviesPathInput.value.trim() : '';
  const serien_movies_path = serienMoviesPathInput ? serienMoviesPathInput.value.trim() : '';
  const data_folder_path = dataFolderPathInput ? dataFolderPathInput.value.trim() : '';
  
  try {
    const payload = { 
      languages: langs, 
      min_free_gb, 
      autostart_mode,
      storage_mode,
      movies_path,
      series_path,
      anime_path,
      serien_path,
      anime_separate_movies,
      serien_separate_movies,
      anime_movies_path,
      serien_movies_path
    };
    if (download_path) payload.download_path = download_path;
    if (data_folder_path) payload.data_folder_path = data_folder_path;
    if (refreshTitlesChk) payload.refresh_titles = !!refreshTitlesChk.checked;
    const resp = await apiPost('/config', payload);
    // Re-fetch to ensure UI reflects normalized/persisted values
    await fetchConfig();
    if (resp && resp.config) {
      console.log('Config saved:', resp.config);
    }
    if (data_folder_path && resp && resp.status === 'ok') {
      alert('Einstellungen gespeichert. Der Server muss neu gestartet werden, damit der neue Data-Ordner verwendet wird.');
    } else {
      alert('Einstellungen gespeichert');
    }
  } catch(e) { alert('Speichern fehlgeschlagen'); console.error(e); }
}

function resetConfig() {
  fetchConfig();
}

saveConfigBtn?.addEventListener('click', saveConfig);
resetConfigBtn?.addEventListener('click', resetConfig);
chooseDownloadPathBtn?.addEventListener('click', async () => {
  if (!chooseDownloadPathBtn) return;
  chooseDownloadPathBtn.disabled = true;
  try {
    const res = await fetch('/pick_folder');
    const data = await res.json();
    if (data && data.status === 'ok' && data.selected) {
      if (downloadPathInput) downloadPathInput.value = data.selected;
    } else if (data && data.status === 'canceled') {
      // silently ignore
    } else {
      alert('Ordnerauswahl nicht möglich' + (data && data.error ? `: ${data.error}` : ''));
    }
  } catch (e) {
    console.error('pick folder failed', e);
    alert('Ordnerauswahl fehlgeschlagen.');
  } finally {
    chooseDownloadPathBtn.disabled = false;
  }
});

chooseMoviesPathBtn?.addEventListener('click', async () => {
  if (!chooseMoviesPathBtn) return;
  chooseMoviesPathBtn.disabled = true;
  try {
    const res = await fetch('/pick_folder');
    const data = await res.json();
    if (data && data.status === 'ok' && data.selected) {
      if (moviesPathInput) moviesPathInput.value = data.selected;
    } else if (data && data.status === 'canceled') {
      // silently ignore
    } else {
      alert('Ordnerauswahl nicht möglich' + (data && data.error ? `: ${data.error}` : ''));
    }
  } catch (e) {
    console.error('pick folder failed', e);
    alert('Ordnerauswahl fehlgeschlagen.');
  } finally {
    chooseMoviesPathBtn.disabled = false;
  }
});

chooseSeriesPathBtn?.addEventListener('click', async () => {
  if (!chooseSeriesPathBtn) return;
  chooseSeriesPathBtn.disabled = true;
  try {
    const res = await fetch('/pick_folder');
    const data = await res.json();
    if (data && data.status === 'ok' && data.selected) {
      if (seriesPathInput) seriesPathInput.value = data.selected;
    } else if (data && data.status === 'canceled') {
      // silently ignore
    } else {
      alert('Ordnerauswahl nicht möglich' + (data && data.error ? `: ${data.error}` : ''));
    }
  } catch (e) {
    console.error('pick folder failed', e);
    alert('Ordnerauswahl fehlgeschlagen.');
  } finally {
    chooseSeriesPathBtn.disabled = false;
  }
});

chooseAnimePathBtn?.addEventListener('click', async () => {
  if (!chooseAnimePathBtn) return;
  chooseAnimePathBtn.disabled = true;
  try {
    const res = await fetch('/pick_folder');
    const data = await res.json();
    if (data && data.status === 'ok' && data.selected) {
      if (animePathInput) animePathInput.value = data.selected;
    } else if (data && data.status === 'canceled') {
      // silently ignore
    } else {
      alert('Ordnerauswahl nicht möglich' + (data && data.error ? `: ${data.error}` : ''));
    }
  } catch (e) {
    console.error('pick folder failed', e);
    alert('Ordnerauswahl fehlgeschlagen.');
  } finally {
    chooseAnimePathBtn.disabled = false;
  }
});

chooseSerienPathBtn?.addEventListener('click', async () => {
  if (!chooseSerienPathBtn) return;
  chooseSerienPathBtn.disabled = true;
  try {
    const res = await fetch('/pick_folder');
    const data = await res.json();
    if (data && data.status === 'ok' && data.selected) {
      if (serienPathInput) serienPathInput.value = data.selected;
    } else if (data && data.status === 'canceled') {
      // silently ignore
    } else {
      alert('Ordnerauswahl nicht möglich' + (data && data.error ? `: ${data.error}` : ''));
    }
  } catch (e) {
    console.error('pick folder failed', e);
    alert('Ordnerauswahl fehlgeschlagen.');
  } finally {
    chooseSerienPathBtn.disabled = false;
  }
});

chooseAnimeMoviesPathBtn?.addEventListener('click', async () => {
  if (!chooseAnimeMoviesPathBtn) return;
  chooseAnimeMoviesPathBtn.disabled = true;
  try {
    const res = await fetch('/pick_folder');
    const data = await res.json();
    if (data && data.status === 'ok' && data.selected) {
      if (animeMoviesPathInput) animeMoviesPathInput.value = data.selected;
    } else if (data && data.status === 'canceled') {
      // silently ignore
    } else {
      alert('Ordnerauswahl nicht möglich' + (data && data.error ? `: ${data.error}` : ''));
    }
  } catch (e) {
    console.error('pick folder failed', e);
    alert('Ordnerauswahl fehlgeschlagen.');
  } finally {
    chooseAnimeMoviesPathBtn.disabled = false;
  }
});

chooseSerienMoviesPathBtn?.addEventListener('click', async () => {
  if (!chooseSerienMoviesPathBtn) return;
  chooseSerienMoviesPathBtn.disabled = true;
  try {
    const res = await fetch('/pick_folder');
    const data = await res.json();
    if (data && data.status === 'ok' && data.selected) {
      if (serienMoviesPathInput) serienMoviesPathInput.value = data.selected;
    } else if (data && data.status === 'canceled') {
      // silently ignore
    } else {
      alert('Ordnerauswahl nicht möglich' + (data && data.error ? `: ${data.error}` : ''));
    }
  } catch (e) {
    console.error('pick folder failed', e);
    alert('Ordnerauswahl fehlgeschlagen.');
  } finally {
    chooseSerienMoviesPathBtn.disabled = false;
  }
});

chooseDataFolderBtn?.addEventListener('click', async () => {
  if (!chooseDataFolderBtn) return;
  chooseDataFolderBtn.disabled = true;
  try {
    const res = await fetch('/pick_folder');
    const data = await res.json();
    if (data && data.status === 'ok' && data.selected) {
      if (dataFolderPathInput) dataFolderPathInput.value = data.selected;
    } else if (data && data.status === 'canceled') {
      // silently ignore
    } else {
      alert('Ordnerauswahl nicht möglich' + (data && data.error ? `: ${data.error}` : ''));
    }
  } catch (e) {
    console.error('pick folder failed', e);
    alert('Ordnerauswahl fehlgeschlagen.');
  } finally {
    chooseDataFolderBtn.disabled = false;
  }
});

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
      const isDeleted = !!row.deleted;
      tr.innerHTML = `
        <td class="text-secondary">${row.id}</td>
        <td class="break-anywhere">${row.title || ''}</td>
        <td class="break-anywhere"><a href="${row.url}" target="_blank" rel="noreferrer">${row.url}</a></td>
        <td>${row.complete ? "✅" : "❌"}</td>
        <td>${row.deutsch_komplett ? "✅" : "❌"}</td>
        <td>${isDeleted ? "✅" : "❌"}</td>
        <td class="mono small break-anywhere"><div class="cell-scroll">${fehl}</div></td>
        <td class="text-nowrap">${row.last_season || 0}/${row.last_episode || 0}/${row.last_film || 0}</td>
        <td class="d-flex gap-2">
          <button class="btn btn-sm btn-outline-primary" data-queue-id="${row.id}">Als nächstes</button>
          ${isDeleted ? `<button class="btn btn-sm btn-warning" data-restore-id="${row.id}">Wieder herunterladen</button>` : ''}
          <button class="btn btn-sm btn-outline-danger" data-delete-id="${row.id}">Aus Datenbank löschen</button>
        </td>
      `;
      dbBody.appendChild(tr);
    });
    // attach queue buttons
    dbBody.querySelectorAll('button[data-queue-id]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const id = Number(e.currentTarget.getAttribute('data-queue-id'));
        if (id) queueAdd(id);
      });
    });
    // attach restore buttons
    dbBody.querySelectorAll('button[data-restore-id]').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const id = Number(e.currentTarget.getAttribute('data-restore-id'));
        if (!id) return;
        const ok = confirm('Diesen als gelöscht markierten Anime erneut herunterladen?\nDer Status wird zurückgesetzt und er wird der Warteschlange hinzugefügt.');
        if (!ok) return;
        try {
          await fetch('/anime/restore', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, queue: true }) });
          await fetchDatabase();
          await fetchQueue();
        } catch(err) {
          console.error('restore anime failed', err);
          alert('Reaktivieren fehlgeschlagen');
        }
      });
    });
    // attach delete buttons with double confirmation
    dbBody.querySelectorAll('button[data-delete-id]').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const id = Number(e.currentTarget.getAttribute('data-delete-id'));
        if (!id) return;
        const first = confirm('Diesen Eintrag dauerhaft aus der Datenbank löschen?\nDies kann nicht rückgängig gemacht werden.');
        if (!first) return;
        const second = confirm('Sicher? Der Datenbank-Eintrag wird dauerhaft entfernt.');
        if (!second) return;
        try {
          await fetch(`/anime?id=${encodeURIComponent(id)}`, { method: 'DELETE' });
          await fetchDatabase();
        } catch(err) {
          console.error('delete anime failed', err);
          alert('Löschen fehlgeschlagen');
        }
      });
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
      lines.forEach((ln, idx) => {
        const row = document.createElement('div');
        // Default category INFO
        let category = 'INFO';
        let text = ln;
        let tagText = null;
        const m = ln.match(/^\s*\[([^\]]+)\]\s*(.*)$/);
        if (m) {
          tagText = m[1].trim();
          text = m[2] || '';
          const up = tagText.toUpperCase();
          if (up.includes('ERROR') || up.includes('FEHLER')) category = 'ERROR';
          else if (up.includes('WARN')) category = 'WARN';
          else if (up.includes('OK') || up.includes('SUCCESS')) category = 'OK';
          else if (up.includes('DB')) category = 'DB';
          else if (up.includes('CONFIG')) category = 'CONFIG';
          else if (up.includes('SYSTEM')) category = 'SYSTEM';
          else if (up.includes('DEL')) category = 'WARN';
        }
        row.className = 'log-line sev-' + category;
        // line number
        const lnSpan = document.createElement('span');
        lnSpan.className = 'log-ln';
        lnSpan.textContent = String(idx + 1);
        row.appendChild(lnSpan);
        // tag
        if (tagText) {
          const tagSpan = document.createElement('span');
          tagSpan.className = 'log-tag tag-' + category;
          tagSpan.textContent = tagText;
          row.appendChild(tagSpan);
        }
        // text
        const textSpan = document.createElement('span');
        textSpan.className = 'log-text';
        textSpan.textContent = text || (tagText ? '' : ln);
        row.appendChild(textSpan);
        frag.appendChild(row);
      });
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

/* Upload TXT file */
async function uploadTxtFile() {
  const fileInput = txtFileUpload;
  if (!fileInput.files || fileInput.files.length === 0) {
    uploadStatus.textContent = 'Bitte wähle eine Datei aus';
    uploadStatus.className = 'small text-danger';
    return;
  }
  
  const file = fileInput.files[0];
  if (!file.name.endsWith('.txt')) {
    uploadStatus.textContent = 'Nur TXT-Dateien erlaubt';
    uploadStatus.className = 'small text-danger';
    return;
  }
  
  const formData = new FormData();
  formData.append('file', file);
  
  try {
    uploadStatus.textContent = 'Hochladen...';
    uploadStatus.className = 'small text-info';
    uploadTxtBtn.disabled = true;
    
    const res = await fetch('/upload_txt', {
      method: 'POST',
      body: formData
    });
    
    const data = await res.json();
    
    if (res.ok && data.status === 'ok') {
      uploadStatus.textContent = data.msg;
      uploadStatus.className = 'small text-success';
      fileInput.value = ''; // Clear file input
      // Refresh overview and database
      setTimeout(() => {
        fetchOverview();
        fetchDatabase();
        uploadStatus.textContent = '';
      }, 3000);
    } else {
      uploadStatus.textContent = data.msg || 'Upload fehlgeschlagen';
      uploadStatus.className = 'small text-danger';
    }
  } catch (e) {
    console.error('uploadTxtFile', e);
    uploadStatus.textContent = 'Fehler beim Upload';
    uploadStatus.className = 'small text-danger';
  } finally {
    uploadTxtBtn.disabled = false;
  }
}

/* Event listeners */
startDefault.addEventListener('click', () => startDownload('default'));
startNew.addEventListener('click', () => startDownload('new'));
startGerman.addEventListener('click', () => startDownload('german'));
startMissing.addEventListener('click', () => startDownload('check-missing'));
startFullCheck?.addEventListener('click', () => startDownload('full-check'));
uploadTxtBtn?.addEventListener('click', uploadTxtFile);
stopDownloadBtn?.addEventListener('click', stopDownload);
addLinkBtn?.addEventListener('click', addDirectLink);
searchBtn?.addEventListener('click', searchAnime);
// Live-Suche bei Eingabe
searchQuery?.addEventListener('input', handleSearchInput);
// Enter-Taste triggert sofortige Suche
searchQuery?.addEventListener('keyup', (e) => {
  if (e.key === 'Enter') {
    // Lösche Debounce-Timer und suche sofort
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer);
    }
    searchAnime();
  }
});
refreshBtn.addEventListener('click', () => { fetchOverview(); fetchDatabase(); fetchStatus(); });
clearFilter.addEventListener('click', () => { logFilter.value=''; });
dbRefresh.addEventListener('click', fetchDatabase);
dbSearch.addEventListener('keyup', (e) => { if (e.key === 'Enter') fetchDatabase(); });
dbComplete.addEventListener('change', fetchDatabase);
dbDeutsch?.addEventListener('change', fetchDatabase);
dbSort.addEventListener('change', fetchDatabase);
dbOrder.addEventListener('change', fetchDatabase);

/* Stop-Download Funktion */
async function stopDownload() {
  try {
    stopDownloadBtn.disabled = true;
    const res = await fetch('/stop_download', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'}
    });
    const data = await res.json();
    if (res.ok) {
      console.log('Stop-Anforderung gesendet');
    }
  } catch (e) {
    console.error('stopDownload', e);
  } finally {
    stopDownloadBtn.disabled = false;
  }
}

/* Link direkt hinzufügen */
async function addDirectLink() {
  const url = directLinkInput?.value?.trim();
  if (!url) {
    linkAddStatus.textContent = 'Bitte URL eingeben';
    linkAddStatus.className = 'small text-warning';
    return;
  }
  
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    linkAddStatus.textContent = 'Ungültige URL';
    linkAddStatus.className = 'small text-danger';
    return;
  }
  
  try {
    linkAddStatus.textContent = 'Hinzufügen...';
    linkAddStatus.className = 'small text-info';
    addLinkBtn.disabled = true;
    
    const res = await apiPost('/add_link', { url: url });
    
    if (res.status === 'ok') {
      linkAddStatus.textContent = res.msg || 'Erfolgreich hinzugefügt';
      linkAddStatus.className = 'small text-success';
      directLinkInput.value = ''; // Clear input
      // Refresh overview and database
      setTimeout(() => {
        fetchOverview();
        fetchDatabase();
        linkAddStatus.textContent = '';
      }, 3000);
    } else {
      linkAddStatus.textContent = res.msg || 'Fehler beim Hinzufügen';
      linkAddStatus.className = 'small text-danger';
    }
  } catch (e) {
    console.error('addDirectLink', e);
    linkAddStatus.textContent = 'Fehler beim Hinzufügen';
    linkAddStatus.className = 'small text-danger';
  } finally {
    addLinkBtn.disabled = false;
  }
}

/* Anime/Serie suchen */
async function searchAnime(isLiveSearch = false) {
  const query = searchQuery?.value?.trim();
  
  if (!query) {
    searchResults.innerHTML = '';
    searchResults.style.display = 'none';
    searchStatus.textContent = '';
    return;
  }
  
  try {
    searchStatus.textContent = 'Durchsuche AniWorld.to + S.to...';
    searchStatus.className = 'small text-info';
    searchBtn.disabled = true;
    searchResults.innerHTML = '<div class="text-center p-3"><div class="spinner-border spinner-border-sm text-primary" role="status"></div> Suche läuft...</div>';
    searchResults.style.display = 'block';
    
    const res = await apiPost('/search', { query: query });
    
    if (res.status === 'ok') {
      displaySearchResults(res.results || [], isLiveSearch);
      const totalText = isLiveSearch && res.count > 5 ? ` (Top 5 von ${res.count})` : '';
      searchStatus.textContent = `${res.count || 0} Ergebnis(se) gefunden${totalText}`;
      searchStatus.className = 'small text-success';
      setTimeout(() => {
        searchStatus.textContent = '';
      }, 5000);
    } else {
      searchStatus.textContent = res.msg || 'Suche fehlgeschlagen';
      searchStatus.className = 'small text-danger';
      searchResults.style.display = 'none';
    }
  } catch (e) {
    console.error('searchAnime', e);
    searchStatus.textContent = 'Fehler bei der Suche';
    searchStatus.className = 'small text-danger';
    searchResults.style.display = 'none';
  } finally {
    searchBtn.disabled = false;
  }
}

/* Live-Suche mit Debounce */
let searchDebounceTimer = null;

function handleSearchInput() {
  const query = searchQuery?.value?.trim();
  
  // Lösche vorherigen Timer
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer);
  }
  
  // Leere Eingabe oder zu kurz = keine Suche
  if (!query || query.length < 2) {
    searchResults.innerHTML = '';
    searchResults.style.display = 'none';
    searchStatus.textContent = '';
    return;
  }
  
  // Setze neuen Timer für 300ms (schnellere Echtzeit-Suche)
  searchDebounceTimer = setTimeout(() => {
    searchAnime(true); // true = Live-Suche (limitiert auf Top-5)
  }, 300);
}

function displaySearchResults(results, limitToFive = false) {
  searchResults.innerHTML = '';
  
  if (!results || results.length === 0) {
    searchResults.innerHTML = '<div class="search-no-results">Keine Ergebnisse gefunden</div>';
    searchResults.style.display = 'block';
    return;
  }
  
  const fragment = document.createDocumentFragment();
  
  // Zeige maximal 5 Ergebnisse bei Live-Suche, sonst alle
  const displayResults = limitToFive ? results.slice(0, 5) : results;
  
  displayResults.forEach(result => {
    const item = document.createElement('div');
    item.className = 'search-result-item';
    
    // Cover-Bild hinzufügen falls vorhanden
    if (result.cover) {
      const coverImg = document.createElement('img');
      coverImg.className = 'search-result-cover';
      coverImg.src = result.cover;
      coverImg.alt = result.name + ' Cover';
      coverImg.onerror = () => { coverImg.style.display = 'none'; }; // Verstecke bei Fehler
      item.appendChild(coverImg);
    }
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'search-result-content';
    
    const title = document.createElement('div');
    title.className = 'search-result-title';
    title.textContent = result.title;
    
    // Provider Badge hinzufügen
    if (result.provider) {
      const badge = document.createElement('span');
      badge.className = result.provider === 'aniworld' ? 'badge bg-primary ms-2' : 'badge bg-success ms-2';
      badge.textContent = result.provider === 'aniworld' ? 'AniWorld' : 'S.to';
      badge.style.fontSize = '0.7rem';
      title.appendChild(badge);
    }
    
    const url = document.createElement('div');
    url.className = 'search-result-url small text-muted';
    url.textContent = result.url;
    
    const btnContainer = document.createElement('div');
    btnContainer.className = 'search-result-actions';
    
    const addBtn = document.createElement('button');
    addBtn.className = 'btn btn-sm btn-primary';
    addBtn.textContent = '➕ Hinzufügen';
    addBtn.onclick = () => addSearchResult(result.url, result.title);
    
    const copyBtn = document.createElement('button');
    copyBtn.className = 'btn btn-sm btn-outline-secondary';
    copyBtn.textContent = '📋 URL kopieren';
    copyBtn.onclick = () => copyToClipboard(result.url);
    
    btnContainer.appendChild(addBtn);
    btnContainer.appendChild(copyBtn);
    
    contentDiv.appendChild(title);
    contentDiv.appendChild(url);
    contentDiv.appendChild(btnContainer);
    
    item.appendChild(contentDiv);
    
    fragment.appendChild(item);
  });
  
  searchResults.appendChild(fragment);
  searchResults.style.display = 'block';
}

async function addSearchResult(url, title) {
  try {
    const res = await apiPost('/add_link', { url: url });
    if (res.status === 'ok') {
      searchStatus.textContent = `"${title}" erfolgreich hinzugefügt`;
      searchStatus.className = 'small text-success';
      fetchOverview();
      fetchDatabase();
      setTimeout(() => {
        searchStatus.textContent = '';
      }, 3000);
    } else {
      searchStatus.textContent = res.msg || 'Fehler beim Hinzufügen';
      searchStatus.className = 'small text-danger';
    }
  } catch (e) {
    console.error('addSearchResult', e);
    searchStatus.textContent = 'Fehler beim Hinzufügen';
    searchStatus.className = 'small text-danger';
  }
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    searchStatus.textContent = 'URL in Zwischenablage kopiert';
    searchStatus.className = 'small text-success';
    setTimeout(() => {
      searchStatus.textContent = '';
    }, 2000);
  }).catch(e => {
    console.error('copyToClipboard', e);
    searchStatus.textContent = 'Kopieren fehlgeschlagen';
    searchStatus.className = 'small text-danger';
  });
}

/* start polling */
fetchOverview();
fetchDatabase();
fetchStatus();
fetchLogs();
fetchDisk();
fetchQueue();
// Staggered polling: each runs regularly with offsets between starts
const INTERVAL_MS = 5000; // 5 Sekunden (war vorher 60s)
const STAGGER_MS = 1000; // 1 Sekunde zwischen den verschiedenen Abfragen
function scheduleStaggered(fn, offsetMs) {
  setTimeout(() => {
    try { fn(); } catch(e) { console.error(e); }
    setInterval(fn, INTERVAL_MS);
  }, offsetMs);
}
scheduleStaggered(fetchOverview, 0);
scheduleStaggered(fetchDatabase, STAGGER_MS);
scheduleStaggered(fetchStatus, STAGGER_MS * 2);
scheduleStaggered(fetchLogs, STAGGER_MS * 3);
scheduleStaggered(fetchDisk, STAGGER_MS * 4);
scheduleStaggered(fetchQueue, STAGGER_MS * 5);

// Logs toolbar actions
copyLogsBtn?.addEventListener('click', async () => {
  try {
    const text = Array.isArray(lastLogs) && lastLogs.length ? lastLogs.join('\n') : (logBox.textContent || '');
    await navigator.clipboard.writeText(text);
  } catch (e) {
    console.error('copy logs failed', e);
  }
});

queueClearBtn?.addEventListener('click', queueClear);
