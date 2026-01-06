// ==UserScript==
// @name         AniWorld & S.to Download-Button
// @namespace    AniLoader
// @version      1.6
// @icon         https://cdn-icons-png.flaticon.com/512/9205/9205302.png
// @description  Fügt einen Export-Button unter die Episodenliste ein, prüft, ob der Anime-Link schon in der DB ist, und sendet ihn bei Klick an ein lokales Python-Skript. Funktioniert für AniWorld und S.to.
// @author       Wim
// @downloadURL  https://github.com/WimWamWom/AniLoader/raw/refs/heads/main/Tampermonkey.user.js
// @updateURL    https://github.com/WimWamWom/AniLoader/raw/refs/heads/main/Tampermonkey.user.js
// @match        https://aniworld.to/*
// @match        https://s.to/*
// @grant        GM_xmlhttpRequest
// @connect      deine.domain.com
// @connect      10.10.10.10
// ==/UserScript==

(function() {
    'use strict';

    // 🌐 === SERVER KONFIGURATION ===
    // Passe diese Werte an deine Umgebung an:
    
    // Option 1: Domain verwenden (nginx reverse proxy mit SSL)
    const USE_DOMAIN = true;// true = Domain verwenden, false = IP verwenden
    const SERVER_DOMAIN = "deine.domain.com";// Deine Domain
    const USE_HTTPS = true; 

    // Option 2: IP-Adresse verwenden (direkter Zugriff)
    const SERVER_IP = "10.10.10.10";
    const SERVER_PORT = 5050;
    
    // Basic Auth (für nginx Passwortschutz)
    const AUTH_USERNAME = "Username";// Benutzername für Basic Auth
    const AUTH_PASSWORD = "Password";// Passwort für Basic Auth
    const USE_AUTH = true;// true = Basic Auth verwenden, false = ohne Auth

    // === HILFSFUNKTIONEN ===
    function getBaseUrl() {
        if (USE_DOMAIN) {
            const protocol = USE_HTTPS ? 'https' : 'http';
            return `${protocol}://${SERVER_DOMAIN}`;
        } else {
            return `http://${SERVER_IP}:${SERVER_PORT}`;
        }
    }

    function getAuthHeaders() {
        const headers = {
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache'
        };
        if (USE_AUTH && AUTH_USERNAME && AUTH_PASSWORD) {
            headers.Authorization = 'Basic ' + btoa(AUTH_USERNAME + ':' + AUTH_PASSWORD);
        }
        return headers;
    }

    async function apiGet(path) {
        const separator = path.includes('?') ? '&' : '?';
        const url = `${getBaseUrl()}${path}${separator}_t=${Date.now()}`;
        console.log('[AniLoader] GET:', url);
        return new Promise((resolve, reject) => {
            GM.xmlHttpRequest({
                method: 'GET',
                url: url,
                headers: getAuthHeaders(),
                onload: (response) => {
                    if (response.status >= 200 && response.status < 300) {
                        try {
                            resolve(JSON.parse(response.responseText));
                        } catch (e) {
                            reject(new Error('JSON parse error'));
                        }
                    } else {
                        reject(new Error('API ' + response.status));
                    }
                },
                onerror: () => reject(new Error('Network error')),
                ontimeout: () => reject(new Error('Timeout'))
            });
        });
    }
    async function apiPost(path, body) {
        const url = `${getBaseUrl()}${path}`;
        console.log('[AniLoader] POST:', url, body);
        const headers = {
            'Content-Type':'application/json',
            ...getAuthHeaders()
        };
        return new Promise((resolve, reject) => {
            GM.xmlHttpRequest({
                method: 'POST',
                url: url,
                headers: headers,
                data: JSON.stringify(body||{}),
                onload: (response) => {
                    if (response.status >= 200 && response.status < 300) {
                        try {
                            resolve(JSON.parse(response.responseText));
                        } catch (e) {
                            reject(new Error('JSON parse error'));
                        }
                    } else {
                        reject(new Error('API ' + response.status));
                    }
                },
                onerror: () => reject(new Error('Network error')),
                ontimeout: () => reject(new Error('Timeout'))
            });
        });
    }

    function getAnimeBaseUrl() {
        const url = window.location.href;
        let match;

        if(url.includes("aniworld.to")) {
            match = url.match(/https:\/\/aniworld\.to\/anime\/stream\/([^\/]+)/);
            return match ? `https://aniworld.to/anime/stream/${match[1]}` : url;
        }

        if(url.includes("s.to")) {
            match = url.match(/https:\/\/s\.to\/serie\/stream\/([^\/]+)/);
            return match ? `https://s.to/serie/stream/${match[1]}` : url;
        }

        return url;
    }

    const streamContainer = document.querySelector('#stream') || document.querySelector('.episodes-list');
    if (!streamContainer) return;

    // Wrapper, in den entweder der Button oder ein Offline-Hinweis gerendert wird
    const buttonWrapper = document.createElement("div");
    buttonWrapper.style.marginTop = "16px";
    buttonWrapper.style.marginBottom = "16px";
    buttonWrapper.style.textAlign = "left";

    // Button-Element (wird nur eingefügt, wenn der Server online ist)
    const exportButton = document.createElement("button");
    exportButton.innerText = "📤 Downloaden";
    exportButton.style.backgroundColor = "rgba(99,124,249,1)";
    exportButton.style.color = "white";
    exportButton.style.fontSize = "15px";
    exportButton.style.fontWeight = "bold";
    exportButton.style.padding = "10px 18px";
    exportButton.style.border = "none";
    exportButton.style.borderRadius = "8px";
    exportButton.style.cursor = "pointer";
    exportButton.style.boxShadow = "0px 3px 8px rgba(0,0,0,0.25)";
    exportButton.style.transition = "all 0.25s ease-in-out";

    exportButton.addEventListener("mouseover", () => {
        if(!exportButton.disabled) exportButton.style.backgroundColor = "rgba(79,104,229,1)";
    });
    exportButton.addEventListener("mouseout", () => {
        if(!exportButton.disabled) exportButton.style.backgroundColor = "rgba(99,124,249,1)";
    });

    // Offline-Hinweis (gleich groß wie der Download-Button, weiß, mit Symbol)
    const offlineInfo = document.createElement('button');
    offlineInfo.textContent = '⛔ Server offline';
    offlineInfo.style.backgroundColor = '#ffffff';
    offlineInfo.style.color = '#333';
    offlineInfo.style.fontSize = '15px';
    offlineInfo.style.fontWeight = 'bold';
    offlineInfo.style.padding = '10px 18px';
    offlineInfo.style.border = '1px solid rgba(108,117,125,0.35)';
    offlineInfo.style.borderRadius = '8px';
    offlineInfo.style.cursor = 'not-allowed';
    offlineInfo.style.boxShadow = '0px 3px 8px rgba(0,0,0,0.15)';
    offlineInfo.style.transition = 'all 0.25s ease-in-out';
    offlineInfo.disabled = true;

    // Compute and set button state based on DB + status
    async function refreshButton() {
        const animeUrl = getAnimeBaseUrl();
        let entry = null;
        try {
            const db = await apiGet(`/database?q=${encodeURIComponent(animeUrl)}`);
            entry = Array.isArray(db) ? db.find(r => r.url === animeUrl) : null;
        } catch(e) { /* ignore */ }
        let status = null;
        try { status = await apiGet('/status'); } catch(e) { /* ignore */ }
        const running = status && status.status === 'running';
        const currentTitle = status && status.current_title;

        // Decide label/style
        let label = '📤 Downloaden';
        let bg = 'rgba(99,124,249,1)'; // primary
        let disabled = false;

        if (!entry || entry.deleted) {
            // not in DB or deleted -> offer Downloaden
            label = '📤 Downloaden';
            bg = 'rgba(99,124,249,1)';
            disabled = false;
        } else if (entry.complete) {
            // complete -> Gedownloaded
            label = '✅ Gedownloaded';
            bg = 'rgba(0,200,0,0.8)';
            disabled = true;
        } else if (running && currentTitle && entry.title === currentTitle) {
            // currently downloading this title
            label = '⬇️ Downloaded';
            bg = 'rgba(255,184,107,0.9)'; // warning
            disabled = true;
        } else {
            // in DB but not complete and not currently downloading -> disabled per requirement
            label = '📄 In der Liste';
            bg = 'rgba(108,117,125,0.9)'; // secondary
            disabled = true;
        }

        exportButton.innerText = label;
        exportButton.style.backgroundColor = bg;
        exportButton.disabled = !!disabled;
        exportButton.style.cursor = disabled ? 'not-allowed' : 'pointer';
    }

    // Click -> ensure in DB if needed, then start download if not running
    exportButton.addEventListener("click", async () => {
        if (exportButton.disabled) return;
        const animeUrl = getAnimeBaseUrl();
        try {
            // Check DB state
            const db = await apiGet(`/database?q=${encodeURIComponent(animeUrl)}`);
            let entry = Array.isArray(db) ? db.find(r => r.url === animeUrl) : null;
            if (!entry || entry.deleted) {
                // add/reactivate
                const res = await apiPost('/export', { url: animeUrl });
                if (!(res && res.status === 'ok')) throw new Error('Export failed');
            }
            // Check if a download is already running
            const s = await apiGet('/status');
            const running = s && s.status === 'running';
            if (!running) {
                await apiPost('/start_download', { mode: 'default' });
            }
            // reflect state
            await refreshButton();
        } catch (e) {
            console.error(e);
            exportButton.innerText = "⚠ Fehler!";
            exportButton.style.backgroundColor = "rgba(200,0,0,0.8)";
        }
    });

    // Server-Check und UI-Umschaltung
    async function isServerOnline() {
        try {
            const url = `${getBaseUrl()}/status?_t=${Date.now()}`;
            console.log('[AniLoader] Checking server:', url);
            return new Promise((resolve) => {
                GM.xmlHttpRequest({
                    method: 'GET',
                    url: url,
                    headers: getAuthHeaders(),
                    timeout: 5000,
                    onload: (response) => {
                        console.log('[AniLoader] Server response:', response.status);
                        if (response.status >= 200 && response.status < 300) {
                            try {
                                const data = JSON.parse(response.responseText);
                                console.log('[AniLoader] Server data:', data);
                            } catch (e) { /* ignore */ }
                            resolve(true);
                        } else {
                            resolve(false);
                        }
                    },
                    onerror: (e) => {
                        console.error('[AniLoader] Server-Check Fehler:', e);
                        resolve(false);
                    },
                    ontimeout: () => {
                        console.error('[AniLoader] Server-Check Timeout');
                        resolve(false);
                    }
                });
            });
        } catch (e) {
            console.error('[AniLoader] Server-Check Fehler:', e);
            return false;
        }
    }

    let onlineState = null; // unknown | true | false
    let refreshTimer = null;

    async function renderByServerState() {
        const isOnline = await isServerOnline();
        console.log('[AniLoader] Server online:', isOnline, '| Previous state:', onlineState);
        if (isOnline === onlineState) return; // no change
        onlineState = isOnline;
        // clear wrapper
        buttonWrapper.innerHTML = '';
        if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }

        if (isOnline) {
            console.log('[AniLoader] ✅ Server ONLINE - Zeige Download-Button');
            // show button and start periodic refresh
            buttonWrapper.appendChild(exportButton);
            await refreshButton();
            refreshTimer = setInterval(refreshButton, 15000);
        } else {
            console.log('[AniLoader] ❌ Server OFFLINE - Zeige Offline-Hinweis');
            // show offline info
            buttonWrapper.appendChild(offlineInfo);
        }
    }

    // mount wrapper next to stream container and start polling server state
    streamContainer.insertAdjacentElement("afterend", buttonWrapper);

    console.log('[AniLoader] 🚀 Skript gestartet');
    console.log('[AniLoader] Server:', `http://${SERVER_IP}:${SERVER_PORT}`);
    console.log('[AniLoader] URL:', getAnimeBaseUrl());

    // Show offline placeholder immediately (do not wait for /health)
    buttonWrapper.appendChild(offlineInfo);

    // Then check server status and update UI accordingly
    console.log('[AniLoader] Starte Server-Check...');
    renderByServerState();
    setInterval(renderByServerState, 10000);
})();
