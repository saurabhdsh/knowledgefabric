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
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Embedding model (all-MiniLM-L6-v2, ONNX) baked into the image so the first
# fabric does not depend on a download at runtime. Checksum-verified.
RUN mkdir -p /opt/weave/embeddings/all-MiniLM-L6-v2 \
    && curl -fsSL --retry 5 --retry-delay 5 \
        https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz \
        -o /tmp/onnx.tar.gz \
    && echo "913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3  /tmp/onnx.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/onnx.tar.gz -C /opt/weave/embeddings/all-MiniLM-L6-v2 \
    && rm -f /tmp/onnx.tar.gz \
    && test -f /opt/weave/embeddings/all-MiniLM-L6-v2/onnx/model.onnx

# Copy requirements first for better caching
COPY requirements.txt .

# CPU-only Torch first (EC2 has no GPU). Installing plain torch==2.1.0 from PyPI
# pulls ~GB of nvidia_* CUDA wheels and often fails mid-download (Broken pipe).
# x86_64 wheels on the CPU index are tagged "+cpu"; arm64 (Apple Silicon Docker)
# wheels are not, so fall back to the untagged version from the same index.
RUN pip install --upgrade pip \
    && (pip install --no-cache-dir --default-timeout=600 \
            torch==2.1.0+cpu \
            --index-url https://download.pytorch.org/whl/cpu \
        || pip install --no-cache-dir --default-timeout=600 \
            torch==2.1.0 \
            --index-url https://download.pytorch.org/whl/cpu) \
    && grep -v -E '^torch==' requirements.txt > /tmp/requirements.no-torch.txt \
    && printf 'torch==%s\n' "$(python -c 'import torch; print(torch.__version__)')" > /tmp/constraints.txt \
    && pip install --no-cache-dir --default-timeout=600 \
        -c /tmp/constraints.txt \
        -r /tmp/requirements.no-torch.txt \
    && rm -f /tmp/requirements.no-torch.txt /tmp/constraints.txt

# Copy application code
COPY . .

# Runtime user + gosu so the entrypoint can chown mounted volumes as root,
# then drop privileges before uvicorn starts.
RUN apt-get update && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p uploads chroma_db models data ontology_data /var/weave \
    && groupadd --system weave \
    && useradd --system --gid weave --home-dir /var/weave --shell /usr/sbin/nologin weave \
    && chown -R weave:weave /app /var/weave \
    && chmod +x /app/docker-entrypoint.sh

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=40s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Run the application (entrypoint chowns volumes, then gosu weave)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
