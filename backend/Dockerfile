FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    git \
    curl \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# CPU-only Torch first (EC2 has no GPU). Installing plain torch==2.1.0 from PyPI
# pulls ~GB of nvidia_* CUDA wheels and often fails mid-download (Broken pipe).
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --default-timeout=600 \
        torch==2.1.0+cpu \
        --index-url https://download.pytorch.org/whl/cpu \
    && grep -v -E '^torch==' requirements.txt > /tmp/requirements.no-torch.txt \
    && printf '%s\n' 'torch==2.1.0+cpu' > /tmp/constraints.txt \
    && pip install --no-cache-dir --default-timeout=600 \
        -c /tmp/constraints.txt \
        -r /tmp/requirements.no-torch.txt \
    && rm -f /tmp/requirements.no-torch.txt /tmp/constraints.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p uploads chroma_db models

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
