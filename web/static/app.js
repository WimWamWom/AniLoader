/* AniLoader – Professional Dynamic UI */

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
      // Smooth tab transition
      const activeTab = $('.tab-content.active');
      if (activeTab) {
        activeTab.style.opacity = '0';
        activeTab.style.transform = 'translateY(4px)';
        setTimeout(() => {
          activeTab.classList.remove('active');
          activeTab.style.opacity = '';
          activeTab.style.transform = '';
          btn.classList.add('active');
          const newTab = $(`#${btn.dataset.tab}`);
          newTab.classList.add('active');
          // Tab-spezifisches Laden
          if (btn.dataset.tab === 'tab-db') loadDatabase();
          if (btn.dataset.tab === 'tab-settings') loadSettings();
          if (btn.dataset.tab === 'tab-logs') {
            refreshFullLog();
            loadArchivedLogs();
            loadLogSettings();
          }
        }, 120);
      } else {
        btn.classList.add('active');
        $(`#${btn.dataset.tab}`).classList.add('active');
      }
    });
  });
}

// ──────────────────────── Download Tab ────────────────────────

let statusInterval = null;

async function refreshStatus() {
  try {
    const s = await api('/status');
    const badge = $('#status-badge');
    const newClass = 'status-badge badge-' + s.status;
    if (badge.className !== newClass) {
      badge.textContent = s.status;
      badge.className = newClass;
      badge.style.animation = 'none';
      badge.offsetHeight;
      badge.style.animation = 'fadeIn 0.3s ease-out';
    }

    updateText('#dl-mode', s.mode || '–');
    updateText('#dl-title', s.current_title || '–');
    updateText('#dl-season', s.current_season != null ? `S${String(s.current_season).padStart(2,'0')}` : '–');
    updateText('#dl-episode', s.current_episode != null ? `E${String(s.current_episode).padStart(3,'0')}` : '–');
    updateText('#dl-started', s.started_at || '–');

    const p = s.progress || {};
    updateText('#prog-series', `${p.current_series_index || 0}/${p.total_series || 0}`);
    updateText('#prog-downloaded', p.downloaded_episodes || 0);
    updateText('#prog-skipped', p.skipped_episodes || 0);
    updateText('#prog-failed', p.failed_episodes || 0);

    // Buttons
    const isRunning = s.status === 'running' || s.status === 'stopping';
    $$('.btn-start').forEach(b => b.disabled = isRunning);
    $('#btn-stop').disabled = !isRunning || s.status === 'stopping';

  } catch (e) {
    console.error('Status refresh error:', e);
  }
}

// Smooth text update – only update DOM if value changed, with subtle flash
function updateText(sel, value) {
  const el = $(sel);
  if (!el) return;
  const str = String(value);
  if (el.textContent !== str) {
    el.textContent = str;
    el.style.animation = 'none';
    el.offsetHeight;
    el.style.animation = 'fadeIn 0.25s ease-out';
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
    const el = $('#log-output-mini');
    if (el) {
      const lines = (data.log || '').trim().split('\n');
      el.textContent = lines.slice(-15).join('\n');
      el.scrollTop = el.scrollHeight;
    }
  } catch (e) { /* ignore */ }
}

// ──────────────────────── Logs Tab ────────────────────────

let logLevel = 'all';       // 'all' | 'error' | 'warn' | 'ok' | 'dl'
let rawLogText = '';
let logAutoRefreshInterval = null;

// Tag → CSS-Klasse Mapping
const TAG_CLASSES = {
  'OK': 'tag-ok', 'DONE': 'tag-done', 'DL': 'tag-dl', 'CMD': 'tag-cmd',
  'SKIP': 'tag-skip', 'WARN': 'tag-warn', 'ERROR': 'tag-error', 'FATAL': 'tag-fatal',
  'FAIL': 'tag-fail', 'SERVER': 'tag-server', 'DB': 'tag-db', 'DB-ERROR': 'tag-error',
  'CONFIG': 'tag-config', 'CONFIG-WARN': 'tag-warn', 'IMPORT': 'tag-import',
  'SCRAPER': 'tag-scraper', 'MODE': 'tag-mode', 'START': 'tag-start',
  'STOP': 'tag-stop', 'SERIE': 'tag-serie', 'NEW': 'tag-new',
  'CHECK': 'tag-check', 'GERMAN': 'tag-german', 'ANIWORLD': 'tag-aniworld',
  'ANIWORLD-ERR': 'tag-error', 'AUTOSTART': 'tag-start', 'SUCHE': 'tag-scraper',
  'LOG-ERROR': 'tag-error',
};

