# Multi-stage build für kleineres Image
FROM python:3.11-slim AS builder

WORKDIR /build

# System-Abhängigkeiten für pip install
RUN apt-get update && apt-get install -y \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Cache-Buster: ändert sich automatisch wenn requirements.txt geändert wird
ARG REQUIREMENTS_HASH
RUN pip install --no-cache-dir --user -r requirements.txt


# Finales Image
FROM python:3.11-slim

LABEL maintainer="WimWamWom"
LABEL description="AniLoader – Anime & Serien Download-Manager"
LABEL org.opencontainers.image.title="AniLoader"
LABEL org.opencontainers.image.description="Anime & Serien Download-Manager mit Web-Interface"
LABEL org.opencontainers.image.url="https://github.com/WimWamWom/AniLoader"
LABEL org.opencontainers.image.source="https://github.com/WimWamWom/AniLoader"
LABEL org.opencontainers.image.vendor="WimWamWom"
LABEL net.unraid.docker.icon="https://raw.githubusercontent.com/WimWamWom/AniLoader/main/static/AniLoader.png"

WORKDIR /app

# ffmpeg + curl für Health-Check + chromium für nodriver CF-Bypass-Fallback
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    chromium \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Python-Pakete vom Builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Anwendungscode kopieren
COPY main.py .
COPY app/ ./app/
COPY web/ ./web/

# Verzeichnisse für persistente Daten
RUN mkdir -p /app/data /app/Downloads /app/Anime /app/Serien /app/Anime-Filme /app/Serien-Filme

EXPOSE 5050

VOLUME ["/app/data", "/app/Downloads", "/app/Anime", "/app/Serien", "/app/Anime-Filme", "/app/Serien-Filme"]

ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5050/health || exit 1

CMD ["python", "main.py"]
