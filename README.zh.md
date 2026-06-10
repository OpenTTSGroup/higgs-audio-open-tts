# higgs-audio-open-tts

[English](./README.md) · **中文**

基于 [Higgs Audio v3](https://huggingface.co/bosonai/higgs-audio-v3-tts-4b)
（[Boson AI](https://github.com/boson-ai/higgs-audio)）的 OpenAI 兼容
HTTP TTS 服务，单镜像发布到 GHCR。

遵循 [Open TTS 规范](https://github.com/OpenTTSGroup/open-tts-spec)：

- `POST /v1/audio/speech` — OpenAI 兼容的语音克隆合成
- `POST /v1/audio/clone` — 一次性上传音频做零样本克隆
- `POST /v1/audio/design` — 无需参考音频的合成
- `POST /v1/audio/realtime` — 分块流式合成
- `GET  /v1/audio/voices` — 列出文件克隆音色
- `GET  /v1/audio/voices/preview?id=...` — 下载参考音频
- `GET  /healthz` — 引擎状态、能力矩阵、并发快照

支持 `mp3`、`opus`、`aac`、`flac`、`wav`、`pcm` 六种输出格式（服务端编码单声道
float32）。音色目录通过 `${VOICES_DIR}/<id>.{wav,txt,yml}` 三件套提供。

## 快速开始

```bash
mkdir -p voices cache

# 准备一段 5-15 秒的参考音频和对应转录：
cp ~/my-ref.wav voices/alice.wav
echo "这是参考音频对应的转录文本。" > voices/alice.txt

docker run --rm --gpus all -p 8000:8000 \
  -v "$PWD/voices:/voices:ro" \
  -v "$PWD/cache:/root/.cache" \
  ghcr.io/openttsgroup/higgs-audio-open-tts:latest
```

首次启动会下载约 8 GB 权重到 `/root/.cache` 并启动 sglang-omni 推理后端；
挂载 cache 目录避免重复下载。引擎加载期间 `/healthz` 返回 `status="loading"`。

```bash
curl -s localhost:8000/healthz | jq

# 声音克隆
curl -X POST localhost:8000/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"input":"你好，来自 Higgs Audio。","voice":"file://alice","response_format":"mp3"}' \
  -o out.mp3

# 无参考音频合成（设计端点）
curl -X POST localhost:8000/v1/audio/design \
  -H 'Content-Type: application/json' \
  -d '{"input":"你好，来自 Higgs Audio。","response_format":"mp3"}' \
  -o out_design.mp3
```

## 能力矩阵

| capability | 取值 | 说明 |
|---|---|---|
| `clone` | `true` | 通过 `voice="file://..."` 或 `POST /v1/audio/clone` 做零样本克隆 |
| `streaming` | `true` | `POST /v1/audio/realtime` 流式输出 mp3/pcm/opus/aac |
| `design` | `true` | 通过 `POST /v1/audio/design` 无需参考音频合成；`instruct` 接受 Higgs 内联控制 token |
| `languages` | `false` | 支持 102 种语言内联混排，无需显式指定语种 |
| `builtin_voices` | `false` | 所有音色基于文件，无引擎内置音色 |

## 环境变量

### 引擎（带 `HIGGS_` 前缀）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `HIGGS_MODEL` | `bosonai/higgs-audio-v3-tts-4b` | HuggingFace model id 或本地路径 |
| `HIGGS_DEVICE` | `auto` | `auto` / `cuda` / `cpu` |
| `HIGGS_CUDA_INDEX` | `0` | 多卡场景指定 GPU 序号 |
| `HIGGS_DTYPE` | `bfloat16` | `float16` / `bfloat16` / `float32` |
| `HIGGS_INTERNAL_PORT` | `8001` | 内部 sglang-omni 后端端口 |
| `HIGGS_TP_SIZE` | `1` | 多 GPU 张量并行大小 |
| `HIGGS_QUANTIZATION` | `none` | 量化方式：`none` / `fp8` / `awq` / `gptq`。仅 CUDA 有效，CPU 自动回退为 `none`。 |
| `HIGGS_BACKEND_URL` | （空） | 外部 sglang-omni 后端 URL；设置后引擎连接该地址而非自行启动 |
| `HIGGS_TEMPERATURE` | `0.8` | 默认采样温度 |
| `HIGGS_TOP_K` | `50` | 默认 top-k 采样 |
| `HIGGS_MAX_NEW_TOKENS` | `2048` | 默认最大生成 token 数 |

### 服务级（无前缀）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `HOST` | `0.0.0.0` | |
| `PORT` | `8000` | |
| `LOG_LEVEL` | `info` | uvicorn 日志级别 |
| `VOICES_DIR` | `/voices` | 文件克隆音色扫描根 |
| `MAX_INPUT_CHARS` | `8000` | 超出返回 413 |
| `DEFAULT_RESPONSE_FORMAT` | `mp3` | |
| `MAX_CONCURRENCY` | `1` | 同时推理上限 |
| `MAX_QUEUE_SIZE` | `0` | 0 = 不限 |
| `QUEUE_TIMEOUT` | `0` | 秒；0 = 不限 |
| `MAX_AUDIO_BYTES` | `20971520` | `/v1/audio/clone` 上传大小限制 |
| `CORS_ENABLED` | `false` | 设为 `true` 时挂载 `CORSMiddleware`，对**所有端点**放开任意 origin / method / header（不带凭证）。反向代理前置或同源调用时保持 `false`。 |

## Compose

参考 [`docker/docker-compose.example.yml`](docker/docker-compose.example.yml)。

## 请求参数

GET 端点（`/healthz`、`/v1/audio/voices`、`/v1/audio/voices/preview`）无请求体，
最多一个 `id` 查询参数；响应结构参见
[Open TTS 规范](https://github.com/OpenTTSGroup/open-tts-spec)。

下列表格描述有请求体的 POST 端点。**状态**列使用固定词汇：

- **required** — 必填，缺失返回 422。
- **supported** — 可选字段，引擎实际消费。
- **ignored** — 为 OpenAI 兼容接受，但永远不生效。
- **conditional** — 行为取决于上下文，详见"说明"列。
- **extension** — Higgs Audio 特有扩展，规范未定义。

### `POST /v1/audio/speech`（application/json）

| 字段 | 类型 | 默认值 | 状态 | 说明 |
|---|---|---|---|---|
| `model` | string | `null` | ignored | 仅用于 OpenAI 兼容。 |
| `input` | string | — | required | 长度 1..`MAX_INPUT_CHARS`；空串 -> 422，超长 -> 413。 |
| `voice` | string | — | required | `file://<id>` 加载 `${VOICES_DIR}/<id>.wav` + `.txt` 做零样本克隆。 |
| `response_format` | enum | `mp3` | supported | `mp3`/`opus`/`aac`/`flac`/`wav`/`pcm` 六选一。 |
| `speed` | float | `1.0` | supported | 范围 `[0.25, 4.0]`；透传到后端。 |
| `instructions` | string \| null | `null` | conditional | Higgs 内联控制 token（如 `<\|emotion:amusement\|>`）会被拼接到 input 前；自然语言风格描述不会被模型理解。 |
| `temperature` | float | `0.8` | extension | 采样温度 `[0.0, 2.0]`。 |
| `top_k` | int | `50` | extension | Top-k 采样。 |
| `top_p` | float | `null` | extension | Top-p 采样 `[0.0, 1.0]`。 |
| `max_new_tokens` | int | `2048` | extension | 最大生成步数 `[1, 16384]`。 |
| `seed` | int | `null` | extension | 随机种子。 |

### `POST /v1/audio/clone`（multipart/form-data）

| 字段 | 类型 | 默认值 | 状态 | 说明 |
|---|---|---|---|---|
| `audio` | file | — | required | 参考音频。推荐 WAV（PCM 16-bit，16kHz+，5-15 秒）；也接受 MP3/FLAC/Opus/M4A。超过 `MAX_AUDIO_BYTES` -> 413。**不会**持久化到 `${VOICES_DIR}`。 |
| `prompt_text` | string | — | required | 参考音频的转录文本；空串 -> 422。 |
| `input` | string | — | required | 同 `/speech.input`。 |
| `response_format` | string | `mp3` | supported | 同 `/speech`。 |
| `speed` | float | `1.0` | supported | 范围 `[0.25, 4.0]`。 |
| `instructions` | string \| null | `null` | conditional | 同 `/speech.instructions`。 |
| `model` | string | `null` | ignored | 仅用于 OpenAI 兼容。 |

### `POST /v1/audio/design`（application/json）

| 字段 | 类型 | 默认值 | 状态 | 说明 |
|---|---|---|---|---|
| `input` | string | — | required | 长度 1..`MAX_INPUT_CHARS`。 |
| `instruct` | string \| null | `null` | supported | Higgs 内联控制 token 拼接到 input 前。传 null 或空串使用引擎默认声音，不报错。 |
| `response_format` | enum | `mp3` | supported | 同 `/speech`。 |
| `temperature` | float | `0.8` | extension | 采样温度。 |
| `top_k` | int | `50` | extension | Top-k 采样。 |
| `top_p` | float | `null` | extension | Top-p 采样。 |
| `max_new_tokens` | int | `2048` | extension | 最大生成步数。 |
| `seed` | int | `null` | extension | 随机种子。 |

### `POST /v1/audio/realtime`（application/json）

请求体与 `/v1/audio/speech` 相同。下表只列与 `/speech` 的差异：

| 字段 | 状态覆盖 | 说明 |
|---|---|---|
| `response_format` | 受限 | 仅 `mp3` / `pcm` / `opus` / `aac`；`flac` / `wav` 返回 422。 |
| 其他字段 | — | 与 `/speech` 一致。 |

## 内联控制 token

Higgs Audio 支持在 `input` 文本中嵌入控制 token：

```
<|emotion:amusement|><|prosody:expressive_high|>哈哈，那真是太搞笑了。
```

**情绪**（21 种）：`elation`、`amusement`、`enthusiasm`、`determination`、`pride`、`contentment`、`affection`、`relief`、`contemplation`、`confusion`、`surprise`、`awe`、`longing`、`arousal`、`anger`、`fear`、`disgust`、`bitterness`、`sadness`、`shame`、`helplessness`

**风格**：`singing`、`shouting`、`whispering`

**音效**：`cough`、`laughter`、`crying`、`screaming`、`burping`、`humming`、`sigh`、`sniff`、`sneeze`

**韵律**：`speed_very_slow`、`speed_slow`、`speed_fast`、`speed_very_fast`、`pitch_low`、`pitch_high`、`pause`、`long_pause`、`expressive_high`、`expressive_low`

在 `/v1/audio/speech` 的 `instructions` 字段或 `/v1/audio/design` 的 `instruct` 字段中传入控制 token，它们会被拼接到 input 文本前。

## 架构

本服务使用 [sglang-omni](https://github.com/sgl-project/sglang-omni) 作为推理
后端。启动时引擎会在内部端口（默认 8001）启动 sglang-omni 服务，并将 TTS 请求
代理到该服务。也可通过设置 `HIGGS_BACKEND_URL` 连接到外部 sglang-omni 实例。

## 已知限制

- Higgs Audio 是 4B 参数模型，需要至少 16 GB 显存的 GPU（推荐 24 GB+）。
- `instructions` / `instruct` 字段仅支持 Higgs 专用内联控制 token（`<|...|>`），不支持自由文本风格描述。
- 首次启动需下载约 8 GB 权重；后续启动使用缓存。
- `/v1/audio/design` 端点以随机/默认声音特征合成——不接受自然语言声音描述（如"女性，英式口音"）。
- `flac` / `wav` 不支持 `/v1/audio/realtime`。

## 规范

本项目遵循 [Open TTS 规范](https://github.com/OpenTTSGroup/open-tts-spec)。
