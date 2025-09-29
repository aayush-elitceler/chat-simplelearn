# Stage 1: Builder (installs all packages with CPU-only torch)
FROM python:3.11-slim AS builder

WORKDIR /install

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ git libffi-dev libjpeg-dev zlib1g-dev \
    libpq-dev libgl1 libsm6 libxext6 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirement file
COPY requirements.txt .

# Install with CPU-only PyTorch and no pip cache
RUN pip install --upgrade pip setuptools wheel \
    && pip install --prefix=/install-deps --no-cache-dir \
    -r requirements.txt \
    --extra-index-url https://download.pytorch.org/whl/cpu

# ------------------------------------------------------

# Stage 2: Minimal runtime image
FROM python:3.11-slim

LABEL description="Noui FastAPI app with torch CPU"

WORKDIR /app

# Install runtime system libraries (required by cv/image libraries)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg-dev zlib1g-dev libgl1 libsm6 libxext6 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy preinstalled Python packages
COPY --from=builder /install-deps /usr/local

# Copy app source code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
