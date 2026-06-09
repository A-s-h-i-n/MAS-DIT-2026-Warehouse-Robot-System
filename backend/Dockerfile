FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code.
COPY backend ./backend

# Persist the SQLite database on a mounted volume.
ENV WMS_DB_PATH=/app/data/warehouse.db
ENV WMS_HOST=0.0.0.0
ENV WMS_PORT=8000

EXPOSE 8000

CMD ["uvicorn", "backend.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
