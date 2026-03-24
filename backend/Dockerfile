FROM public.ecr.aws/docker/library/python:3.11-slim

WORKDIR /app

# Ensure PyTorch can find NVIDIA runtime libraries injected by ECS GPU
ENV PATH /usr/local/nvidia/bin:/usr/local/cuda/bin:${PATH}
ENV LD_LIBRARY_PATH /usr/local/nvidia/lib:/usr/local/nvidia/lib64
# System deps for RDKit + build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxrender1 \
    libxext6 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps - full PyTorch with GPU support
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ app/

# Create data directory
RUN mkdir -p /tmp/polypred_data /tmp/polypred_models

# Copy benchmark models weights
COPY Specific_Models_Final/ /Specific_Models_Final/

# Health check - longer timeout for heavy ML operations
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=5 \
  CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# 2 workers: one can serve health checks while another processes ML requests
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
