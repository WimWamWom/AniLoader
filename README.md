<a id="readme-top"></a>

# AniLoader — Language selection

Choose your language / Wähle deine Sprache:

* [Deutsch](./README.de.md)
* [English](./README.en.md)

---

This repository now contains two full README files: `README.de.md` (German) and `README.en.md` (English).

Click the language you prefer above to open the full documentation in that language.

If you want the old single README restored, open `README.de.md` — it contains the original German content.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Debugging & Troubleshooting (häufige Fehler)

### Kein Download startet / aniworld: command not found
aniworld nicht installiert oder nicht in PATH. Installiere / passe run_download an.

### AniLoader.txt wird nicht eingelesen
Stelle sicher, dass AniLoader.txt im selben Ordner wie AniLoader.py liegt. Beim Start wird die Datenbank aktualisiert.

### Keine Logs im UI
/logs liefert die Log-Zeilen als JSON. Prüfe mit curl http://localhost:5050/logs. UI muss diese anzeigen.

### Server wird beim Seiten-Reload neu gestartet
Das Skript läuft als normaler Flask-Prozess. Wenn du im Entwickler-Modus (debug=True) startest, kann der Reloader Threads neu starten. In deinem Code ist debug=False, das ist gut — Threads überleben Seitenreloads nicht automatisch, aber hier ist der Server persistent.

### Datenbank-Inkonsistenzen
SQLite Datei AniLoader.db kannst du mit sqlite3 AniLoader.db öffnen. Backup machen bevor du Änderungen vornimmst.

### Remote Zugriff / Firewall
Standardmäßig host="0.0.0.0" heißt erreichbar von Außen. Setze Firewall/Router-Portforwarding wenn nötig. Achtung: unsicher, wenn öffentlich zugänglich — siehe Sicherheitsabschnitt.


<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Lizenz

Dieses Projekt ist unter der [MIT-Lizenz](https://github.com/WimWamWom/AniLoader/blob/main/LICENSE) lizenziert. </br>
Genauer Informatoinen stehen in der LICENSE-Datei.
<p align="right">(<a href="#readme-top">back to top</a>)</p>
