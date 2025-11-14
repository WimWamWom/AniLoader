# AniLoader Docker Anleitung

## Voraussetzungen
- Docker Desktop (Windows) oder Docker Engine (Linux/Unraid)
- Git (optional, zum Klonen des Repositories)

## Schritt 1: Docker Image erstellen

### Auf Windows (lokal testen):
```powershell
# Navigiere zum Projektverzeichnis
cd "c:\Users\roehn\Documents\Git Hub\AniLoader"

# Baue das Docker Image
docker build -t aniloader:latest .
```

### Optional: Image testen
```powershell
# Starte Container zum Testen
docker run -d -p 5000:5000 -v ${PWD}/data:/app/data -v ${PWD}/Downloads:/app/Downloads --name aniloader-test aniloader:latest

# Öffne Browser: http://localhost:5000
# Stoppe Container nach Test
docker stop aniloader-test
docker rm aniloader-test
```

## Schritt 2: Image für Unraid vorbereiten

### Option A: Docker Hub verwenden (empfohlen)

1. **Erstelle einen Docker Hub Account** (falls noch nicht vorhanden):
   - Gehe zu https://hub.docker.com
   - Registriere dich kostenlos

2. **Tag das Image**:
   ```powershell
   # Ersetze "deinusername" mit deinem Docker Hub Username
   docker tag aniloader:latest deinusername/aniloader:latest
   ```

3. **Login bei Docker Hub**:
   ```powershell
   docker login
   # Gib Username und Passwort ein
   ```

4. **Push das Image zu Docker Hub**:
   ```powershell
   docker push deinusername/aniloader:latest
   ```

### Option B: Image als Datei exportieren

```powershell
# Exportiere Image als TAR-Datei
docker save -o aniloader.tar aniloader:latest

# Kopiere aniloader.tar zu deinem Unraid Server (z.B. via SMB oder SCP)
```

## Schritt 3: In Unraid installieren

### Via Docker Hub (Option A):

1. Öffne das **Unraid WebUI**
2. Gehe zu **Docker** Tab
3. Klicke auf **Add Container**
4. Fülle folgende Felder aus:

   **Basic Settings:**
   - Name: `aniloader`
   - Repository: `deinusername/aniloader:latest`
   - Network Type: `bridge`

   **Port Mappings:**
   - Container Port: `5000`
   - Host Port: `5000` (oder einen anderen freien Port)
   - Connection Type: `TCP`

   **Volume Mappings:**
   
   Path 1 (Data):
   - Container Path: `/app/data`
   - Host Path: `/mnt/user/appdata/aniloader/data`
   - Access Mode: `Read/Write`
   
   Path 2 (Downloads):
   - Container Path: `/app/Downloads`
   - Host Path: `/mnt/user/Downloads/AniLoader` (oder dein gewünschter Pfad)
   - Access Mode: `Read/Write`
   
   Optional - Path 3 (Filme, nur bei separate mode):
   - Container Path: `/movies`
   - Host Path: `/mnt/user/Movies` (dein Filme-Verzeichnis)
   - Access Mode: `Read/Write`
   
   Optional - Path 4 (Serien, nur bei separate mode):
   - Container Path: `/series`
   - Host Path: `/mnt/user/TV Shows` (dein Serien-Verzeichnis)
   - Access Mode: `Read/Write`

5. Klicke auf **Apply**

### Via TAR-Import (Option B):

1. Kopiere `aniloader.tar` nach `/mnt/user/appdata/` auf deinem Unraid Server
2. Öffne die Unraid Terminal Konsole
3. Importiere das Image:
   ```bash
   docker load -i /mnt/user/appdata/aniloader.tar
   ```
4. Folge dann den Schritten von Option A ab Punkt 1

## Schritt 4: Container konfigurieren

1. Nach dem Start öffne: `http://UNRAID-IP:5000`
2. Gehe zu den Einstellungen in der Web-UI
3. Konfiguriere:
   - Download-Pfad (Standard: `/app/Downloads`)
   - Bei **separate mode**: 
     - Filme-Pfad: `/movies`
     - Serien-Pfad: `/series`
   - Port, Threads, etc.

## Wichtige Hinweise

### Pfade in der Konfiguration:
- Verwende **Container-Pfade** in der config.json, nicht Host-Pfade
- Standard Downloads: `/app/Downloads`
- Separate Filme: `/movies`
- Separate Serien: `/series`

