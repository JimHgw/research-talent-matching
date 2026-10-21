FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_SKIP_DOTENV=1 \
    FLASK_DEBUG=0

WORKDIR /app

COPY backend/requirements.txt backend/requirements-docker.txt ./backend/
RUN python -m pip install --no-cache-dir -r backend/requirements-docker.txt

COPY backend/__init__.py backend/app.py ./backend/
COPY backend/src/ ./backend/src/
COPY backend/docker/ ./backend/docker/
COPY docs/api/openapi.json ./docs/api/openapi.json
COPY docs/api/examples/tags.json ./docs/api/examples/tags.json

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/data \
    && chown app:app /app/data

USER app
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).close()"]

ENTRYPOINT ["sh", "/app/backend/docker/entrypoint.sh"]
# The runtime user has no home directory; a control socket is not needed here.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--worker-class", "gthread", "--threads", "4", "--no-control-socket", "--access-logfile", "-", "--error-logfile", "-", "backend.app:create_app()"]
