FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Copy Excel file for one-time import (it stays in the image)
COPY "Patient List.xlsm" .

ENV DB_PATH=/app/data/clinic.db
ENV EXCEL_PATH=/app/Patient\ List.xlsm

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
