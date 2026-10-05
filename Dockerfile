# --- Stage 1: build the frontend ---
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Stage 2: run the backend ---
FROM python:3.12-slim
WORKDIR /app
COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir \
    "fastapi>=0.115" "uvicorn[standard]>=0.32" "pymupdf>=1.24" "python-multipart>=0.0.12"
COPY backend/app ./app
COPY --from=frontend /frontend/dist ./frontend_dist
EXPOSE 8000
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
