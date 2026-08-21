FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOT_LIST_DATABASE_URL=sqlite+aiosqlite:////app/data/hot_list.db \
    HOT_LIST_DEBUG=false

WORKDIR /app

RUN addgroup --system hotlist \
    && adduser --system --ingroup hotlist --home /app hotlist

COPY pyproject.toml README.md main.py ./
COPY database ./database
COPY services ./services
COPY spider ./spider
COPY tools ./tools
COPY web ./web

RUN python -m pip install --upgrade pip \
    && python -m pip install . \
    && mkdir -p /app/data \
    && chown -R hotlist:hotlist /app

USER hotlist

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=3).read()" || exit 1

CMD ["python", "-m", "uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "1"]