// Tag → Level-Gruppe (für Filter)
const TAG_TO_LEVEL = {
  'ERROR': 'error', 'FATAL': 'error', 'FAIL': 'error',
  'DB-ERROR': 'error', 'ANIWORLD-ERR': 'error', 'LOG-ERROR': 'error',
  'CONFIG-WARN': 'error',
  'WARN': 'warn',
  'OK': 'ok', 'DONE': 'ok', 'START': 'ok', 'NEW': 'ok',
  'DL': 'dl', 'CMD': 'dl', 'ANIWORLD': 'dl',
};

function parseLogLine(line) {
  // Format: [2025-03-02 14:30:00] [TAG] message
  const m = line.match(/^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*\[([^\]]+)\]\s*(.*)$/);
  if (m) {
    return { timestamp: m[1], tag: m[2], message: m[3], raw: line };
  }
  // Separator lines (═══ or ───)
  if (/^[\[?\d].*[═─]{5,}/.test(line) || /^[═─]{5,}/.test(line)) {
    const m2 = line.match(/^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*(.*)$/);
    if (m2) {
      return { timestamp: m2[1], tag: null, message: m2[2], raw: line, isSeparator: true };
    }
    return { timestamp: null, tag: null, message: line, raw: line, isSeparator: true };
  }
  // Timestamp but no tag
  const m3 = line.match(/^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*(.*)$/);
  if (m3) {
    return { timestamp: m3[1], tag: null, message: m3[2], raw: line };
  }
  return { timestamp: null, tag: null, message: line, raw: line };
}

function matchesLevel(tag, level) {
  if (level === 'all') return true;
  if (!tag) return level === 'all';
  const tagLevel = TAG_TO_LEVEL[tag.toUpperCase()] || 'all';
  return tagLevel === level;
}

function renderFormattedLog() {
  const container = $('#log-output-full');
  if (!container) return;

  const filterText = ($('#log-filter')?.value || '').toLowerCase();
  const lines = rawLogText.trim().split('\n').filter(l => l.trim());

  if (!lines.length || (lines.length === 1 && !lines[0].trim())) {
    container.innerHTML = '<span style="color:#666">Keine Logs vorhanden.</span>';
    updateLogStats([]);
    return;
  }

  const parsed = lines.map(parseLogLine);

  // Filter
  const filtered = parsed.filter(p => {
    // Level filter
    if (logLevel !== 'all' && !matchesLevel(p.tag, logLevel) && !p.isSeparator) return false;
    // Text filter
    if (filterText && !p.raw.toLowerCase().includes(filterText)) return false;
    return true;
  });

  // Render
  const html = filtered.map(p => {
    if (p.isSeparator) {
      return `<div class="log-line log-separator">${escH(p.raw)}</div>`;
    }

    const ts = p.timestamp
      ? `<span class="log-ts">${escH(p.timestamp)}</span>`
      : '';

    let tagHtml = '';
    if (p.tag) {
      const cls = TAG_CLASSES[p.tag.toUpperCase()] || TAG_CLASSES[p.tag.split('-')[0]?.toUpperCase()] || 'tag-default';
      tagHtml = `<span class="log-tag ${cls}">${escH(p.tag)}</span>`;
    }

    const msg = highlightMessage(p.message || '', p.tag);

    return `<div class="log-line">${ts}${tagHtml}<span class="log-msg">${msg}</span></div>`;
  }).join('');

  container.innerHTML = html || '<span style="color:#666">Keine passenden Eintr\u00e4ge.</span>';

  // Auto-scroll
  if ($('#log-autoscroll')?.checked) {
    container.scrollTop = container.scrollHeight;
  }

  updateLogStats(parsed);
}

