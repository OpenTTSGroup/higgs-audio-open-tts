# syntax=docker/dockerfile:1.7

# ============================================================================
# Base: lmsysorg/sglang-omni:dev ships torch 2.9.1, flash-attn, sglang,
# UCX 1.20.x, and CUDA pre-built.  We clone sglang-omni from source
# (not on PyPI) and layer the Open TTS API on top.
#
# Installation follows the official guide — Option A (Docker):
# https://sgl-project.github.io/sglang-omni/get_started/installation.html
# ============================================================================
ARG SGLANG_OMNI_TAG=dev

FROM lmsysorg/sglang-omni:${SGLANG_OMNI_TAG}

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/root/.cache/huggingface \
    HF_HUB_ENABLE_HF_TRANSFER=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

# Create venv and install sglang-omni (mirrors official install steps)
RUN uv venv /opt/venv -p 3.12 && \
    git clone https://github.com/sgl-project/sglang-omni.git /opt/sglang-omni && \
    cd /opt/sglang-omni && \
    uv pip install -v . && \
    rm -rf /opt/sglang-omni/.git

# Runtime tools needed by audio encoding (PyAV / SoundFile)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# API layer dependencies
COPY docker/requirements.api.txt /tmp/requirements.api.txt
RUN uv pip install -r /tmp/requirements.api.txt

# Engine-specific extra dependencies
COPY docker/requirements.engine.txt /tmp/requirements.engine.txt
RUN uv pip install -r /tmp/requirements.engine.txt

WORKDIR /opt/api

COPY app /opt/api/app
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

VOLUME ["/voices", "/root/.cache"]
EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]
