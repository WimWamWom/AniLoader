/* AniLoader – Minimales JavaScript */

const API = '';  // Relativer Pfad (same origin)

// ──────────────────────── Hilfsfunktionen ────────────────────────

async function api(path, opts = {}) {
  const url = `${API}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  });
  return res.json();
}

function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }

// ──────────────────────── Tab-Steuerung ────────────────────────

function initTabs() {
  $$('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      $$('.tab-btn').forEach(b => b.classList.remove('active'));
      $$('.tab-content').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      $(`#${btn.dataset.tab}`).classList.add('active');

      // Tab-spezifisches Laden
      if (btn.dataset.tab === 'tab-db') loadDatabase();
      if (btn.dataset.tab === 'tab-settings') loadSettings();
    });
  });
}

// ──────────────────────── Download Tab ────────────────────────

let statusInterval = null;

async function refreshStatus() {
  try {
    const s = await api('/status');
    const badge = $('#status-badge');
    badge.textContent = s.status;
    badge.className = 'status-badge badge-' + s.status;

    $('#dl-mode').textContent = s.mode || '–';
    $('#dl-title').textContent = s.current_title || '–';
    $('#dl-season').textContent = s.current_season != null ? `S${String(s.current_season).padStart(2,'0')}` : '–';
    $('#dl-episode').textContent = s.current_episode != null ? `E${String(s.current_episode).padStart(3,'0')}` : '–';
    $('#dl-started').textContent = s.started_at || '–';

    const p = s.progress || {};
    $('#prog-series').textContent = `${p.current_series_index || 0}/${p.total_series || 0}`;
    $('#prog-downloaded').textContent = p.downloaded_episodes || 0;
    $('#prog-skipped').textContent = p.skipped_episodes || 0;
    $('#prog-failed').textContent = p.failed_episodes || 0;

    // Buttons
    const isRunning = s.status === 'running' || s.status === 'stopping';
    $$('.btn-start').forEach(b => b.disabled = isRunning);
    $('#btn-stop').disabled = !isRunning || s.status === 'stopping';

  } catch (e) {
    console.error('Status refresh error:', e);
  }
}

async function startDownload(mode) {
  await api('/start_download', {
    method: 'POST',
    body: JSON.stringify({ mode }),
  });
  refreshStatus();
}

async function stopDownload() {
  await api('/stop_download', { method: 'POST' });
  refreshStatus();
}

async function refreshLog() {
  try {
    const data = await api('/last_run');
    const el = $('#log-output');
    el.textContent = data.log || '';
    el.scrollTop = el.scrollHeight;
  } catch (e) { /* ignore */ }
}

// ──────────────────────── Hinzufügen Tab ────────────────────────

async function addLink() {
  const input = $('#add-url');
  const url = input.value.trim();
  if (!url) return;

  try {
    const res = await api('/add_link', {
      method: 'POST',
      body: JSON.stringify({ url }),
    });
    input.value = '';
    showMsg('#add-msg', res.title ? `Hinzugefügt: ${res.title}` : 'Hinzugefügt', 'success');
  } catch (e) {
    showMsg('#add-msg', 'Fehler beim Hinzufügen', 'danger');
  }
}

async function uploadTxt() {
  const input = $('#file-input');
  if (!input.files.length) return;

  const form = new FormData();
  form.append('file', input.files[0]);

  try {
    const res = await fetch('/upload_txt', { method: 'POST', body: form });
    const data = await res.json();
    showMsg('#upload-msg', `${data.added} Einträge importiert`, 'success');
    input.value = '';
  } catch (e) {
    showMsg('#upload-msg', 'Upload fehlgeschlagen', 'danger');
  }
}

async function searchAnime() {
  const query = $('#search-query').value.trim();
  const platform = $('#search-platform').value;
  if (!query) return;

  $('#search-results').innerHTML = '<p>Suche...</p>';

  try {
    const data = await api('/search', {
      method: 'POST',
      body: JSON.stringify({ query, platform }),
    });
    renderSearchResults(data.results || []);
  } catch (e) {
    $('#search-results').innerHTML = '<p>Suche fehlgeschlagen</p>';
  }
}

function renderSearchResults(results) {
  const container = $('#search-results');
  if (!results.length) {
    container.innerHTML = '<p>Keine Ergebnisse</p>';
    return;
  }

  container.innerHTML = results.map(r => `
    <div class="search-result">
      <div class="info">
        <span class="title">${esc(r.title)}</span>
        <span class="platform">${esc(r.platform)}</span>
        ${r.description ? `<br><small style="color:var(--text-muted)">${esc(r.description).slice(0,120)}</small>` : ''}
      </div>
      <button class="btn btn-primary btn-sm" onclick="addFromSearch('${esc(r.url)}')">+ Hinzufügen</button>
    </div>
  `).join('');
}

