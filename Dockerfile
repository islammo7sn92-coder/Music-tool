# Single-image deployment: builds the React app and serves it from FastAPI.
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsndfile1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
# CPU-only torch keeps the image small. For GPU use a CUDA base image / default PyPI wheels.
RUN pip install --no-cache-dir torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY --from=web /web/dist frontend/dist
ENV MODELS_DIR=/app/models UPLOADS_DIR=/app/uploads OUTPUTS_DIR=/app/outputs TEMP_DIR=/app/temp
# Bake the model into the image so the first request is fast
RUN python backend/scripts/download_model.py
EXPOSE 8000
WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
