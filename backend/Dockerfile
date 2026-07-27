FROM python:3.11-slim

WORKDIR /app

# Install deps first so the layer caches across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code (the trained model in artifacts/ ships with the image).
COPY . .

# SQLite audit trail lives on a mounted volume (see docker-compose.yml) so it
# survives container restarts; overridable with CLEARANCE_DB_URL.
ENV CLEARANCE_DB_URL=sqlite:////data/clearance.db
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
