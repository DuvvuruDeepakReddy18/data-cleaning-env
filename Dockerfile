# Dockerfile for Data Cleaning Environment
# Deployable to Hugging Face Spaces (Docker SDK)

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the full project
COPY data_cleaning_env/ ./data_cleaning_env/
COPY pyproject.toml .
COPY openenv.yaml .
COPY README.md .
COPY inference.py .

# Install the package
RUN pip install --no-cache-dir -e .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV ENABLE_WEB_INTERFACE=true

# Expose port (HF Spaces expects 7860 by default, but we use 8000 with app_port)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the server
CMD ["uvicorn", "data_cleaning_env.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
