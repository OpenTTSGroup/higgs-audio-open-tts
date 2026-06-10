# higgs-audio-open-tts

**English** · [中文](./README.zh.md)

OpenAI-compatible HTTP TTS service built on top of
[Higgs Audio v3](https://huggingface.co/bosonai/higgs-audio-v3-tts-4b)
by [Boson AI](https://github.com/boson-ai/higgs-audio). Ships as a single
CUDA container image on GHCR.

Implements the [Open TTS spec](https://github.com/OpenTTSGroup/open-tts-spec):

- `POST /v1/audio/speech` — OpenAI-compatible synthesis (voice cloning)
- `POST /v1/audio/clone` — one-shot zero-shot cloning (multipart upload)
- `POST /v1/audio/design` — synthesis without reference audio
- `POST /v1/audio/realtime` — chunked streaming synthesis
- `GET  /v1/audio/voices` — list file-based voices
- `GET  /v1/audio/voices/preview?id=...` — download a reference WAV
- `GET  /healthz` — engine status, capabilities, concurrency snapshot

Six output formats (`mp3`, `opus`, `aac`, `flac`, `wav`, `pcm`); mono
`float32` encoded server-side. Voices live on disk as
`${VOICES_DIR}/<id>.{wav,txt,yml}` triples.

## Quick start

```bash
mkdir -p voices cache

# Drop a 5-15 s reference WAV plus its transcript:
cp ~/my-ref.wav voices/alice.wav
echo "This is the transcript of the reference clip." > voices/alice.txt

docker run --rm --gpus all -p 8000:8000 \
  -v "$PWD/voices:/voices:ro" \
  -v "$PWD/cache:/root/.cache" \
  ghcr.io/openttsgroup/higgs-audio-open-tts:latest
```

First boot downloads the model weights (~8 GB) to `/root/.cache` and starts
the sglang-omni inference backend. Mount the cache directory to avoid repeat
downloads. `/healthz` reports `status="loading"` until the engine is ready.

```bash
curl -s localhost:8000/healthz | jq

# Voice cloning
curl -X POST localhost:8000/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"input":"Hello from Higgs Audio.","voice":"file://alice","response_format":"mp3"}' \
  -o out.mp3

# Synthesis without reference (design endpoint)
curl -X POST localhost:8000/v1/audio/design \
  -H 'Content-Type: application/json' \
  -d '{"input":"Hello from Higgs Audio.","response_format":"mp3"}' \
  -o out_design.mp3
```

## Features

| capability | value | notes |
|---|---|---|
| `clone` | `true` | zero-shot via `voice="file://..."` or `POST /v1/audio/clone` |
| `streaming` | `true` | chunked mp3/pcm/opus/aac via `POST /v1/audio/realtime` |
| `design` | `true` | synthesis without reference audio via `POST /v1/audio/design`; `instruct` accepts Higgs inline control tokens |
| `languages` | `false` | 102 languages supported inline; no explicit language list |
| `builtin_voices` | `false` | all voices are file-based; no engine-built-in voices |

## Environment variables

### Engine (prefixed `HIGGS_`)

| variable | default | description |
|---|---|---|
| `HIGGS_MODEL` | `bosonai/higgs-audio-v3-tts-4b` | HuggingFace model id or local path |
| `HIGGS_DEVICE` | `auto` | `auto` / `cuda` / `cpu` |
| `HIGGS_CUDA_INDEX` | `0` | GPU index when multiple are visible |
| `HIGGS_DTYPE` | `bfloat16` | `float16` / `bfloat16` / `float32` |
| `HIGGS_INTERNAL_PORT` | `8001` | Port for the internal sglang-omni backend |
| `HIGGS_TP_SIZE` | `1` | Tensor-parallel size for multi-GPU |
| `HIGGS_MEM_FRACTION_STATIC` | (auto) | Fraction of GPU memory for KV cache (`0.0`–`1.0`). Increase if you see "thinker KV cache" errors. |
| `HIGGS_BACKEND_URL` | (none) | URL of an external sglang-omni backend; if set, the engine connects to it instead of launching its own |
| `HIGGS_TEMPERATURE` | `0.8` | Default sampling temperature |
| `HIGGS_TOP_K` | `50` | Default top-k sampling |
| `HIGGS_MAX_NEW_TOKENS` | `1024` | Default max generated tokens |

### Service-level (no prefix)

| variable | default | description |
|---|---|---|
| `HOST` | `0.0.0.0` | |
| `PORT` | `8000` | |
| `LOG_LEVEL` | `info` | uvicorn log level |
| `VOICES_DIR` | `/voices` | scan root for file-based voices |
| `MAX_INPUT_CHARS` | `8000` | 413 above this |
| `DEFAULT_RESPONSE_FORMAT` | `mp3` | |
| `MAX_CONCURRENCY` | `1` | in-flight synthesis ceiling |
| `MAX_QUEUE_SIZE` | `0` | 0 = unbounded queue |
| `QUEUE_TIMEOUT` | `0` | seconds; 0 = unbounded wait |
| `MAX_AUDIO_BYTES` | `20971520` | upload limit for `/v1/audio/clone` |
| `CORS_ENABLED` | `false` | `true` mounts a `CORSMiddleware` allowing any origin / method / header on every endpoint (no credentials). Keep `false` when fronted by a reverse proxy or same-origin. |

## Compose

See [`docker/docker-compose.example.yml`](docker/docker-compose.example.yml).

## API request parameters

GET endpoints (`/healthz`, `/v1/audio/voices`, `/v1/audio/voices/preview`)
take no body and at most a single `id` query parameter — see the
[Open TTS spec](https://github.com/OpenTTSGroup/open-tts-spec) for their
response shape.

The tables below describe the POST endpoints. The **Status** column uses a
fixed vocabulary:

- **required** — rejected with 422 if missing.
- **supported** — accepted and consumed by Higgs Audio.
- **ignored** — accepted for OpenAI compatibility; has no effect.
- **conditional** — behaviour depends on context; see the notes column.
- **extension** — Higgs-specific field, not part of the Open TTS spec.

### `POST /v1/audio/speech` (application/json)

| Field | Type | Default | Status | Notes |
|---|---|---|---|---|
| `model` | string | `null` | ignored | OpenAI compatibility only. |
| `input` | string | — | required | 1..`MAX_INPUT_CHARS` chars. Empty -> 422, over limit -> 413. |
| `voice` | string | — | required | `file://<id>` loads `${VOICES_DIR}/<id>.wav` + `.txt` for zero-shot cloning. |
| `response_format` | enum | `mp3` | supported | `mp3`/`opus`/`aac`/`flac`/`wav`/`pcm`. |
| `speed` | float | `1.0` | supported | Range `[0.25, 4.0]`. Passed through to the backend. |
| `instructions` | string \| null | `null` | conditional | Higgs inline control tokens (e.g. `<\|emotion:amusement\|>`) prepended to input text. Natural language style hints are not interpreted by the model. |
| `temperature` | float | `0.8` | extension | Sampling temperature `[0.0, 2.0]`. |
| `top_k` | int | `50` | extension | Top-k sampling. |
| `top_p` | float | `null` | extension | Top-p (nucleus) sampling `[0.0, 1.0]`. |
| `max_new_tokens` | int | `1024` | extension | Max generated multi-codebook steps `[1, 16384]`. |
| `seed` | int | `null` | extension | Random seed for reproducibility. |

### `POST /v1/audio/clone` (multipart/form-data)

| Field | Type | Default | Status | Notes |
|---|---|---|---|---|
| `audio` | file | — | required | Reference audio. Recommended WAV (PCM 16-bit, 16kHz+, 5-15 s). MP3/FLAC/Opus/M4A also accepted. Over `MAX_AUDIO_BYTES` -> 413. Never persisted to `${VOICES_DIR}`. |
| `prompt_text` | string | — | required | Reference-clip transcript. Empty -> 422. |
| `input` | string | — | required | Same semantics as `/speech.input`. |
| `response_format` | string | `mp3` | supported | Same as `/speech`. |
| `speed` | float | `1.0` | supported | Range `[0.25, 4.0]`. |
| `instructions` | string \| null | `null` | conditional | Same as `/speech.instructions`. |
| `model` | string | `null` | ignored | OpenAI compatibility only. |

### `POST /v1/audio/design` (application/json)

| Field | Type | Default | Status | Notes |
|---|---|---|---|---|
| `input` | string | — | required | 1..`MAX_INPUT_CHARS` chars. |
| `instruct` | string \| null | `null` | supported | Higgs inline control tokens prepended to input. Null/empty -> engine default voice, no error. |
| `response_format` | enum | `mp3` | supported | Same as `/speech`. |
| `temperature` | float | `0.8` | extension | Sampling temperature. |
| `top_k` | int | `50` | extension | Top-k sampling. |
| `top_p` | float | `null` | extension | Top-p (nucleus) sampling. |
| `max_new_tokens` | int | `1024` | extension | Max generated tokens. |
| `seed` | int | `null` | extension | Random seed. |

### `POST /v1/audio/realtime` (application/json)

Request body mirrors `/v1/audio/speech`. Only divergences listed:

| Field | Status override | Notes |
|---|---|---|
| `response_format` | restricted | Only `mp3` / `pcm` / `opus` / `aac`. `flac` / `wav` return 422. |
| All other fields | — | Same as `/speech`. |

## Inline control tokens

Higgs Audio supports inline control tokens embedded in the `input` text:

```
<|emotion:amusement|><|prosody:expressive_high|>Wait, that was hilarious.
```

**Emotions** (21): `elation`, `amusement`, `enthusiasm`, `determination`, `pride`, `contentment`, `affection`, `relief`, `contemplation`, `confusion`, `surprise`, `awe`, `longing`, `arousal`, `anger`, `fear`, `disgust`, `bitterness`, `sadness`, `shame`, `helplessness`

**Styles**: `singing`, `shouting`, `whispering`

**Sound effects**: `cough`, `laughter`, `crying`, `screaming`, `burping`, `humming`, `sigh`, `sniff`, `sneeze`

**Prosody**: `speed_very_slow`, `speed_slow`, `speed_fast`, `speed_very_fast`, `pitch_low`, `pitch_high`, `pause`, `long_pause`, `expressive_high`, `expressive_low`

Use these tokens in the `instructions` field of `/v1/audio/speech` or the `instruct` field of `/v1/audio/design` to prepend them to the input text.

## Architecture

This service wraps [sglang-omni](https://github.com/sgl-project/sglang-omni)
as the inference backend. On startup, the engine launches a sglang-omni server
on an internal port (default 8001) and proxies TTS requests through it.
Alternatively, set `HIGGS_BACKEND_URL` to connect to an external sglang-omni
instance.

## Known limitations

- Higgs Audio is a 4B parameter model and requires a GPU with at least 16 GB VRAM (24 GB+ recommended).
- The `instructions` / `instruct` field only supports Higgs-specific inline control tokens (`<|...|>`), not free-form natural language style descriptions.
- First startup downloads ~8 GB of model weights; subsequent starts use the cached weights.
- The `/v1/audio/design` endpoint generates with a random/default voice characteristic — it does not accept natural language voice descriptions like "female, british accent".
- `flac` and `wav` are not supported for `/v1/audio/realtime`.

## Spec

This project implements the [Open TTS spec](https://github.com/OpenTTSGroup/open-tts-spec).