### Datenbank und Konfiguration:
- Die Datenbank (`anime.db`) wird in `/app/data` gespeichert
- Die Konfiguration (`config.json`) wird in `/app/data` gespeichert
- Diese bleiben auch bei Container-Neustart erhalten

### Updates:
```powershell
# Auf Windows: Neues Image bauen
docker build -t aniloader:latest .
docker tag aniloader:latest deinusername/aniloader:latest
docker push deinusername/aniloader:latest

# Auf Unraid: Container stoppen, Image updaten, neu starten
# Via WebUI: Force Update klicken
# Oder Terminal:
docker pull deinusername/aniloader:latest
docker stop aniloader
docker rm aniloader
# Dann Container neu erstellen via WebUI
```

### Troubleshooting:

**Container startet nicht:**
```bash
# Logs ansehen
docker logs aniloader
```

**Keine Downloads möglich:**
- Prüfe Volume-Mappings
- Prüfe Schreibrechte: `chmod -R 777 /mnt/user/Downloads/AniLoader`

**Webinterface nicht erreichbar:**
- Prüfe Port-Mapping
- Prüfe Firewall-Einstellungen
- Prüfe ob Port in config.json mit Container-Port übereinstimmt

**Permission-Probleme:**
```bash
# Auf Unraid Terminal
chown -R nobody:users /mnt/user/appdata/aniloader
chmod -R 777 /mnt/user/appdata/aniloader
```

## Alternative: docker-compose auf Unraid

Falls du docker-compose verwenden möchtest (benötigt zusätzliches Plugin):

1. Installiere **Compose Manager** Plugin via Community Applications
2. Kopiere `docker-compose.yml` nach `/mnt/user/appdata/aniloader/`
3. Passe Pfade in der yml an
4. Starte via Compose Manager

## Erweiterte Konfiguration

### Eigenes Unraid Template erstellen:

Erstelle eine XML-Datei für einfachere Installation:

```xml
<?xml version="1.0"?>
<Container version="2">
  <Name>aniloader</Name>
  <Repository>deinusername/aniloader:latest</Repository>
  <Registry>https://hub.docker.com/r/deinusername/aniloader/</Registry>
  <Network>bridge</Network>
  <Privileged>false</Privileged>
  <Support>https://github.com/WimWamWom/AniLoader</Support>
  <Project>https://github.com/WimWamWom/AniLoader</Project>
  <Overview>AniLoader - Anime Download Manager mit Web-Interface</Overview>
  <Category>Downloaders: Status:Stable</Category>
  <WebUI>http://[IP]:[PORT:5000]</WebUI>
  <Icon>https://raw.githubusercontent.com/WimWamWom/AniLoader/main/static/icon.png</Icon>
  <Config Name="WebUI Port" Target="5000" Default="5000" Mode="tcp" Description="Port für Web-Interface" Type="Port" Display="always" Required="true" Mask="false">5000</Config>
  <Config Name="Data" Target="/app/data" Default="/mnt/user/appdata/aniloader/data" Mode="rw" Description="Datenbank und Konfiguration" Type="Path" Display="always" Required="true" Mask="false">/mnt/user/appdata/aniloader/data</Config>
  <Config Name="Downloads" Target="/app/Downloads" Default="/mnt/user/Downloads/AniLoader" Mode="rw" Description="Download-Verzeichnis" Type="Path" Display="always" Required="true" Mask="false">/mnt/user/Downloads/AniLoader</Config>
  <Config Name="Movies (optional)" Target="/movies" Default="" Mode="rw" Description="Filme-Verzeichnis (nur für separate mode)" Type="Path" Display="advanced" Required="false" Mask="false"></Config>
  <Config Name="Series (optional)" Target="/series" Default="" Mode="rw" Description="Serien-Verzeichnis (nur für separate mode)" Type="Path" Display="advanced" Required="false" Mask="false"></Config>
</Container>
```

Speichere diese als `/boot/config/plugins/dockerMan/templates-user/aniloader.xml` auf Unraid.

## Nützliche Docker Befehle

```bash
# Container Status
docker ps -a | grep aniloader

# Logs anzeigen
docker logs -f aniloader

# In Container einsteigen
docker exec -it aniloader /bin/bash

# Container neu starten
docker restart aniloader

# Image neu bauen (nach Code-Änderungen)
docker build --no-cache -t aniloader:latest .

# Speicherplatz aufräumen
docker system prune -a
```
