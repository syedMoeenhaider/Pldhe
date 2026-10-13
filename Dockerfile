# Root Dockerfile — for Hugging Face Spaces (Docker SDK).
# HF expects a Dockerfile at the repo root and the app listening on $PORT (7860).
# (Render / docker-compose keep using ./backend/Dockerfile.)

FROM python:3.12-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app

EXPOSE 7860
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}
