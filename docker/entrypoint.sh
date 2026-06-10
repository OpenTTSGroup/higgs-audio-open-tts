#!/usr/bin/env bash
set -euo pipefail

# Engine defaults
: "${HIGGS_MODEL:=bosonai/higgs-audio-v3-tts-4b}"
: "${HIGGS_DEVICE:=auto}"
: "${HIGGS_DTYPE:=bfloat16}"
: "${HIGGS_INTERNAL_PORT:=8001}"
: "${HIGGS_TP_SIZE:=1}"
: "${HIGGS_QUANTIZATION:=none}"

# Service-level defaults
: "${VOICES_DIR:=/voices}"
: "${HOST:=0.0.0.0}"
: "${PORT:=8000}"
: "${LOG_LEVEL:=info}"
: "${CORS_ENABLED:=false}"

export HIGGS_MODEL HIGGS_DEVICE HIGGS_DTYPE HIGGS_INTERNAL_PORT HIGGS_TP_SIZE HIGGS_QUANTIZATION \
       VOICES_DIR HOST PORT LOG_LEVEL CORS_ENABLED

if [ "$#" -eq 0 ]; then
  exec uvicorn app.server:app --host "$HOST" --port "$PORT" --log-level "$LOG_LEVEL"
fi
exec "$@"