function highlightMessage(msg, tag) {
  let s = escH(msg);
  // Season/Episode Nummern hervorheben
  s = s.replace(/(S\d{2}E\d{3})/g, '<strong style="color:var(--primary)">$1</strong>');
  // URLs erkennen
  s = s.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" style="color:var(--primary);text-decoration:underline;">$1</a>');
  // Dateinamen (.mkv, .mp4)
  s = s.replace(/([^\s<]+\.(mkv|mp4|txt))/gi, '<span style="color:#aaf">$1</span>');
  return s;
}

function updateLogStats(parsed) {
  const stats = $('#log-stats');
  if (!stats) return;

  let errors = 0, warns = 0, oks = 0, dls = 0, total = parsed.length;
  for (const p of parsed) {
    if (!p.tag) continue;
    const lv = TAG_TO_LEVEL[p.tag.toUpperCase()];
    if (lv === 'error') errors++;
    else if (lv === 'warn') warns++;
    else if (lv === 'ok') oks++;
    else if (lv === 'dl') dls++;
  }

  stats.innerHTML = `
    <span class="log-stat-item"><span class="log-stat-dot" style="background:var(--text-muted)"></span> ${total} Zeilen</span>
    <span class="log-stat-item"><span class="log-stat-dot" style="background:var(--success)"></span> ${oks} Erfolg</span>
    <span class="log-stat-item"><span class="log-stat-dot" style="background:var(--primary)"></span> ${dls} Downloads</span>
    <span class="log-stat-item"><span class="log-stat-dot" style="background:var(--warning)"></span> ${warns} Warnungen</span>
    <span class="log-stat-item"><span class="log-stat-dot" style="background:var(--danger)"></span> ${errors} Fehler</span>
  `;
}

function setLogLevel(level) {
  logLevel = level;
  $$('.log-level-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.level === level);
  });
  renderFormattedLog();
}

async function refreshFullLog() {
  try {
    const data = await api('/last_run');
    rawLogText = data.log || '';
    renderFormattedLog();
  } catch (e) {
    const container = $('#log-output-full');
    if (container) container.innerHTML = '<span style="color:var(--danger)">Logs konnten nicht geladen werden.</span>';
  }
}

function toggleLogAutoRefresh() {
  const enabled = $('#log-auto-refresh')?.checked;
  if (enabled && !logAutoRefreshInterval) {
    logAutoRefreshInterval = setInterval(refreshFullLog, 8000);
  } else if (!enabled && logAutoRefreshInterval) {
    clearInterval(logAutoRefreshInterval);
    logAutoRefreshInterval = null;
  }
}

function copyLogToClipboard(btn) {
  if (!rawLogText.trim()) {
    alert('Kein Log zum Kopieren verfügbar.');
    return;
  }
  
  navigator.clipboard.writeText(rawLogText).then(() => {
    // Feedback geben
    const originalText = btn.textContent;
    btn.textContent = '✓ Kopiert!';
    btn.style.backgroundColor = 'var(--success)';
    
    setTimeout(() => {
      btn.textContent = originalText;
      btn.style.backgroundColor = '';
    }, 2000);
  }).catch(err => {
    console.error('Fehler beim Kopieren:', err);
    alert('Fehler beim Kopieren in die Zwischenablage.');
  });
}

// ──────────────────────── Archivierte Logs ────────────────────────

async function loadArchivedLogs() {
  try {
    const data = await api('/archived_logs');
    const selector = $('#log-selector');
    if (!selector) return;

    // Aktuelle Option beibehalten
    const currentValue = selector.value;
    
    // Dropdown leeren und neu befüllen
    selector.innerHTML = '<option value="current">Aktueller Lauf (last_run.txt)</option>';
    
    if (data.archived_logs && data.archived_logs.length > 0) {
      data.archived_logs.forEach(log => {
        const option = document.createElement('option');
        option.value = log.filename;
        const date = new Date(log.timestamp * 1000).toLocaleString('de-DE');
        const sizeMB = (log.size / 1024 / 1024).toFixed(1);
        option.textContent = `${log.filename} (${date} - ${sizeMB} MB)`;
        selector.appendChild(option);
      });
    }
    
    // Vorherige Auswahl wiederherstellen (falls noch vorhanden)
    if (currentValue && Array.from(selector.options).some(opt => opt.value === currentValue)) {
      selector.value = currentValue;
    }
  } catch (e) {
    console.error('Fehler beim Laden der archivierten Logs:', e);
  }
}

