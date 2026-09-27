FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY backend/ .

# Render injects $PORT dynamically; default to 8000 for local Docker usage
ENV PORT=8000

EXPOSE $PORT

# Production: no --reload; use shell form so $PORT expands correctly
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2
