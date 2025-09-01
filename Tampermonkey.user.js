// ==UserScript==
// @name         AniWorld & S.to Download-Button
// @namespace    AniLoader
// @version      1.1
// @icon         https://cdn-icons-png.flaticon.com/512/9205/9205302.png
// @description  Fügt einen Export-Button unter die Episodenliste ein, prüft, ob der Anime-Link schon in der DB ist, und sendet ihn bei Klick an ein lokales Python-Skript. Funktioniert für AniWorld und S.to.
// @author       Wim
// @downloadURL  https://github.com/WimWamWom/AniLoader/raw/refs/heads/main/Tampermonkey.user.js
// @updateURL    https://github.com/WimWamWom/AniLoader/raw/refs/heads/main/Tampermonkey.user.js
// @match        https://aniworld.to/*
// @match        https://s.to/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // 🌐 === SERVER IP / DOMAIN ===
    const SERVER_IP = "localhost"; 

    async function apiGet(path) {
        const res = await fetch(`http://${SERVER_IP}:5050${path}`);
        if (!res.ok) throw new Error('API ' + res.status);
        return res.json();
    }
    async function apiPost(path, body) {
        const res = await fetch(`http://${SERVER_IP}:5050${path}`, {
            method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body||{})
        });
        if (!res.ok) throw new Error('API ' + res.status);
        return res.json();
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

    const buttonWrapper = document.createElement("div");
    buttonWrapper.style.marginTop = "16px";
    buttonWrapper.style.marginBottom = "16px";
    buttonWrapper.style.textAlign = "left";

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

    // Initial state & periodic refresh
    refreshButton();
    setInterval(refreshButton, 15000);

    buttonWrapper.appendChild(exportButton);
    streamContainer.insertAdjacentElement("afterend", buttonWrapper);
})();
