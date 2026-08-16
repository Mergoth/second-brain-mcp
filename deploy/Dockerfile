# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base

# Install ripgrep — not available in slim base image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Non-root user (UID 1000).
RUN useradd --create-home --uid 1000 mcp
USER mcp
WORKDIR /home/mcp/app

# Install uv and project dependencies.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source.
COPY src/ src/

# /vault is the only writable mount point.
VOLUME ["/vault"]

EXPOSE 8000

# Read-only rootfs is enforced by compose; the entrypoint only needs /vault
# and the uv cache (which is already under /home/mcp).
ENTRYPOINT ["uv", "run", "--frozen", "python", "-m", "second_brain_mcp", "--transport", "http"]
