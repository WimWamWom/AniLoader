# Docker Hub Upload Checkliste

## ✅ Vorbereitungen getroffen:

### 1. Dockerfile optimiert
- ✅ Multi-stage build für kleineres Image
- ✅ `aniworld` CLI-Tool installiert (WICHTIG!)
- ✅ Alle Python-Dependencies aus requirements.txt
- ✅ System-Tools: wget, curl
- ✅ Volumes für /app/data und /app/Downloads
- ✅ Health Check implementiert
- ✅ Default config.json Template erstellt
- ✅ Port 5000 exponiert

### 2. Docker Compose
- ✅ Version 3.8
- ✅ Alle notwendigen Volumes
- ✅ Restart policy
- ✅ Health Check

### 3. .dockerignore
- ✅ Python-Cache ausschließen
- ✅ Git-Dateien ausschließen
- ✅ Data/Downloads Verzeichnisse ausschließen
- ✅ IDE-Dateien ausschließen

### 4. Dokumentation
- ✅ DOCKER_README.md für Docker Hub
- ✅ DOCKER_ANLEITUNG.md für Nutzer
- ✅ GitHub Actions Workflow für automatische Builds

## 🚀 Upload zu Docker Hub - Manuelle Methode:

### Schritt 1: Docker Hub Account
1. Registriere dich bei https://hub.docker.com
2. Notiere deinen Username (z.B. `wimwamwom`)

### Schritt 2: Repository erstellen
1. Gehe zu https://hub.docker.com/repositories
2. Klicke "Create Repository"
3. Name: `aniloader`
4. Visibility: Public (oder Private)
5. Description: "Anime Download Manager mit Web-Interface"

### Schritt 3: Image bauen und hochladen

**Auf Windows (PowerShell):**
```powershell
# 1. Zum Projektverzeichnis wechseln
cd "c:\Users\roehn\Documents\Git Hub\AniLoader"

# 2. Image bauen (WICHTIG: mit --no-cache für frischen Build)
docker build --no-cache -t wimwamwom/aniloader:latest .

# 3. Test lokal (optional)
docker run -d -p 5000:5000 -v ${PWD}/data:/app/data -v ${PWD}/Downloads:/app/Downloads --name test-aniloader wimwamwom/aniloader:latest
# Browser öffnen: http://localhost:5000
# Testen ob Upload funktioniert
# Testen ob Download funktioniert (aniworld muss funktionieren!)
docker stop test-aniloader; docker rm test-aniloader

# 4. Bei Docker Hub einloggen
docker login
# Username: wimwamwom (oder dein Username)
# Password: (dein Passwort oder Token)

# 5. Image hochladen
docker push wimwamwom/aniloader:latest

# 6. Optional: Version-Tag erstellen
docker tag wimwamwom/aniloader:latest wimwamwom/aniloader:v1.0.0
docker push wimwamwom/aniloader:v1.0.0
```

### Schritt 4: Description auf Docker Hub aktualisieren
1. Gehe zu https://hub.docker.com/r/wimwamwom/aniloader
2. Klicke auf "Edit"
3. Kopiere den Inhalt von `DOCKER_README.md` in das Description-Feld
4. Speichern

## 🤖 Upload zu Docker Hub - Automatische Methode (GitHub Actions):

### Voraussetzungen:
1. **GitHub Repository ist öffentlich** oder du hast GitHub Actions aktiviert

2. **Docker Hub Token erstellen:**
   - Gehe zu https://hub.docker.com/settings/security
   - Klicke "New Access Token"
   - Name: `GitHub Actions`
   - Permissions: `Read, Write, Delete`
   - Token kopieren und sicher aufbewahren!

3. **GitHub Secrets einrichten:**
   - Gehe zu deinem GitHub Repo: https://github.com/WimWamWom/AniLoader
   - Settings → Secrets and variables → Actions
   - Klicke "New repository secret"
   - Füge hinzu:
     - Name: `DOCKER_HUB_USERNAME`, Value: `wimwamwom`
     - Name: `DOCKER_HUB_TOKEN`, Value: `<dein-token-von-schritt-2>`

