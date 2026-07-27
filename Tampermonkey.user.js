// ==UserScript==
// @name         AniLoader Export-Button
// @namespace    AniLoader
// @version      2.3
// @icon         https://raw.githubusercontent.com/WimWamWom/AniLoader/main/web/static/AniLoader.png
// @description  Fügt einen Download-Button auf aniworld.to / serienstream.to ein, der Serien an den AniLoader-Server sendet.
// @author       WimWamWom
// @downloadURL  https://github.com/WimWamWom/AniLoader/raw/refs/heads/main/Tampermonkey.user.js
// @updateURL    https://github.com/WimWamWom/AniLoader/raw/refs/heads/main/Tampermonkey.user.js
// @match        https://aniworld.to/*
// @match        https://s.to/*
// @match        https://serienstream.to/*
// @match        https://serienstream.cx/*
// @match        http://186.2.175.5/*
// @grant        GM_xmlhttpRequest
// @grant        GM.xmlHttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_deleteValue
// @grant        GM_registerMenuCommand
// @connect      aniloader.example.com
// @connect      localhost:5050
// ==/UserScript==

(function () {
    'use strict';

    // ════════════════════════════════════════════
    //  SERVER-KONFIGURATION
    // ════════════════════════════════════════════

    const DEFAULTS = {
        // Option A: Domain (z.B. hinter nginx/Caddy Reverse-Proxy)
        USE_DOMAIN: false,
        SERVER_DOMAIN: "aniloader.example.com",
        USE_HTTPS: true,
        // Option B: Direkte IP
        SERVER_IP: "127.0.0.1",
        SERVER_PORT: 5050,
        // Basic-Auth (optional, für Reverse-Proxy)
        USE_AUTH: false,
        AUTH_USER: "",
        AUTH_PASS: "",
    };

    const CONFIG_KEY = "aniloader_config";

    // Gespeicherte Einstellungen über die Standardwerte legen (Storage gewinnt).
    function loadConfig() {
        let stored = null;
        try { stored = (typeof GM_getValue === 'function') ? GM_getValue(CONFIG_KEY, null) : null; }
        catch (e) { /* Storage nicht verfügbar */ }
        if (typeof stored === "string") { try { stored = JSON.parse(stored); } catch { stored = null; } }
        return Object.assign({}, DEFAULTS, (stored && typeof stored === "object") ? stored : {});
    }

    let CONFIG = loadConfig();

    // ════════════════════════════════════════════

    const GMX = typeof GM !== 'undefined' && GM.xmlHttpRequest ? GM.xmlHttpRequest : GM_xmlhttpRequest;

    function baseUrl() {
        if (CONFIG.USE_DOMAIN) {
            return `${CONFIG.USE_HTTPS ? 'https' : 'http'}://${CONFIG.SERVER_DOMAIN}`;
        }
        return `http://${CONFIG.SERVER_IP}:${CONFIG.SERVER_PORT}`;
    }

    function authHeaders() {
        const h = { 'Cache-Control': 'no-cache' };
        if (CONFIG.USE_AUTH && CONFIG.AUTH_USER) {
            h.Authorization = 'Basic ' + btoa(`${CONFIG.AUTH_USER}:${CONFIG.AUTH_PASS}`);
        }
        return h;
    }

    function apiGet(path) {
        const sep = path.includes('?') ? '&' : '?';
        return new Promise((resolve, reject) => {
            GMX({
                method: 'GET',
                url: `${baseUrl()}${path}${sep}_t=${Date.now()}`,
                headers: authHeaders(),
                timeout: 6000,
                onload: r => {
                    if (r.status >= 200 && r.status < 300) {
                        try { resolve(JSON.parse(r.responseText)); }
                        catch { reject(new Error('JSON parse')); }
                    } else reject(new Error(`HTTP ${r.status}`));
                },
                onerror: () => reject(new Error('network')),
                ontimeout: () => reject(new Error('timeout'))
            });
        });
    }

    function apiPost(path, body) {
        return new Promise((resolve, reject) => {
            GMX({
                method: 'POST',
                url: `${baseUrl()}${path}`,
                headers: { 'Content-Type': 'application/json', ...authHeaders() },
                data: JSON.stringify(body || {}),
                timeout: 10000,
                onload: r => {
                    if (r.status >= 200 && r.status < 300) {
                        try { resolve(JSON.parse(r.responseText)); }
                        catch { reject(new Error('JSON parse')); }
                    } else reject(new Error(`HTTP ${r.status}`));
                },
                onerror: () => reject(new Error('network')),
                ontimeout: () => reject(new Error('timeout'))
            });
        });
    }

    // ── Einstellungen (bleiben über Skript-Updates via GM-Storage erhalten) ──

    function saveConfig(cfg) {
        CONFIG = Object.assign({}, DEFAULTS, cfg);
        try { GM_setValue(CONFIG_KEY, CONFIG); }
        catch (e) { alert('[AniLoader] Speichern fehlgeschlagen: ' + e); }
    }

    function openSettings() {
        const existing = document.getElementById('aniloader-settings');
        if (existing) existing.remove();

        const ov = document.createElement('div');
        ov.id = 'aniloader-settings';
        Object.assign(ov.style, {
            position: 'fixed', inset: '0', zIndex: '2147483647',
            background: 'rgba(0,0,0,.55)', display: 'flex',
            alignItems: 'center', justifyContent: 'center'
        });

        const box = document.createElement('div');
        Object.assign(box.style, {
            background: '#1e1e2a', color: '#eee', padding: '22px 24px',
            borderRadius: '12px', width: 'min(460px, 92vw)',
            font: '14px/1.4 system-ui, sans-serif',
            boxShadow: '0 12px 40px rgba(0,0,0,.5)', maxHeight: '90vh', overflowY: 'auto'
        });
        const title = document.createElement('h2');
        title.textContent = '⚙️ AniLoader – Einstellungen';
        title.style.cssText = 'margin:0 0 14px;font-size:18px;';
        box.appendChild(title);

        const fields = [
            ['USE_DOMAIN',    'checkbox', 'Domain statt IP verwenden'],
            ['SERVER_DOMAIN', 'text',     'Server-Domain'],
            ['USE_HTTPS',     'checkbox', 'HTTPS für Domain'],
            ['SERVER_IP',     'text',     'Server-IP'],
            ['SERVER_PORT',   'number',   'Server-Port'],
            ['USE_AUTH',      'checkbox', 'Basic-Auth verwenden'],
            ['AUTH_USER',     'text',     'Auth-Benutzer'],
            ['AUTH_PASS',     'password', 'Auth-Passwort'],
        ];

        const inputs = {};
        for (const [key, type, label] of fields) {
            const row = document.createElement('label');
            row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:12px;margin:8px 0;';
            const span = document.createElement('span');
            span.textContent = label;
            span.style.flex = '1';
            const inp = document.createElement('input');
            inp.type = type;
            if (type === 'checkbox') {
                inp.checked = !!CONFIG[key];
                inp.style.cssText = 'width:18px;height:18px;';
            } else {
                inp.value = CONFIG[key];
                inp.style.cssText = 'flex:1;max-width:230px;padding:5px 8px;border-radius:6px;border:1px solid #444;background:#2b2b3a;color:#eee;';
            }
            inputs[key] = inp;
            row.append(span, inp);
            box.appendChild(row);
        }

        const btnRow = document.createElement('div');
        btnRow.style.cssText = 'display:flex;gap:10px;margin-top:18px;justify-content:flex-end;';
        const mkBtn = (txt, bg) => {
            const b = document.createElement('button');
            b.textContent = txt;
            b.style.cssText = `padding:8px 16px;border:none;border-radius:8px;cursor:pointer;color:#fff;font-weight:bold;background:${bg};`;
            return b;
        };
        const cancel = mkBtn('Abbrechen', '#555');
        const save = mkBtn('💾 Speichern', 'rgba(99,124,249,1)');
        cancel.addEventListener('click', () => ov.remove());
        save.addEventListener('click', () => {
            const cfg = {};
            for (const [key, type] of fields) {
                if (type === 'checkbox') cfg[key] = inputs[key].checked;
                else if (type === 'number') cfg[key] = parseInt(inputs[key].value, 10) || DEFAULTS[key];
                else cfg[key] = inputs[key].value.trim();
            }
            saveConfig(cfg);
            ov.remove();
            alert('[AniLoader] Einstellungen gespeichert. Die Seite wird neu geladen.');
            location.reload();
        });
        btnRow.append(cancel, save);
        box.appendChild(btnRow);

        ov.appendChild(box);
        ov.addEventListener('click', e => { if (e.target === ov) ov.remove(); });
        (document.body || document.documentElement).appendChild(ov);
    }

    function resetSettings() {
        if (!confirm('[AniLoader] Alle gespeicherten Einstellungen auf Standard zurücksetzen?')) return;
        try { if (typeof GM_deleteValue === 'function') GM_deleteValue(CONFIG_KEY); } catch (e) { /* ignore */ }
        CONFIG = loadConfig();
        alert('[AniLoader] Einstellungen zurückgesetzt. Die Seite wird neu geladen.');
        location.reload();
    }

    if (typeof GM_registerMenuCommand === 'function') {
        GM_registerMenuCommand('⚙️ AniLoader – Einstellungen', openSettings);
        GM_registerMenuCommand('↩️ AniLoader – Einstellungen zurücksetzen', resetSettings);
    }

    // ── Serien-URL extrahieren ──

    function seriesUrl() {
        const href = location.href;
        let m;
        if (href.includes('aniworld.to')) {
            m = href.match(/https:\/\/aniworld\.to\/anime\/stream\/([^\/]+)/);
            return m ? `https://aniworld.to/anime/stream/${m[1]}` : null;
        }
        if (href.includes('s.to')) {
            m = href.match(/https:\/\/s\.to\/serie\/(?:stream\/)?([^\/?#]+)/);
            return m ? `https://s.to/serie/${m[1]}` : null;
        }
        if (href.includes('serienstream.to')) {
            m = href.match(/https:\/\/serienstream\.to\/serie\/(?:stream\/)?([^\/?#]+)/);
            return m ? `https://serienstream.to/serie/${m[1]}` : null;
        }
        if (href.includes('serienstream.cx')) {
            m = href.match(/https:\/\/serienstream\.cx\/serie\/(?:stream\/)?([^\/?#]+)/);
            return m ? `https://serienstream.cx/serie/${m[1]}` : null;
        }
        if (href.includes('186.2.175.5')) {
            m = href.match(/http:\/\/186\.2\.175\.5\/serie\/(?:stream\/)?([^\/?#]+)/);
            return m ? `http://186.2.175.5/serie/${m[1]}` : null;
        }
        return null;
    }

    function normalizeSeriesUrl(value) {
        if (!value) return value;
        return value
            .replace(/^https?:\/\/s\.to\/serie\/(?:stream\/)?/i, 'https://serienstream.to/serie/')
            .replace(/^https?:\/\/serienstream\.cx\/serie\/(?:stream\/)?/i, 'https://serienstream.to/serie/')
            .replace(/^http:\/\/186\.2\.175\.5\/serie\/(?:stream\/)?/i, 'https://serienstream.to/serie/')
            .replace(/^https?:\/\/serienstream\.to\/serie\/stream\//i, 'https://serienstream.to/serie/');
    }

    function seriesKey(value) {
        const url = normalizeSeriesUrl(value || '');
        let m = url.match(/^https:\/\/aniworld\.to\/anime\/stream\/([^\/?#]+)/i);
        if (m) return `aniworld:${m[1].toLowerCase()}`;
        m = url.match(/^https:\/\/serienstream\.to\/serie\/([^\/?#]+)/i);
        if (m) return `serienstream.to:${m[1].toLowerCase()}`;
        return null;
    }

    const rawUrl = seriesUrl();
    if (!rawUrl) return; // kein Stream-URL → Skript ignorieren

    // Immer kanonische URL an die API schicken
    const url = normalizeSeriesUrl(rawUrl);
    const currentKey = seriesKey(url);

    // ── Container finden ──

    let anchor = null;

    // Für s.to / serienstream.to / 186.2.175.5 neue HTML-Struktur
    if (rawUrl.includes('s.to') || rawUrl.includes('serienstream.to') || rawUrl.includes('serienstream.cx') || rawUrl.includes('186.2.175.5')) {
        anchor = document.querySelector('nav.mb-3#episode-nav') ||
                document.querySelector('.d-md-none.mb-2');
    }

    // Fallback für aniworld.to oder wenn s.to Selektoren nicht gefunden werden
    if (!anchor) {
        anchor = document.querySelector('#stream') || document.querySelector('.episodes-list');
    }

    if (!anchor) return;

    // ── UI-Elemente ──

    const wrap = document.createElement('div');
    wrap.style.cssText = 'margin:16px 0;text-align:left;';

    const btn = document.createElement('button');
    Object.assign(btn.style, {
        fontSize: '15px', fontWeight: 'bold', padding: '10px 18px',
        border: 'none', borderRadius: '8px', cursor: 'pointer',
        color: '#fff', boxShadow: '0 3px 8px rgba(0,0,0,.25)',
        transition: 'all .2s'
    });

    const offlineBtn = document.createElement('button');
    offlineBtn.textContent = '⛔ Server offline';
    Object.assign(offlineBtn.style, {
        fontSize: '15px', fontWeight: 'bold', padding: '10px 18px',
        border: '1px solid rgba(108,117,125,.35)', borderRadius: '8px',
        cursor: 'not-allowed', color: '#333', backgroundColor: '#fff',
        boxShadow: '0 3px 8px rgba(0,0,0,.15)'
    });
    offlineBtn.disabled = true;

    // ── Button-State berechnen ──

    function setBtn(label, bg, disabled) {
        btn.textContent = label;
        btn.style.backgroundColor = bg;
        btn.disabled = !!disabled;
        btn.style.cursor = disabled ? 'not-allowed' : 'pointer';
    }

    async function refreshBtn() {
        let entry = null;
        try {
            const searchToken = currentKey ? currentKey.split(':', 2)[1] : url;
            const db = await apiGet(`/database?q=${encodeURIComponent(searchToken)}`);
            entry = Array.isArray(db)
                ? db.find(r => seriesKey(r.url) === currentKey)
                : null;
        } catch { /* ignore */ }

        let status = null;
        try { status = await apiGet('/status'); } catch { /* ignore */ }

        const running = status?.status === 'running';

        if (!entry || entry.deleted) {
            setBtn('📤 Downloaden', 'rgba(99,124,249,1)', false);
        } else if (entry.complete) {
            setBtn('✅ Gedownloaded', 'rgba(0,200,0,.8)', true);
        } else if (running && status.current_title && entry.title === status.current_title) {
            setBtn('⬇️ Wird geladen…', 'rgba(255,184,107,.9)', true);
        } else {
            setBtn('📄 In der Liste', 'rgba(108,117,125,.9)', true);
        }
    }

    // ── Klick-Handler ──

    btn.addEventListener('click', async () => {
        if (btn.disabled) return;
        try {
            // In DB einfügen oder wiederherstellen
            const searchToken = currentKey ? currentKey.split(':', 2)[1] : url;
            const db = await apiGet(`/database?q=${encodeURIComponent(searchToken)}`);
            const entry = Array.isArray(db)
                ? db.find(r => seriesKey(r.url) === currentKey)
                : null;
            if (!entry || entry.deleted) {
                const res = await apiPost('/export', { url });
                if (!res || res.status !== 'ok') throw new Error('Export fehlgeschlagen');
            }

            // Nur Download starten wenn in Config autostart_mode !== null
            const s = await apiGet('/status');
            if (s?.status !== 'running') {
                try {
                    const config = await apiGet('/config');
                    const autostartMode = config?.download?.autostart_mode;
                    if (autostartMode && autostartMode !== null) {
                        await apiPost('/start_download', { mode: 'default' });
                    }
                } catch (configError) {
                    // Config-Fehler ignorieren, kein Auto-Download
                    console.log('[AniLoader] Config nicht verfügbar, kein Auto-Download');
                }
            }

            await refreshBtn();
        } catch (e) {
            console.error('[AniLoader]', e);
            setBtn('⚠ Fehler!', 'rgba(200,0,0,.8)', true);
            setTimeout(refreshBtn, 3000);
        }
    });

    // ── Online/Offline-Umschaltung ──

    let wasOnline = null;
    let refreshInterval = null;

    async function checkServer() {
        let online = false;
        try {
            await apiGet('/health');
            online = true;
        } catch { /* offline */ }

        if (online === wasOnline) return;
        wasOnline = online;
        wrap.innerHTML = '';
        if (refreshInterval) { clearInterval(refreshInterval); refreshInterval = null; }

        if (online) {
            wrap.appendChild(btn);
            await refreshBtn();
            refreshInterval = setInterval(refreshBtn, 15000);
        } else {
            wrap.appendChild(offlineBtn);
        }
    }

    // ── Initialisierung ──

    anchor.insertAdjacentElement('afterend', wrap);
    wrap.appendChild(offlineBtn); // sofort Offline anzeigen

    checkServer();
    setInterval(checkServer, 10000);
})();
