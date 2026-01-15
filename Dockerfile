# =============================================================================
# ChronoReel - Dockerfile for Cloud Run
# =============================================================================
# This container runs the video generation pipeline on GCP Cloud Run Jobs.
# It includes ffmpeg for MoviePy video processing.
# =============================================================================

FROM python:3.12-slim

# Install system dependencies for MoviePy/ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    imagemagick \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create output directory
RUN mkdir -p /app/output

# Environment variables (set via Cloud Run or GitHub Secrets)
# GOOGLE_API_KEY - Gemini API key
# FAL_KEY - Fal.ai API key
# GOOGLE_APPLICATION_CREDENTIALS - Path to service account JSON (mounted as secret)

# Default command: Run full pipeline for Timeline B channel
CMD ["python", "main.py", "--config", "configs/timeline_b.yaml"]