async function loadSelectedLog() {
  const selector = $('#log-selector');
  if (!selector) return;
  
  const selectedLog = selector.value;
  
  try {
    if (selectedLog === 'current') {
      // Aktueller Log
      await refreshFullLog();
    } else {
      // Archivierter Log
      const data = await api(`/archived_logs/${encodeURIComponent(selectedLog)}`);
      rawLogText = data.content || '';
      renderFormattedLog();
      
      // Auto-Refresh deaktivieren für archivierte Logs
      const autoRefresh = $('#log-auto-refresh');
      if (autoRefresh && autoRefresh.checked) {
        autoRefresh.checked = false;
        toggleLogAutoRefresh();
      }
    }
  } catch (e) {
    const container = $('#log-output-full');
    if (container) {
      container.innerHTML = '<span style="color:var(--danger)">Log konnte nicht geladen werden: ' + e.message + '</span>';
    }
  }
}

async function loadLogSettings() {
  try {
    const cfg = await api('/config');
    $('#cfg-log-retention-days').value = cfg.logging?.log_retention_days || 7;
  } catch (e) {
    console.error('Fehler beim Laden der Log-Einstellungen:', e);
  }
}

async function saveLogSettings() {
  try {
    // Aktuelle Konfiguration laden
    const cfg = await api('/config');
    
    // Nur den Logging-Teil aktualisieren
    cfg.logging = cfg.logging || {};
    cfg.logging.log_retention_days = parseInt($('#cfg-log-retention-days').value) || 7;
    
    // Speichern
    const res = await api('/config', {
      method: 'POST',
      body: JSON.stringify(cfg),
    });
    
    if (res.status === 'ok') {
      // Temporäre Erfolgsmeldung neben dem Speichern-Button anzeigen
      const btn = document.querySelector('button[onclick="saveLogSettings()"]');
      const originalText = btn.textContent;
      btn.textContent = '✓ Gespeichert';
      btn.style.background = 'var(--success)';
      setTimeout(() => {
        btn.textContent = originalText;
        btn.style.background = '';
      }, 2000);
    } else {
      alert('Fehler beim Speichern: ' + (res.errors || []).join(', '));
    }
  } catch (e) {
    alert('Speichern fehlgeschlagen: ' + e.message);
  }
}

