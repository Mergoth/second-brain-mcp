# syntax=docker/dockerfile:1
FROM python:3.13-slim

# Install ripgrep — not available in slim base image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Non-root user. UID/GID are build args so they can match the vault owner on the NAS —
# a mismatch fails exactly the writes to the mode-600 files (Tasks.md, meta/log.md).
ARG UID=1000
ARG GID=1000
# The GID may already exist in the base image (Synology's `users` is 100, as is Debian's).
RUN (getent group "${GID}" >/dev/null || groupadd --gid "${GID}" mcp) \
    && useradd --create-home --uid "${UID}" --gid "${GID}" mcp

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

USER mcp
WORKDIR /home/mcp/app

# Dependencies first (cached layer), then the project itself. Non-editable so the venv does
# not depend on the source tree at runtime.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --chown=${UID}:${GID} pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-editable
COPY --chown=${UID}:${GID} src/ src/
RUN uv sync --frozen --no-dev --no-editable

# Run the venv interpreter directly. `uv run` needs a writable cache and cannot start on the
# read-only rootfs that compose enforces.
ENV PATH="/home/mcp/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

# /vault and /state are the only writable mount points.
VOLUME ["/vault", "/state"]

EXPOSE 8000

ENTRYPOINT ["python", "-m", "second_brain_mcp", "--transport", "http"]
