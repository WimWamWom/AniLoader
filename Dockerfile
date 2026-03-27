# Multi-stage build: builder resolves Python deps and downloads patchright's Chromium,
# keeping those heavy layers separate from the lean runtime image.
FROM python:3.11-slim AS builder

WORKDIR /build

# Build-time tools: gcc for compiled extensions (lxml), git for VCS pip sources.
# Chromium runtime libs are NOT needed here — they belong in the final stage.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install patchright's Chromium to a fixed path so it can be COPY'd to the final stage.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

COPY requirements.txt .
# Cache-Buster: layer is rebuilt automatically when requirements.txt changes.
ARG REQUIREMENTS_HASH

# Install Python packages and patchright's patched Chromium (the only browser needed).
RUN pip install --no-cache-dir --user -r requirements.txt \
    && python -m patchright install chromium

RUN chmod -R 755 /ms-playwright

# ---------------------------------------------------------------------------
# Final image
# ---------------------------------------------------------------------------
FROM python:3.11-slim

LABEL maintainer="WimWamWom"
LABEL description="AniLoader – Anime & Serien Download-Manager"
LABEL org.opencontainers.image.title="AniLoader"
LABEL org.opencontainers.image.description="Anime & Serien Download-Manager mit Web-Interface"
LABEL org.opencontainers.image.url="https://github.com/WimWamWom/AniLoader"
LABEL org.opencontainers.image.source="https://github.com/WimWamWom/AniLoader"
LABEL org.opencontainers.image.vendor="WimWamWom"
LABEL net.unraid.docker.icon="https://raw.githubusercontent.com/WimWamWom/AniLoader/main/web/static/AniLoader.png"

WORKDIR /app

# ffmpeg: required by aniworld CLI for media muxing.
# curl: used by the Docker health check.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python packages installed in the builder stage.
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# patchright's patched Chromium binary from the builder stage.
COPY --from=builder /ms-playwright /ms-playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install Chromium's OS-level runtime dependencies (libnss3, libgbm1, etc.).
# Using patchright's own installer ensures the correct package names are used
# for whatever Debian/Ubuntu version this image is based on.
RUN patchright install-deps chromium

# Application code.
COPY main.py .
COPY app/ ./app/
COPY web/ ./web/

# Directories for persistent data.
RUN mkdir -p /app/data /app/Downloads /app/Anime /app/Serien /app/Anime-Filme /app/Serien-Filme

EXPOSE 5050

VOLUME ["/app/data", "/app/Downloads", "/app/Anime", "/app/Serien", "/app/Anime-Filme", "/app/Serien-Filme"]

ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5050/health || exit 1

CMD ["python", "main.py"]
