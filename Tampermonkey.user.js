// ==UserScript==
// @name         AniWorld & S.to Download-Button
// @namespace    AniLoader
// @version      1.0
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

    exportButton.addEventListener("click", () => {
        if(exportButton.disabled) return;

        const animeUrl = getAnimeBaseUrl();

        fetch(`http://${SERVER_IP}:5050/export`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url: animeUrl })
        })
        .then(response => response.json())
        .then(data => {
            if(data.status === "ok") {
                exportButton.innerText = "✅ Gedownloaded!";
                exportButton.style.backgroundColor = "rgba(0,200,0,0.8)";
                exportButton.disabled = true; 
                exportButton.style.cursor = "not-allowed";
            } else {
                exportButton.innerText = "⚠ Fehler!";
                exportButton.style.backgroundColor = "rgba(200,0,0,0.8)";
            }
        })
        .catch(err => {
            console.error(err);
            exportButton.innerText = "⚠ Fehler!";
            exportButton.style.backgroundColor = "rgba(200,0,0,0.8)";
        });
    });

    const animeUrl = getAnimeBaseUrl();
    fetch(`http://${SERVER_IP}:5050/check?url=${encodeURIComponent(animeUrl)}`)
        .then(response => response.json())
        .then(data => {
            if(data.exists) {
                exportButton.innerText = "✅ Gedownloaded!";
                exportButton.style.backgroundColor = "rgba(0,200,0,0.8)";
                exportButton.disabled = true; 
                exportButton.style.cursor = "not-allowed";
            }
        })
        .catch(err => console.error(err));

    buttonWrapper.appendChild(exportButton);
    streamContainer.insertAdjacentElement("afterend", buttonWrapper);
})();