function escH(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
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

async function searchAnime(limit) {
  const query = $('#search-query').value.trim();
  const platform = $('#search-platform').value;
  if (!query) { $('#search-results').innerHTML = ''; return; }

  if (!limit) $('#search-results').innerHTML = '<p>Suche...</p>';

  try {
    const body = { query, platform };
    if (limit) body.limit = limit;
    const data = await api('/search', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    renderSearchResults(data.results || []);
  } catch (e) {
    $('#search-results').innerHTML = '<p>Suche fehlgeschlagen</p>';
  }
}

let _searchTimer = null;
function liveSearch() {
  clearTimeout(_searchTimer);
  _searchTimer = setTimeout(() => searchAnime(5), 300);
}

function renderSearchResults(results) {
  const container = $('#search-results');
  if (!results.length) {
    container.innerHTML = '<p style="color:var(--text-muted); text-align:center; padding:16px 0;">Keine Ergebnisse</p>';
    return;
  }

  container.innerHTML = results.map((r, i) => `
    <div class="search-result fade-in" style="animation-delay:${i * 40}ms" data-url="${esc(r.url)}">
      <div class="search-poster-wrap">
        <div class="search-poster-placeholder"></div>
        <img class="search-poster" alt="${esc(r.title)}" style="display:none">
      </div>
      <div class="info">
        <span class="title">${esc(r.title)}</span>
        <span class="platform">${esc(r.platform)}</span>
        ${r.description ? `<br><small style="color:var(--text-muted)">${esc(r.description).slice(0,120)}</small>` : ''}
      </div>
      <button class="btn btn-primary btn-sm" onclick="addFromSearch('${esc(r.url)}')">+ Hinzufügen</button>
    </div>
  `).join('');

  // Poster asynchron nachladen
  results.forEach((r, i) => {
    api(`/poster?url=${encodeURIComponent(r.url)}`)
      .then(data => {
        if (!data.poster_url) return;
        const cards = $$('#search-results .search-result');
        const card = cards[i];
        if (!card) return;
        const img = card.querySelector('.search-poster');
        const placeholder = card.querySelector('.search-poster-placeholder');
        if (img) {
          img.src = `/proxy_poster?url=${encodeURIComponent(data.poster_url)}`;
          img.onload = () => {
            img.style.display = 'block';
            if (placeholder) placeholder.style.display = 'none';
          };
          img.onerror = () => { /* bleibt Placeholder */ };
        }
      })
      .catch(() => { /* Poster optional – Fehler ignorieren */ });
  });
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

function toggleDbOrder() {
  dbSortDir = dbSortDir === 'ASC' ? 'DESC' : 'ASC';
  const btn = $('#db-order-btn');
  if (btn) btn.textContent = dbSortDir === 'ASC' ? '↑ Aufsteigend' : '↓ Absteigend';
  loadDatabase();
}

async function loadDatabase() {
  const search   = $('#db-search')?.value.trim() || '';
  const complete = $('#db-complete')?.value || '';
  const deutsch  = $('#db-deutsch')?.value  || '';
  const sort_by  = $('#db-sort')?.value     || dbSortCol;

  try {
    let url = `/database?q=${encodeURIComponent(search)}&sort=${sort_by}&dir=${dbSortDir}`;
    if (complete !== '') url += `&complete=${complete}`;
    if (deutsch  !== '') url += `&deutsch=${deutsch}`;
    const data = await api(url);
    renderDatabase(data);
  } catch (e) {
    console.error('DB load error:', e);
  }
}

function renderDatabase(entries) {
  const tbody = $('#db-tbody');
  if (!entries || !entries.length) {
    tbody.innerHTML = '<tr><td colspan="9" class="db-empty">Keine Einträge gefunden</td></tr>';
    return;
  }

  tbody.innerHTML = entries.map(e => {
    const isDeleted = !!e.deleted;
    const ok  = '<span class="db-bool-yes">✔</span>';
    const no  = '<span class="db-bool-no">✘</span>';
    const komplett = isDeleted ? '<span style="color:var(--text-muted)">del</span>' : (e.complete ? ok : no);
    const deKomp   = e.deutsch_komplett ? ok : no;
    const season   = e.last_season  || 0;
    const episode  = e.last_episode || 0;
    const film     = e.last_film    || 0;
    const se       = `S${String(season).padStart(2,'0')}E${String(episode).padStart(3,'0')}`;

    // Kurz-URL für Anzeige
    const displayUrl = e.url.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '');

    // Fehlende deutsche Folgen formatieren
    let fehlendeDE = '–';
    let missing = [];
    try {
      missing = JSON.parse(e.fehlende_deutsch_folgen || '[]');
      if (missing.length > 0) {
        if (missing.length <= 3) {
          fehlendeDE = missing.map(ep => `E${String(ep).padStart(3,'0')}`).join(', ');
        } else {
          fehlendeDE = `${missing.length} Episoden`;
        }
      }
    } catch (ex) {
      fehlendeDE = '–';
    }

    const actionBtns = isDeleted
      ? `<button class="db-btn db-btn-restore" onclick="restoreAnime(${e.id})">&#8635; Erneut laden</button>
         <button class="db-btn db-btn-del" onclick="deleteAnime(${e.id})">&#10005; Löschen</button>`
      : `<button class="db-btn db-btn-del" onclick="deleteAnime(${e.id})">&#10005; Löschen</button>`;

    return `<tr class="${isDeleted ? 'db-row-deleted' : ''}">
      <td class="db-nr">${e.id}</td>
      <td>${esc(e.title || '–')}</td>
      <td><a class="db-url-link" href="${e.url}" target="_blank" rel="noreferrer" title="${e.url}">${esc(displayUrl)}</a></td>
      <td style="text-align:center">${komplett}</td>
      <td style="text-align:center">${deKomp}</td>
      <td class="db-missing-de" title="${esc(JSON.stringify(missing || []))}">${esc(fehlendeDE)}</td>
      <td class="db-se">${se}</td>
      <td style="text-align:center">${film || '–'}</td>
      <td><div class="db-actions">${actionBtns}</div></td>
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
  if ($('#db-sort'))     $('#db-sort').value = col;
  const btn = $('#db-order-btn');
  if (btn) btn.textContent = dbSortDir === 'ASC' ? '↑ Aufsteigend' : '↓ Absteigend';
  loadDatabase();
}

function queueAdd(id) {
  api(`/anime/${id}/queue`, { method: 'POST' }).catch(() => {});
}

async function deleteAnime(id) {
  if (!confirm('Eintrag wirklich löschen?')) return;
  if (!confirm('Sicher? Dieser Schritt kann nicht rückgängig gemacht werden.')) return;
  await api(`/anime/${id}`, { method: 'DELETE' });
  loadDatabase();
}

async function restoreAnime(id) {
  if (!confirm('Diesen Eintrag erneut herunterladen? Der Status wird zurückgesetzt.')) return;
  await api(`/anime/${id}/restore`, { method: 'POST' });
  loadDatabase();
}

// ──────────────────────── Einstellungen Tab ────────────────────────

let currentConfig = {};

function initSettingsPills() {
  $$('.settings-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      $$('.settings-pill').forEach(p => p.classList.remove('active'));
      $$('.settings-panel').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      const panel = $(`#${pill.dataset.settings}`);
      if (panel) panel.classList.add('active');
    });
  });
}

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
  $('#cfg-refresh-titles').checked = cfg.download?.refresh_titles || false;

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
      refresh_titles: $('#cfg-refresh-titles').checked,
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
  el.className = `toast-msg toast-${type}`;
  el.style.display = 'inline-block';
  el.style.animation = 'none';
  el.offsetHeight; // trigger reflow
  el.style.animation = 'fadeIn 0.2s ease-out';
  clearTimeout(el._hideTimer);
  el._hideTimer = setTimeout(() => {
    el.style.opacity = '0';
    el.style.transition = 'opacity 0.3s';
    setTimeout(() => { el.style.display = 'none'; el.style.opacity = ''; el.style.transition = ''; }, 300);
  }, 3500);
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

