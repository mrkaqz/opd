FROM python:3.12-slim

WORKDIR /app

# Install dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create data directory for SQLite database
RUN mkdir -p /app/data

# Environment defaults (override via docker-compose or -e flags)
ENV DB_PATH=/app/data/clinic.db
ENV AZURE_CLIENT_ID=""

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/visits?limit=1')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
