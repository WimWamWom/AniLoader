# Tampermonkey-Skript Setup-Anleitung

## 🎯 Zweck

Das Tampermonkey-Skript fügt einen "📤 Downloaden"-Button auf AniWorld.to und S.to Seiten hinzu, mit dem du Animes direkt zu AniLoader hinzufügen kannst.

## 📋 Voraussetzungen

1. **Browser-Extension installieren:**
   - Chrome/Edge: [Tampermonkey](https://www.tampermonkey.net/)
   - Firefox: [Tampermonkey](https://addons.mozilla.org/de/firefox/addon/tampermonkey/)

2. **AniLoader läuft** (lokal oder auf Server/Unraid)

## ⚙️ Installation

### Schritt 1: Skript installieren

1. Öffne Tampermonkey Dashboard
2. Klicke auf "Neues Skript erstellen"
3. Kopiere den Inhalt von `Tampermonkey.user.js`
4. **WICHTIG:** Passe die Konfiguration an (siehe unten)
5. Speichern (Strg+S)

### Schritt 2: Konfiguration anpassen

Im Skript findest du oben diese Zeilen:

```javascript
// 🌐 === SERVER KONFIGURATION ===
const SERVER_IP = "localhost";  // Bei Unraid: IP deines Servers
const SERVER_PORT = 5000;        // Standard-Port
```

**Passe diese Werte an deine Umgebung an:**

#### Lokaler PC (Windows/Mac/Linux)
```javascript
const SERVER_IP = "localhost";
const SERVER_PORT = 5000;
```

#### Unraid Server
```javascript
const SERVER_IP = "192.168.1.100";  // Ersetze mit deiner Unraid-IP!
const SERVER_PORT = 5000;
```

#### Anderer Port (wenn in config.json geändert)
```javascript
const SERVER_IP = "192.168.1.100";
const SERVER_PORT = 5050;  // Dein custom Port
```

### Schritt 3: Testen

1. Öffne eine Anime-Seite: `https://aniworld.to/anime/stream/demon-slayer`
2. Du solltest den Button "📤 Downloaden" oder "⛔ Server offline" sehen
3. Bei "Server offline":
   - Prüfe ob AniLoader läuft
   - Prüfe SERVER_IP und SERVER_PORT im Skript
   - Öffne Browser-Konsole (F12) für Fehler

## 🔧 Troubleshooting

### Problem: "⛔ Server offline" obwohl Server läuft

**Ursache:** Falsche IP/Port-Konfiguration

**Lösung:**

1. **Finde deine Server-IP:**
   ```bash
   # Unraid: Im Unraid-WebUI oben rechts
   # Linux/Mac:
   ip addr show | grep inet
   # Windows:
   ipconfig
   ```

2. **Prüfe den Port:**
   - Öffne `config.json` in deinem AniLoader-Datenordner
   - Suche nach `"port": 5000` oder einem anderen Wert
   - Nutze diesen Wert als `SERVER_PORT`

3. **Teste manuell im Browser:**
   ```
   http://192.168.1.100:5000/status
   ```
   - Ersetze IP und Port mit deinen Werten
   - Du solltest JSON mit Status sehen
   - Falls nicht: Server läuft nicht oder Firewall blockiert

### Problem: CORS-Fehler in Browser-Konsole

**Ursache:** Browser blockiert Cross-Origin-Requests

**Lösung:**
- AniLoader hat bereits CORS aktiviert
- Prüfe ob du HTTPS nutzt (sollte HTTP sein)
- Stelle sicher dass der Server erreichbar ist

### Problem: "Mixed Content" Warnung

**Ursache:** Du bist auf HTTPS-Seite (aniworld.to) und versuchst HTTP-Server zu erreichen

**Mögliche Lösungen:**

1. **Browser-Einstellung:** Erlaube "Unsichere Inhalte" für aniworld.to
2. **Reverse Proxy:** Nutze nginx/Caddy mit HTTPS für AniLoader
3. **Lokaler Proxy:** Nutze einen lokalen HTTPS-Proxy

### Problem: Button erscheint nicht

**Prüfe:**

1. Tampermonkey ist aktiviert
2. Skript ist aktiviert (grün im Dashboard)
3. Du bist auf einer unterstützten Seite:
   - `https://aniworld.to/anime/stream/*`
   - `https://s.to/serie/stream/*`
4. Browser-Konsole (F12) zeigt keine JavaScript-Fehler

## 📚 Button-Status erklärt

| Button-Text | Bedeutung | Klickbar |
|-------------|-----------|----------|
| 📤 Downloaden | Anime noch nicht in AniLoader | ✅ Ja |
| 📄 In der Liste | Bereits in AniLoader, noch nicht komplett | ❌ Nein |
| ⬇️ Downloaded | Wird gerade heruntergeladen | ❌ Nein |
| ✅ Gedownloaded | Download komplett | ❌ Nein |
| ⛔ Server offline | AniLoader nicht erreichbar | ❌ Nein |
| ⚠ Fehler! | Verbindungsfehler aufgetreten | ❌ Nein |

## 🔄 Auto-Update

Das Skript hat Auto-Update aktiviert:

```javascript
// @downloadURL  https://github.com/WimWamWom/AniLoader/raw/refs/heads/main/Tampermonkey.user.js
// @updateURL    https://github.com/WimWamWom/AniLoader/raw/refs/heads/main/Tampermonkey.user.js
```

**ABER:** Nach einem Update musst du die Konfiguration erneut anpassen!

**Empfehlung:** 
- Deaktiviere Auto-Update in Tampermonkey-Einstellungen
- ODER: Notiere deine Konfiguration und passe sie nach jedem Update an

## 🌐 Netzwerk-Konfiguration Beispiele

### Standard (Localhost)
```javascript
const SERVER_IP = "localhost";
const SERVER_PORT = 5000;
```
**Funktioniert nur wenn Browser und AniLoader auf demselben PC laufen!**

### Unraid im lokalen Netzwerk
```javascript
const SERVER_IP = "192.168.1.100";  // Deine Unraid IP
const SERVER_PORT = 5000;
```

### Docker mit Host-Netzwerk
```javascript
const SERVER_IP = "192.168.1.100";  // Host-IP
const SERVER_PORT = 5000;
```

### Docker mit Bridge-Netzwerk
```javascript
const SERVER_IP = "192.168.1.100";  // Host-IP
const SERVER_PORT = 5000;            // Mapped Port
```

### Tailscale/VPN
```javascript
const SERVER_IP = "100.64.1.2";     // Tailscale-IP
const SERVER_PORT = 5000;
```

## 🐛 Debug-Tipps

1. **Browser-Konsole öffnen (F12)**
   ```
   Network-Tab → Filtere nach "status"
   Siehst du einen Request?
   - Ja → Was ist die Response? (Status 200 = OK)
   - Nein → Server nicht erreichbar
   ```

2. **Teste Server manuell:**
   ```bash
   # PowerShell/Terminal:
   curl http://192.168.1.100:5000/status
   
   # Oder im Browser:
   http://192.168.1.100:5000/status
   ```

3. **Docker Logs prüfen:**
   ```bash
   docker logs aniloader | grep CORS
   ```

## 📝 Beispiel: Komplette Konfiguration

**Szenario:** Unraid-Server mit IP `192.168.178.50`, Standard-Port

```javascript
// ==UserScript==
// @name         AniWorld & S.to Download-Button
// ... (Rest bleibt gleich)
// ==/UserScript==

(function() {
    'use strict';

    // 🌐 === SERVER KONFIGURATION ===
    const SERVER_IP = "192.168.178.50";  // ← HIER ANPASSEN!
    const SERVER_PORT = 5000;             // ← HIER ANPASSEN FALLS NÖTIG!

    // ... (Rest des Skripts)
})();
```

## 🎓 Weiterführende Hilfe

- **GitHub Issues:** https://github.com/WimWamWom/AniLoader/issues
- **Tampermonkey Docs:** https://www.tampermonkey.net/documentation.php
