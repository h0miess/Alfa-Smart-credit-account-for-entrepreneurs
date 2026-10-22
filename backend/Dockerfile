FROM python:3.12.13-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /uvx /bin/

ARG uid=5055
ARG WORKDIR=/app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=$WORKDIR/src


ENV UV_PROJECT_ENVIRONMENT=/usr/local

WORKDIR $WORKDIR

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY src ./src/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

USER $uid