// ──────────────────────── Ordner-Picker ────────────────────────

let _folderPickerTarget = null;  // ID des Input-Feldes
let _folderPickerPath = '';       // Aktueller Pfad im Browser

function openFolderPicker(inputId) {
  _folderPickerTarget = inputId;
  const currentValue = $(`#${inputId}`)?.value || '';
  const overlay = $('#folder-picker-overlay');
  overlay.style.display = 'flex';

  // ESC zum Schließen
  document.addEventListener('keydown', _folderPickerEsc);

  // Starte beim aktuellen Wert oder Root
  browseTo(currentValue || '');
}

function closeFolderPicker() {
  const overlay = $('#folder-picker-overlay');
  overlay.style.display = 'none';
  _folderPickerTarget = null;
  document.removeEventListener('keydown', _folderPickerEsc);
}

function _folderPickerEsc(e) {
  if (e.key === 'Escape') closeFolderPicker();
}

function selectFolder() {
  if (_folderPickerTarget && _folderPickerPath) {
    $(`#${_folderPickerTarget}`).value = _folderPickerPath;
    // Flash-Feedback auf dem Input
    const input = $(`#${_folderPickerTarget}`);
    input.style.borderColor = 'var(--success)';
    input.style.boxShadow = '0 0 0 3px rgba(52,208,88,0.15)';
    setTimeout(() => { input.style.borderColor = ''; input.style.boxShadow = ''; }, 1200);
  }
  closeFolderPicker();
}