4. **Workflow triggern:**
   ```powershell
   # Code committen und pushen
   git add .
   git commit -m "Add Docker support with aniworld CLI"
   git push origin main
   ```
   
   Oder für Version-Tag:
   ```powershell
   git tag v1.0.0
   git push origin v1.0.0
   ```

5. **Build-Status prüfen:**
   - Gehe zu https://github.com/WimWamWom/AniLoader/actions
   - Der Workflow "Docker Build and Push" sollte laufen
   - Nach Erfolg: Image ist auf Docker Hub verfügbar

## 🔍 Verifikation nach Upload:

### Test auf lokalem System:
```powershell
# Image von Docker Hub ziehen
docker pull wimwamwom/aniloader:latest

# Container starten
docker run -d -p 5000:5000 -v ${PWD}/data:/app/data -v ${PWD}/Downloads:/app/Downloads --name aniloader wimwamwom/aniloader:latest

# Logs prüfen
docker logs -f aniloader

# Testen im Browser
# http://localhost:5000

# Wichtig: TXT Upload testen
# Wichtig: Download testen (aniworld muss funktionieren!)

# Cleanup
docker stop aniloader; docker rm aniloader
```

### Test auf Unraid:
1. Docker Tab → Add Container
2. Repository: `wimwamwom/aniloader:latest`
3. Port 5000:5000 mappen
4. Volumes einrichten:
   - `/mnt/user/appdata/aniloader/data` → `/app/data`
   - `/mnt/user/Downloads/AniLoader` → `/app/Downloads`
5. Container starten
6. Im Browser öffnen: `http://<unraid-ip>:5000`
7. **Kritischer Test:** Download starten und prüfen ob `aniworld` funktioniert!

## 📋 Wichtige Checks vor dem Upload:

- [ ] Dockerfile enthält `RUN pip install --no-cache-dir --user aniworld`
- [ ] requirements.txt ist vollständig
- [ ] Alle statischen Dateien (templates/, static/) werden kopiert
- [ ] .dockerignore schließt unnötige Dateien aus
- [ ] Health Check funktioniert
- [ ] Volumes sind korrekt definiert
- [ ] Port 5000 ist exponiert
- [ ] Image wurde lokal getestet
- [ ] TXT Upload wurde getestet
- [ ] Download mit aniworld wurde getestet
- [ ] DOCKER_README.md ist aktuell

## 🎯 Nach erfolgreichem Upload:

1. **README.md aktualisieren:**
   - Docker Installation Anleitung hinzufügen
   - Badge für Docker Hub hinzufügen

2. **GitHub Release erstellen:**
   - Tag: v1.0.0
   - Beschreibung der Änderungen
   - Link zum Docker Hub Image

3. **Unraid Community Apps (optional):**
   - Template für Unraid Community Apps erstellen
   - Siehe: https://github.com/Squidly271/docker-templates

## ❗ Häufige Fehler vermeiden:

1. **aniworld nicht installiert** → Container-Logs zeigen: `No such file or directory: 'aniworld'`
   - Lösung: Dockerfile prüfen, Build mit --no-cache wiederholen

2. **Volume-Permissions** → Download schlägt fehl
   - Lösung: Host-Verzeichnisse mit korrekten Rechten erstellen

3. **Port bereits belegt** → Container startet nicht
   - Lösung: Anderen Host-Port verwenden (z.B. 5001:5000)

4. **Keine Netzwerkverbindung** → Downloads schlagen fehl
   - Lösung: Docker Network Typ auf "bridge" setzen

## 📞 Support:

Bei Problemen:
- GitHub Issues: https://github.com/WimWamWom/AniLoader/issues
- Docker Hub: https://hub.docker.com/r/wimwamwom/aniloader
