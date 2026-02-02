# Multi-stage build für kleineres Image
FROM python:3.11-slim AS builder

# Arbeitsverzeichnis erstellen
WORKDIR /app

# System-Abhängigkeiten installieren
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python-Abhängigkeiten kopieren
COPY requirements.txt .

# Cache-Break-Argument (wird vom CI bei jedem Build neu gesetzt)
ARG CACHE_BUST=1

# pip upgraden + Dependencies IMMER neu auflösen
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --upgrade --user -r requirements.txt


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
LABEL net.unraid.docker.icon="https://raw.githubusercontent.com/WimWamWom/AniLoader/main/static/AniLoader.png"

# Arbeitsverzeichnis erstellen
WORKDIR /app

# System-Tools installieren
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python-Pakete vom Builder kopieren
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Anwendungscode kopieren
COPY AniLoader.py .
COPY AniLoader.txt .
COPY static/ ./static/
COPY templates/ ./templates/

# Verzeichnisse für persistente Daten erstellen
RUN mkdir -p /app/data /app/Downloads

# Initiale config.json
RUN echo '{"languages": ["German Dub", "German Sub", "English Dub", "English Sub"], "min_free_gb": 2.0, "download_path": "", "autostart_mode": null, "refresh_titles": true, "storage_mode": "standard", "movies_path": "", "series_path": "", "anime_path": "/app/Downloads/Animes", "serien_path": "/app/Downloads/Serien", "anime_separate_movies": false, "serien_separate_movies": false, "data_folder_path": "", "server_port": 5000}' > /app/data/config.json.default

# Port freigeben
EXPOSE 5000

# Volumes
VOLUME ["/app/data", "/app/Downloads"]

# Umgebungsvariablen
ENV PYTHONUNBUFFERED=1

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Startbefehl
CMD ["python", "AniLoader.py"]
