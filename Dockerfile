# ASILI HAWK — single-container deploy (Railway / Render / Fly / any Docker host)
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY --from=frontend /fe/dist ./frontend/dist
ENV PORT=8000
WORKDIR /app/backend
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