async function addFromSearch(url) {
  try {
    const res = await api('/add_link', {
      method: 'POST',
      body: JSON.stringify({ url }),
    });
    showMsg('#search-msg', res.title ? `Hinzugefügt: ${res.title}` : 'Hinzugefügt', 'success');
  } catch (e) {
    showMsg('#search-msg', 'Fehler', 'danger');
  }
}

// ──────────────────────── Datenbank Tab ────────────────────────

let dbSortCol = 'id';
let dbSortDir = 'ASC';

async function loadDatabase() {
  const showDeleted = $('#db-show-deleted')?.checked || false;
  const search = $('#db-search')?.value || '';

  try {
    const data = await api(`/database?sort=${dbSortCol}&dir=${dbSortDir}&include_deleted=${showDeleted}&q=${encodeURIComponent(search)}`);
    renderDatabase(data);
  } catch (e) {
    console.error('DB load error:', e);
  }
}

function renderDatabase(entries) {
  const tbody = $('#db-tbody');
  if (!entries.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center">Keine Einträge</td></tr>';
    return;
  }

  tbody.innerHTML = entries.map(e => {
    const statusClass = e.deleted ? 'ind-deleted' : e.complete ? 'ind-complete' : 'ind-incomplete';
    const statusText = e.deleted ? 'Gelöscht' : e.complete ? 'Komplett' : 'Inkomplett';
    const germanIcon = e.deutsch_komplett ? '✔' : '✘';
    const progress = e.last_season ? `S${String(e.last_season).padStart(2,'0')}E${String(e.last_episode).padStart(3,'0')}` : '–';
    const platform = e.url.includes('aniworld.to') ? 'AW' : 'S.to';

    return `<tr>
      <td>${e.id}</td>
      <td><span class="indicator ${statusClass}"></span>${statusText}</td>
      <td>${esc(e.title || '–')}</td>
      <td><small>${platform}</small></td>
      <td>${germanIcon}</td>
      <td>${progress}</td>
      <td>${e.last_film || 0} Filme</td>
      <td>
        ${e.deleted
          ? `<button class="btn btn-success btn-sm" onclick="restoreAnime(${e.id})">↩</button>`
          : `<button class="btn btn-danger btn-sm" onclick="deleteAnime(${e.id})">✕</button>`
        }
      </td>
    </tr>`;
  }).join('');
}

function sortDb(col) {
  if (dbSortCol === col) {
    dbSortDir = dbSortDir === 'ASC' ? 'DESC' : 'ASC';
  } else {
    dbSortCol = col;
    dbSortDir = 'ASC';
  }
  loadDatabase();
}

async function deleteAnime(id) {
  if (!confirm('Eintrag wirklich löschen?')) return;
  await api(`/anime/${id}`, { method: 'DELETE' });
  loadDatabase();
}

async function restoreAnime(id) {
  await api(`/anime/${id}/restore`, { method: 'POST' });
  loadDatabase();
}

// ──────────────────────── Einstellungen Tab ────────────────────────

let currentConfig = {};

async function loadSettings() {
  try {
    currentConfig = await api('/config');
    renderSettings(currentConfig);
  } catch (e) {
    console.error('Config load error:', e);
  }
}

function renderSettings(cfg) {
  // Server
  $('#cfg-port').value = cfg.server?.port || 5050;

  // Storage
  $('#cfg-storage-mode').value = cfg.storage?.mode || 'standard';
  $('#cfg-download-path').value = cfg.storage?.download_path || '';
  $('#cfg-anime-path').value = cfg.storage?.anime_path || '';
  $('#cfg-series-path').value = cfg.storage?.series_path || '';
  $('#cfg-anime-movies-path').value = cfg.storage?.anime_movies_path || '';
  $('#cfg-serien-movies-path').value = cfg.storage?.serien_movies_path || '';
  $('#cfg-anime-sep-movies').checked = cfg.storage?.anime_separate_movies || false;
  $('#cfg-serien-sep-movies').checked = cfg.storage?.serien_separate_movies || false;

  // Download
  $('#cfg-min-free').value = cfg.download?.min_free_gb || 2.0;
  $('#cfg-timeout').value = cfg.download?.timeout_seconds || 900;
  $('#cfg-autostart').value = cfg.download?.autostart_mode || '';

  // Storage mode visibility
  toggleStoragePaths();

  // Languages (sortable)
  renderLanguages(cfg.languages || []);
}

