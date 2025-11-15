# Multi-stage build für kleineres Image
FROM python:3.11-slim AS builder

# Arbeitsverzeichnis erstellen
WORKDIR /app

# System-Abhängigkeiten installieren
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python-Abhängigkeiten kopieren und installieren
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# aniworld-Downloader installieren
RUN pip install --no-cache-dir --user aniworld

# Finales Image
FROM python:3.11-slim

# Metadaten
LABEL maintainer="WimWamWom"
LABEL description="AniLoader - Anime Download Manager"
LABEL org.opencontainers.image.title="AniLoader"
LABEL org.opencontainers.image.description="Anime Download Manager mit Web-Interface"
LABEL org.opencontainers.image.url="https://github.com/WimWamWom/AniLoader"
LABEL org.opencontainers.image.source="https://github.com/WimWamWom/AniLoader"
LABEL org.opencontainers.image.vendor="WimWamWom"

# Arbeitsverzeichnis erstellen
WORKDIR /app

# System-Tools installieren (wget für Downloads)
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python-Pakete vom Builder kopieren
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Anwendungscode kopieren
COPY AniLoader.py .
COPY downloader.py .
COPY AniLoader.txt .
COPY static/ ./static/
COPY templates/ ./templates/

# Verzeichnisse für persistente Daten erstellen
RUN mkdir -p /app/data /app/Downloads

# Erstelle initiale config.json Template
RUN echo '{"languages": ["German Dub", "German Sub", "English Dub", "English Sub"], "min_free_gb": 2.0, "download_path": "", "autostart_mode": null, "refresh_titles": true, "storage_mode": "standard", "movies_path": "", "series_path": "", "data_folder_path": "", "server_port": 5000}' > /app/data/config.json.default

# Port freigeben (Standard: 5000, kann via config.json geändert werden)
EXPOSE 5000

# Volumes für persistente Daten
VOLUME ["/app/data", "/app/Downloads"]

# Umgebungsvariablen
ENV PYTHONUNBUFFERED=1

# Healthcheck hinzufügen
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Startbefehl
CMD ["python", "AniLoader.py"]
