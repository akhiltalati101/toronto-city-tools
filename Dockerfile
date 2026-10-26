# The scoring API (api/ + toronto_tools/). The React frontend deploys
# separately (see frontend/ and README.md).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Mount a persistent volume here so restarts don't re-download the
    # ~250 MB of release datasets.
    DATA_CACHE_DIR=/data

WORKDIR /app
COPY pyproject.toml ./
COPY toronto_tools ./toronto_tools
COPY api ./api
RUN pip install . && useradd --create-home app && mkdir -p /data && chown app /data
USER app

EXPOSE 8000
# --proxy-headers so per-IP rate limiting sees the client, not the load balancer.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
