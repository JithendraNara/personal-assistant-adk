FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Copy application first (needed for pip install to find the package)
COPY . .

# Install Python deps
RUN pip install --upgrade pip \
    && pip install .

# Create app user and runtime directories
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/data/uploads \
    && chown -R appuser:appuser /app

USER appuser

# Run the API server
ENV PORT=8080 \
    HOST=0.0.0.0

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; p=os.getenv('PORT','8080'); urllib.request.urlopen('http://127.0.0.1:'+p+'/health', timeout=3)"

CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8080"]