function toggleStoragePaths() {
  const mode = $('#cfg-storage-mode').value;
  const sep = $('#separate-paths');
  if (sep) sep.style.display = mode === 'separate' ? 'block' : 'none';
}

function renderLanguages(langs) {
  const list = $('#lang-list');
  list.innerHTML = langs.map((l, i) => `
    <li class="lang-item" draggable="true" data-index="${i}">
      <span class="grip">☰</span>
      <span>${i + 1}. ${l}</span>
    </li>
  `).join('');

  // Drag & Drop
  let dragIdx = null;
  list.querySelectorAll('.lang-item').forEach(item => {
    item.addEventListener('dragstart', e => {
      dragIdx = parseInt(e.target.dataset.index);
      e.target.style.opacity = '0.5';
    });
    item.addEventListener('dragend', e => {
      e.target.style.opacity = '1';
    });
    item.addEventListener('dragover', e => e.preventDefault());
    item.addEventListener('drop', e => {
      e.preventDefault();
      const dropIdx = parseInt(e.target.closest('.lang-item')?.dataset.index);
      if (dragIdx !== null && dropIdx !== undefined && dragIdx !== dropIdx) {
        const arr = [...currentConfig.languages];
        const [moved] = arr.splice(dragIdx, 1);
        arr.splice(dropIdx, 0, moved);
        currentConfig.languages = arr;
        renderLanguages(arr);
      }
    });
  });
}

async function saveSettings() {
  const cfg = {
    server: {
      port: parseInt($('#cfg-port').value) || 5050,
    },
    languages: currentConfig.languages || [],
    storage: {
      mode: $('#cfg-storage-mode').value,
      download_path: $('#cfg-download-path').value,
      anime_path: $('#cfg-anime-path').value,
      series_path: $('#cfg-series-path').value,
      anime_movies_path: $('#cfg-anime-movies-path').value,
      serien_movies_path: $('#cfg-serien-movies-path').value,
      anime_separate_movies: $('#cfg-anime-sep-movies').checked,
      serien_separate_movies: $('#cfg-serien-sep-movies').checked,
    },
    download: {
      min_free_gb: parseFloat($('#cfg-min-free').value) || 2.0,
      timeout_seconds: parseInt($('#cfg-timeout').value) || 900,
      autostart_mode: $('#cfg-autostart').value || null,
    },
    data: currentConfig.data || {},
  };

  try {
    const res = await api('/config', {
      method: 'POST',
      body: JSON.stringify(cfg),
    });
    if (res.status === 'ok') {
      showMsg('#settings-msg', 'Einstellungen gespeichert', 'success');
      currentConfig = cfg;
    } else {
      showMsg('#settings-msg', `Fehler: ${(res.errors||[]).join(', ')}`, 'danger');
    }
  } catch (e) {
    showMsg('#settings-msg', 'Speichern fehlgeschlagen', 'danger');
  }
}

// ──────────────────────── Hilfsfunktionen ────────────────────────

function esc(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}

function showMsg(sel, text, type) {
  const el = $(sel);
  if (!el) return;
  el.textContent = text;
  el.style.color = type === 'success' ? 'var(--success)' : 'var(--danger)';
  el.style.display = 'block';
  setTimeout(() => { el.style.display = 'none'; }, 4000);
}

// ──────────────────────── Upload Drag & Drop ────────────────────────

function initUpload() {
  const area = $('#upload-area');
  const input = $('#file-input');
  if (!area) return;

  area.addEventListener('click', () => input.click());
  area.addEventListener('dragover', e => { e.preventDefault(); area.classList.add('dragover'); });
  area.addEventListener('dragleave', () => area.classList.remove('dragover'));
  area.addEventListener('drop', e => {
    e.preventDefault();
    area.classList.remove('dragover');
    input.files = e.dataTransfer.files;
    uploadTxt();
  });
}

// ──────────────────────── Init ────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initUpload();

  // Status-Polling
  refreshStatus();
  statusInterval = setInterval(refreshStatus, 5000);

  // Log-Polling
  setInterval(refreshLog, 8000);

  // Disk Info
  api('/disk').then(d => {
    const el = $('#disk-info');
    if (el && d.free_gb !== undefined) {
      el.textContent = `${d.free_gb} GB frei`;
    }
  });

  // Enter-Key für Suche
  $('#search-query')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') searchAnime();
  });
  $('#add-url')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') addLink();
  });
});
