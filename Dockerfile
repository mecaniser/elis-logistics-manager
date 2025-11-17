# Multi-stage build for FastAPI + React app
FROM node:18-alpine AS frontend-builder

# Build frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Python runtime stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Copy backend code
COPY backend/ ./backend/

# Copy startup script
COPY backend/start.sh ./backend/start.sh
RUN chmod +x ./backend/start.sh

# Set working directory to backend
WORKDIR /app/backend

# Expose port (Railway will set PORT env var at runtime)
EXPOSE 8000

# Start the application using exec form (best practice)
# PORT is read from environment by start.sh
# Use absolute path to ensure Railway finds the script
CMD ["/app/backend/start.sh"]

