# Stage 1: Build frontend
FROM node:25-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ .
RUN npm run build

# Stage 2: Runtime
FROM python:3.13-slim

ARG BUILD_VERSION="dev"

# https://github.com/kovidgoyal/calibre/releases
ARG CALIBRE_VERSION="9.10.0"
ARG CALIBRE_SHA_AMD64="c089140a43368db2ac3abe01a6f5841e6b8e0a034669a3611751011e4350b8a6"
ARG CALIBRE_SHA_ARM64="270bfc903b7e5b4d89446b13ec674afe6a385650e9f8ff09208d142b31d2ff48"
# https://github.com/jgm/pandoc/releases
ARG PANDOC_VERSION="3.10"
ARG PANDOC_SHA_AMD64="e0f8af62d0f267d22baa5bcefe6d5dda3a097ccc60de794b759fe03159923244"
ARG PANDOC_SHA_ARM64="55413dfb0c1aec861641fe858f1f73e84848f3db497b1c0c02e62887ea76f4a4"
# https://github.com/jgraph/drawio-desktop/releases
ARG DRAWIO_VERSION="30.2.6"
ARG DRAWIO_SHA_AMD64="2a4e44b931e39bdb76d5acc3b2d097aa26c6bf95812e4cc14cb40fcba0265aae"
ARG DRAWIO_SHA_ARM64="9bac7a6daa13dcb240547100179076e5e240674d0f145cbd5db33692bcc36dee"

# Set working directory
WORKDIR /app

ENV APP_VERSION=$BUILD_VERSION
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
# Headless OpenGL: pyrender renders meshes offscreen via OSMesa (software Mesa).
ENV PYOPENGL_PLATFORM=osmesa

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
# pyrender hard-pins PyOpenGL==3.1.0, but its OSMesa backend imports
# OSMesaCreateContextAttribs, which only exists in PyOpenGL>=3.1.6. Override the
# pin (--no-deps so nothing else is touched, --force-reinstall to replace 3.1.0).
RUN pip install --no-cache-dir --no-deps --force-reinstall "PyOpenGL==3.1.7"

