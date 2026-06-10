from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    # --- Engine (HIGGS_* prefix) ----------------------------------------------
    higgs_model: str = Field(
        default="bosonai/higgs-audio-v3-tts-4b",
        description="HuggingFace model id or local path.",
    )
    higgs_device: Literal["auto", "cuda", "cpu"] = "auto"
    higgs_cuda_index: int = Field(default=0, ge=0)
    higgs_dtype: Literal["float16", "bfloat16", "float32"] = "bfloat16"
    higgs_internal_port: int = Field(
        default=8001,
        ge=1024,
        le=65535,
        description="Port for the internal sglang-omni backend.",
    )
    higgs_tp_size: int = Field(
        default=1,
        ge=1,
        description="Tensor-parallel size for sglang-omni.",
    )
    higgs_backend_url: Optional[str] = Field(
        default=None,
        description="URL of an external sglang-omni backend. "
        "If set, the engine connects to it instead of launching its own.",
    )
    higgs_temperature: float = Field(default=0.8, ge=0.0, le=2.0)
    higgs_top_k: int = Field(default=50, ge=0)
    higgs_max_new_tokens: int = Field(default=2048, ge=1, le=16384)

    # --- Service-level (no prefix) --------------------------------------------
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "info"
    voices_dir: str = "/voices"
    max_input_chars: int = Field(default=8000, ge=1)
    default_response_format: Literal[
        "mp3", "opus", "aac", "flac", "wav", "pcm"
    ] = "mp3"
    max_concurrency: int = Field(default=1, ge=1)
    max_queue_size: int = Field(default=0, ge=0)
    queue_timeout: float = Field(default=0.0, ge=0.0)
    max_audio_bytes: int = Field(default=20 * 1024 * 1024, ge=1)
    cors_enabled: bool = False

    @property
    def voices_path(self) -> Path:
        return Path(self.voices_dir)

    @property
    def resolved_device(self) -> str:
        if self.higgs_device == "cpu":
            return "cpu"
        if self.higgs_device == "cuda":
            return f"cuda:{self.higgs_cuda_index}"
        import torch

        if torch.cuda.is_available():
            return f"cuda:{self.higgs_cuda_index}"
        return "cpu"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
