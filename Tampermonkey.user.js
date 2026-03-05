// ==UserScript==
// @name         AniLoader Export-Button
// @namespace    AniLoader
// @version      2.0
// @icon         https://raw.githubusercontent.com/WimWamWom/AniLoader/main/static/AniLoader.png
// @description  Fügt einen Download-Button auf aniworld.to / s.to ein, der Serien an den AniLoader-Server sendet.
// @author       Wim
// @downloadURL  https://github.com/WimWamWom/AniLoader/raw/refs/heads/main/Tampermonkey.user.js
// @updateURL    https://github.com/WimWamWom/AniLoader/raw/refs/heads/main/Tampermonkey.user.js
// @match        https://aniworld.to/*
// @match        https://s.to/*
// @grant        GM_xmlhttpRequest
// @grant        GM.xmlHttpRequest
// @connect      *
// ==/UserScript==

(function () {
    'use strict';

    // ════════════════════════════════════════════
    //  SERVER-KONFIGURATION – Bitte anpassen!
    // ════════════════════════════════════════════

    // Option A: Domain (z.B. hinter nginx/Caddy Reverse-Proxy)
    const USE_DOMAIN = false;
    const SERVER_DOMAIN = "aniloader.example.com";
    const USE_HTTPS = true;

    // Option B: Direkte IP
    const SERVER_IP = "127.0.0.1";
    const SERVER_PORT = 5050;

    // Basic-Auth (optional, für Reverse-Proxy)
    const USE_AUTH = false;
    const AUTH_USER = "";
    const AUTH_PASS = "";

    // ════════════════════════════════════════════

    const GMX = typeof GM !== 'undefined' && GM.xmlHttpRequest ? GM.xmlHttpRequest : GM_xmlhttpRequest;

    function baseUrl() {
        if (USE_DOMAIN) {
            return `${USE_HTTPS ? 'https' : 'http'}://${SERVER_DOMAIN}`;
        }
        return `http://${SERVER_IP}:${SERVER_PORT}`;
    }

    function authHeaders() {
        const h = { 'Cache-Control': 'no-cache' };
        if (USE_AUTH && AUTH_USER) {
            h.Authorization = 'Basic ' + btoa(`${AUTH_USER}:${AUTH_PASS}`);
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

    // ── Serien-URL extrahieren ──

    function seriesUrl() {
        const href = location.href;
        let m;
        if (href.includes('aniworld.to')) {
            m = href.match(/https:\/\/aniworld\.to\/anime\/stream\/([^\/]+)/);
            return m ? `https://aniworld.to/anime/stream/${m[1]}` : null;
        }
        if (href.includes('s.to')) {
            m = href.match(/https:\/\/s\.to\/serie\/([^\/]+)/);
            return m ? `https://s.to/serie/${m[1]}` : null;
        }
        return null;
    }

    const url = seriesUrl();
    if (!url) return; // kein Stream-URL → Skript ignorieren

    // ── Container finden ──

    let anchor = null;

    // Für s.to neue HTML-Struktur
    if (url.includes('s.to')) {
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
            const db = await apiGet(`/database?q=${encodeURIComponent(url)}`);
            entry = Array.isArray(db) ? db.find(r => r.url === url) : null;
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
            const db = await apiGet(`/database?q=${encodeURIComponent(url)}`);
            const entry = Array.isArray(db) ? db.find(r => r.url === url) : null;
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
