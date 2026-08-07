# syntax=docker/dockerfile:1.7

# =============================================================================
# IdentityDNA Protocol — Reference Server
#
# Multi-stage build:
#   1. base     — shared Python base, no secrets, minimal OS packages
#   2. builder  — installs dependencies into an isolated virtualenv
#   3. test     — runs the full unit test suite against the built venv;
#                 the image build FAILS if any test fails (CI-as-a-build-stage)
#   4. runtime  — final, minimal image: venv + app code only, non-root user
#
# Build:
#   docker build -t identitydna/reference-server:0.1.0-alpha .
#
# Run:
#   docker run -p 8000:8000 -v identitydna_data:/home/identitydna/.identitydna \
#     identitydna/reference-server:0.1.0-alpha
#
# This is a REFERENCE implementation (see reference/server/api.py docstring
# and SECURITY.md). It is not hardened for production traffic — no auth on
# debug endpoints, no rate limiting middleware. Treat accordingly.
# =============================================================================

ARG PYTHON_VERSION=3.12
ARG APP_HOME=/app
ARG APP_USER=identitydna
ARG APP_UID=10001


# -----------------------------------------------------------------------------
# Stage 1 — base
# -----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS base

# Fail fast, no interactive prompts, no .pyc clutter, unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Root CA certs (needed by pip/https at build time; harmless at runtime)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*


# -----------------------------------------------------------------------------
# Stage 2 — builder: build the venv in isolation from the final image
# -----------------------------------------------------------------------------
FROM base AS builder
ARG APP_HOME

WORKDIR ${APP_HOME}

# Build tooling only exists in this stage — never ships in the final image
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

# Dependency layer cached independently of application source changes
COPY reference/requirements.txt reference/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r reference/requirements.txt

# Now bring in the application source
COPY reference/ reference/
COPY cli/ cli/
COPY VERSION .


# -----------------------------------------------------------------------------
# Stage 3 — test: build-time quality gate. If this stage fails, `docker build`
# fails — a broken image can never be produced or pushed.
# -----------------------------------------------------------------------------
FROM builder AS test
ARG APP_HOME
WORKDIR ${APP_HOME}

COPY tests/unit/ tests/unit/

RUN pip install pytest>=8.0 \
    && python -m pytest tests/unit/ -v --tb=short


# -----------------------------------------------------------------------------
# Stage 4 — runtime: minimal final image
# -----------------------------------------------------------------------------
FROM base AS runtime
ARG APP_HOME
ARG APP_USER
ARG APP_UID

LABEL org.opencontainers.image.title="IdentityDNA Protocol — Reference Server" \
      org.opencontainers.image.description="Reference implementation of RFC-0001. Not for production use without independent security review." \
      org.opencontainers.image.authors="Ciprian Ștefan Pleșca <contact@agentflow-enterprise.com>" \
      org.opencontainers.image.source="https://github.com/Ciprian-LocalPulse/IdentityDNA-Protocol" \
      org.opencontainers.image.licenses="LicenseRef-IdentityDNA-Proprietary" \
      org.opencontainers.image.version="0.1.0-alpha"

# Explicit dependency on the test stage: this line has no runtime effect, but
# without it BuildKit may skip the `test` stage entirely as an unused build
# target. This COPY --from=test forces the test stage to actually execute
# (and therefore fail the build on any failing test) before runtime is built.
COPY --from=test ${APP_HOME}/reference/requirements.txt /tmp/.test-gate-passed

# Create an unprivileged, non-login user — the server never needs root
RUN groupadd --gid ${APP_UID} ${APP_USER} \
    && useradd --uid ${APP_UID} --gid ${APP_USER} --create-home --shell /usr/sbin/nologin ${APP_USER} \
    && mkdir -p /home/${APP_USER}/.identitydna \
    && chown -R ${APP_USER}:${APP_USER} /home/${APP_USER}

WORKDIR ${APP_HOME}

# Bring in the pre-built, already-tested venv and application code
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder ${APP_HOME}/reference/ reference/
COPY --from=builder ${APP_HOME}/cli/ cli/
COPY --from=builder ${APP_HOME}/VERSION .

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH="${APP_HOME}" \
    IDENTITYDNA_HOST=0.0.0.0 \
    IDENTITYDNA_PORT=8000 \
    HOME="/home/${APP_USER}"

USER ${APP_USER}

EXPOSE 8000

# Uses the real /health endpoint (reference/server/api.py) — no extra
# packages (curl) needed, keeping the final image lean and reducing CVE
# surface area.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
        sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=2).status == 200 else 1)"

WORKDIR ${APP_HOME}/reference/server

ENTRYPOINT ["uvicorn", "api:app"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
