# syntax=docker/dockerfile:1.7

# ============================================================================
# Build arguments
#   CUDA_VERSION    — base image CUDA version.
#   UBUNTU_VERSION  — base OS. 24.04 ships Python 3.12 (sglang-omni requires >=3.12).
#   TORCH_CUDA_TAG  — PyTorch wheel index tag matching CUDA_VERSION.
#   TORCH_VERSION   — PyTorch version pinned to sglang-omni requirement.
# ============================================================================
ARG CUDA_VERSION=12.8.0
ARG UBUNTU_VERSION=24.04
ARG TORCH_VERSION=2.9.1
ARG TORCH_CUDA_TAG=cu128

# ======================================================================
# Builder: install torch + sglang-omni + API deps into /opt/venv
# ======================================================================
FROM nvidia/cuda:${CUDA_VERSION}-cudnn-devel-ubuntu${UBUNTU_VERSION} AS builder

ARG TORCH_VERSION
ARG TORCH_CUDA_TAG

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-venv \
        python3-dev \
        build-essential \
        git \
        ca-certificates \
        curl \
    && ln -sf /usr/bin/python3 /usr/local/bin/python \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
RUN pip install --upgrade pip

# PyTorch — single layer, pinned to sglang-omni requirement.
RUN pip install --index-url https://download.pytorch.org/whl/${TORCH_CUDA_TAG} \
        torch==${TORCH_VERSION} torchaudio==${TORCH_VERSION}

# flash-attn (requires CUDA devel headers for compilation;
# --no-build-isolation needs all build deps pre-installed)
RUN pip install packaging setuptools wheel ninja numpy psutil && \
    pip install flash-attn --no-build-isolation

# sglang-omni (the Higgs Audio serving backend)
RUN pip install "sglang-omni[all]" && \
    pip install hf_transfer

# API layer dependencies
COPY docker/requirements.api.txt /tmp/requirements.api.txt
RUN pip install -r /tmp/requirements.api.txt

# Engine-specific extra dependencies
COPY docker/requirements.engine.txt /tmp/requirements.engine.txt
RUN pip install -r /tmp/requirements.engine.txt

RUN find /opt/venv -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true

# ======================================================================
# Runtime: minimal image with venv + app code
# ======================================================================
FROM nvidia/cuda:${CUDA_VERSION}-cudnn-runtime-ubuntu${UBUNTU_VERSION}

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    HF_HOME=/root/.cache/huggingface \
    HF_HUB_ENABLE_HF_TRANSFER=1 \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        ffmpeg \
        libsndfile1 \
        ca-certificates \
    && ln -sf /usr/bin/python3 /usr/local/bin/python \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

WORKDIR /opt/api

COPY app /opt/api/app
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

VOLUME ["/voices", "/root/.cache"]
EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]