# Install additional system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    ghostscript \
    inkscape \
    tesseract-ocr \
    libsm6 \
    libxext6 \
    libopengl0 \
    libosmesa6 \
    libmagic1 \
    wget \
    xvfb \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libcairo2 \
    librsvg2-bin \
    tar \
    xz-utils \
    unrar-free \
    libreoffice-impress \
    libreoffice-common \
    && rm -rf /var/lib/apt/lists/*

RUN printf '%s\n' \
    '#!/bin/sh' \
    'set -eu' \
    'expected_sha="$1"' \
    'artifact_path="$2"' \
    'artifact_name="$3"' \
    '[ -n "$expected_sha" ] || { echo "Missing SHA256 for ${artifact_name}" >&2; exit 1; }' \
    'echo "${expected_sha}  ${artifact_path}" | sha256sum -c -' \
    > /usr/local/bin/verify-sha256 && \
    chmod +x /usr/local/bin/verify-sha256

# Inkscape's EPS import extension (ps_input.py) requires numpy and lxml
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3-numpy \
    python3-lxml \
    python3-tinycss2 \
    python3-cssselect \
    && rm -rf /var/lib/apt/lists/*

# Install Pandoc from upstream GitHub releases to avoid stale distro packages.
RUN ARCH="${TARGETARCH:-$(dpkg --print-architecture)}" && \
    case "$ARCH" in \
            amd64) PANDOC_ARCH="amd64"; PANDOC_SHA="$PANDOC_SHA_AMD64" ;; \
            arm64) PANDOC_ARCH="arm64"; PANDOC_SHA="$PANDOC_SHA_ARM64" ;; \
      *) echo "Unsupported architecture for pandoc: $ARCH" >&2; exit 1 ;; \
    esac && \
    PANDOC_URL="https://github.com/jgm/pandoc/releases/download/${PANDOC_VERSION}/pandoc-${PANDOC_VERSION}-linux-${PANDOC_ARCH}.tar.gz" && \
    wget --tries=3 --waitretry=5 --retry-connrefused \
            "$PANDOC_URL" -O /tmp/pandoc.tar.gz && \
        /usr/local/bin/verify-sha256 "$PANDOC_SHA" /tmp/pandoc.tar.gz pandoc && \
    tar -xzf /tmp/pandoc.tar.gz -C /tmp && \
    cp /tmp/pandoc-${PANDOC_VERSION}/bin/pandoc /usr/local/bin/pandoc && \
    chmod +x /usr/local/bin/pandoc && \
    rm -rf /tmp/pandoc.tar.gz /tmp/pandoc-${PANDOC_VERSION}


# Install Draw.io from upstream GitHub releases to avoid stale distro packages.
RUN ARCH="${TARGETARCH:-$(dpkg --print-architecture)}" && \
    case "$ARCH" in \
            amd64) DRAWIO_ARCH="amd64"; DRAWIO_SHA="$DRAWIO_SHA_AMD64" ;; \
            arm64) DRAWIO_ARCH="arm64"; DRAWIO_SHA="$DRAWIO_SHA_ARM64" ;; \
      *) echo "Unsupported architecture for drawio: $ARCH" >&2; exit 1 ;; \
    esac && \
    DRAWIO_URL="https://github.com/jgraph/drawio-desktop/releases/download/v${DRAWIO_VERSION}/drawio-${DRAWIO_ARCH}-${DRAWIO_VERSION}.deb"; \
    wget --tries=3 --waitretry=5 --retry-connrefused \
            "$DRAWIO_URL" -O /tmp/drawio.deb && \
        /usr/local/bin/verify-sha256 "$DRAWIO_SHA" /tmp/drawio.deb drawio && \
    apt-get update && apt-get install -y /tmp/drawio.deb && \
    rm /tmp/drawio.deb && \
    rm -rf /var/lib/apt/lists/*

# Install Calibre from official download site to avoid stale distro packages.
RUN ARCH="${TARGETARCH:-$(dpkg --print-architecture)}" && \
    case "$ARCH" in \
            amd64) CALIBRE_ARCH="x86_64"; CALIBRE_SHA="$CALIBRE_SHA_AMD64" ;; \
            arm64) CALIBRE_ARCH="arm64"; CALIBRE_SHA="$CALIBRE_SHA_ARM64" ;; \
      *) echo "Unsupported architecture for calibre: $ARCH" >&2; exit 1 ;; \
    esac && \
    CALIBRE_URL="https://download.calibre-ebook.com/${CALIBRE_VERSION}/calibre-${CALIBRE_VERSION}-${CALIBRE_ARCH}.txz" && \
    wget --tries=3 --waitretry=5 --retry-connrefused \
            "$CALIBRE_URL" -O /tmp/calibre.txz && \
        /usr/local/bin/verify-sha256 "$CALIBRE_SHA" /tmp/calibre.txz calibre && \
    mkdir -p /opt/calibre && \
    tar -xJf /tmp/calibre.txz -C /opt/calibre && \
    ln -sf /opt/calibre/ebook-convert /usr/bin/ebook-convert && \
    rm -f /tmp/calibre.txz

# Security patches: upgrade vulnerable packages to patched versions
RUN apt-get update && \
    apt-get install -y --only-upgrade \
    libnss3 \
    && apt-get purge -y \
    imagemagick \
    imagemagick-7-common \
    libmagickcore-7.q16-10 \
    libmagickcore-7.q16-10-extra \
    libmagickwand-7.q16-10 \
    && rm -rf /var/lib/apt/lists/*

# Copy backend code
COPY backend/ ./backend/

# Remove tests from backend to reduce image size
RUN rm -rf /app/backend/tests

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Copy entrypoint script with executable permission
COPY --chmod=755 docker/entrypoint.sh /app/entrypoint.sh

# Ensure copied application files are always traversable/readable regardless of host umask.
RUN chmod -R a+rX /app/backend /app/frontend

# Expose port
EXPOSE 3313

# Start the application
ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]

# Image metadata (OCI labels)
ARG BUILD_DATE=""
ARG VCS_REF=""
LABEL org.opencontainers.image.title="Transmute"
LABEL org.opencontainers.image.description="Convert anything, anywhere. Self hosted file converter for images, video, audio, json, excel and more!"
LABEL org.opencontainers.image.source="https://github.com/transmute-app/transmute"
LABEL org.opencontainers.image.url="https://github.com/transmute-app/transmute"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.version="$BUILD_VERSION"
LABEL org.opencontainers.image.revision="$VCS_REF"
LABEL org.opencontainers.image.created="$BUILD_DATE"
LABEL description="Convert anything, anywhere. Self hosted file converter for images, video, audio, json, excel and more!"