async function browseTo(path) {
  const listEl = $('#folder-list');
  listEl.innerHTML = '<li class="folder-empty">Lade...</li>';

  try {
    const data = await api('/browse', {
      method: 'POST',
      body: JSON.stringify({ path }),
    });

    _folderPickerPath = data.path || '';
    $('#folder-current-path').textContent = _folderPickerPath || '(Root)';

    // Breadcrumb rendern
    renderBreadcrumb(data.path, data.parent);

    // Ordnerliste rendern
    if (!data.dirs || !data.dirs.length) {
      listEl.innerHTML = '<li class="folder-empty">Keine Unterordner</li>';
      return;
    }

    let html = '';

    // Elternordner (zurück)
    if (data.parent !== null && data.parent !== undefined) {
      html += `<li class="folder-item" ondblclick="browseTo('${escAttr(data.parent)}')" onclick="this.classList.toggle('selected')">
        <span class="folder-icon">⬆️</span>
        <span class="folder-name">..</span>
      </li>`;
    }

    for (const dir of data.dirs) {
      const icon = dir.is_drive ? '💾' : '📁';
      html += `<li class="folder-item" ondblclick="browseTo('${escAttr(dir.path)}')" onclick="previewFolder('${escAttr(dir.path)}')">
        <span class="folder-icon">${icon}</span>
        <span class="folder-name">${esc(dir.name)}</span>
      </li>`;
    }

    listEl.innerHTML = html;

  } catch (e) {
    listEl.innerHTML = `<li class="folder-empty" style="color:var(--danger)">Fehler: ${esc(e.message || 'Unbekannt')}</li>`;
  }
}

function previewFolder(path) {
  _folderPickerPath = path;
  $('#folder-current-path').textContent = path;
}

function renderBreadcrumb(fullPath, parent) {
  const bc = $('#folder-breadcrumb');
  if (!fullPath) {
    bc.innerHTML = '<span onclick="browseTo(\'\')">🖥️ Computer</span>';
    return;
  }

  // Pfad in Teile zerlegen
  const isWindows = fullPath.includes('\\');
  const sep = isWindows ? '\\' : '/';
  const parts = fullPath.split(/[/\\]/).filter(Boolean);

  let html = `<span onclick="browseTo('')">🖥️</span><span class="sep">/</span>`;
  let accumulated = '';

  for (let i = 0; i < parts.length; i++) {
    if (isWindows) {
      accumulated = i === 0 ? parts[0] + '\\' : accumulated + parts[i] + (i < parts.length - 1 ? '\\' : '');
    } else {
      accumulated += '/' + parts[i];
    }
    const isLast = i === parts.length - 1;
    html += `<span onclick="browseTo('${escAttr(accumulated)}')" style="${isLast ? 'color:var(--text);font-weight:600;' : ''}">${esc(parts[i])}</span>`;
    if (!isLast) html += '<span class="sep">/</span>';
  }

  bc.innerHTML = html;
}

function escAttr(str) {
  return (str || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

// ──────────────────────── Init ────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initUpload();
  initSettingsPills();

  // Status-Polling
  refreshStatus();
  statusInterval = setInterval(refreshStatus, 5000);

  // Mini-Log Polling
  refreshLog();
  setInterval(refreshLog, 8000);

  // Log-Auto-Refresh (Logs-Tab)
  logAutoRefreshInterval = setInterval(refreshFullLog, 8000);

  // Disk Info – mit farbiger Anzeige
  api('/disk').then(d => {
    const el = $('#disk-info');
    if (el && d.free_gb !== undefined) {
      const gb = parseFloat(d.free_gb);
      el.textContent = `💾 ${d.free_gb} GB frei`;
      if (gb < 5) el.style.color = 'var(--danger)';
      else if (gb < 20) el.style.color = 'var(--warning)';
    }
  });

  // Enter-Key für Suche (alle Ergebnisse)
  $('#search-query')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') searchAnime();
  });
  // Live-Suche beim Tippen (max 5)
  $('#search-query')?.addEventListener('input', liveSearch);
  $('#add-url')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') addLink();
  });
});

// ──────────────────────── Export-Funktionen ────────────────────────

function exportDatabase() {
  // Direkter Download der Datenbank-Datei
  const link = document.createElement('a');
  link.href = '/export/database';
  link.download = 'AniLoader.db';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function exportLinks() {
  // Direkter Download der Links-Datei
  const link = document.createElement('a');
  link.href = '/export/links';
  link.download = 'AniLoader.txt';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
