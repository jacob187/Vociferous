"""
Model Registry — GGUF/GGML model catalog for Vociferous v4.0.

Replaces CTranslate2 repo references with direct GGUF/GGML URLs.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ASRModel:
    """A whisper.cpp GGML model entry."""

    id: str
    name: str
    filename: str
    repo: str
    size_mb: int
    tier: str  # fast, balanced, quality
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class SLMModel:
    """A llama.cpp GGUF model entry."""

    id: str
    name: str
    filename: str
    repo: str
    size_mb: int
    tier: str  # fast, balanced, quality, pro
    quant: str
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class VADModel:
    """A Voice Activity Detection ONNX model entry."""

    id: str
    name: str
    filename: str
    repo: str
    size_mb: int
    sha256: str | None = None


# --- ASR Models (whisper.cpp GGML) ---

ASR_MODELS: dict[str, ASRModel] = {
    "large-v3-turbo-q5_0": ASRModel(
        id="large-v3-turbo-q5_0",
        name="Whisper Large v3 Turbo (Q5)",
        filename="ggml-large-v3-turbo-q5_0.bin",
        repo="ggerganov/whisper.cpp",
        size_mb=547,
        tier="fast",
        sha256="394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2",
    ),
    "large-v3-turbo": ASRModel(
        id="large-v3-turbo",
        name="Whisper Large v3 Turbo",
        filename="ggml-large-v3-turbo.bin",
        repo="ggerganov/whisper.cpp",
        size_mb=1500,
        tier="balanced",
        sha256="1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69",
    ),
    "large-v3": ASRModel(
        id="large-v3",
        name="Whisper Large v3",
        filename="ggml-large-v3.bin",
        repo="ggerganov/whisper.cpp",
        size_mb=3100,
        tier="quality",
        sha256="64d182b440b98d5203c4f9bd541544d84c605196c4f7b845dfa11fb23594d1e2",
    ),
}

# --- SLM Models (llama.cpp GGUF) ---

SLM_MODELS: dict[str, SLMModel] = {
    "qwen1.7b": SLMModel(
        id="qwen1.7b",
        name="Qwen3 1.7B",
        filename="Qwen3-1.7B-Q8_0.gguf",
        repo="Qwen/Qwen3-1.7B-GGUF",
        size_mb=1800,
        tier="fast",
        quant="Q8_0",
        sha256="061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a",
    ),
    "qwen4b": SLMModel(
        id="qwen4b",
        name="Qwen3 4B",
        filename="Qwen3-4B-Q4_K_M.gguf",
        repo="Qwen/Qwen3-4B-GGUF",
        size_mb=2500,
        tier="balanced",
        quant="Q4_K_M",
        sha256="7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5",
    ),
    "qwen8b": SLMModel(
        id="qwen8b",
        name="Qwen3 8B",
        filename="Qwen3-8B-Q4_K_M.gguf",
        repo="Qwen/Qwen3-8B-GGUF",
        size_mb=5030,
        tier="quality",
        quant="Q4_K_M",
        sha256="d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785",
    ),
    "qwen14b": SLMModel(
        id="qwen14b",
        name="Qwen3 14B",
        filename="Qwen3-14B-Q4_K_M.gguf",
        repo="Qwen/Qwen3-14B-GGUF",
        size_mb=8500,
        tier="pro",
        quant="Q4_K_M",
        sha256="500a8806e85ee9c83f3ae08420295592451379b4f8cf2d0f41c15dffeb6b81f0",
    ),
}


# --- VAD Models (ONNX) ---

SILERO_VAD = VADModel(
    id="silero_vad",
    name="Silero VAD v5",
    filename="silero_vad.onnx",
    repo="deepghs/silero-vad-onnx",
    size_mb=2,
    sha256="2623a2953f6ff3d2c1e61740c6cdb7168133479b267dfef114a4a3cc5bdd788f",
)


def get_asr_model(model_id: str) -> ASRModel | None:
    """Look up an ASR model by ID."""
    return ASR_MODELS.get(model_id)


def get_slm_model(model_id: str) -> SLMModel | None:
    """Look up an SLM model by ID."""
    return SLM_MODELS.get(model_id)


def get_model_catalog() -> dict:
    """Return the full model catalog as serializable dicts."""
    return {
        "asr": {k: _model_to_dict(v) for k, v in ASR_MODELS.items()},
        "slm": {k: _model_to_dict(v) for k, v in SLM_MODELS.items()},
    }


def _model_to_dict(m: ASRModel | SLMModel) -> dict:
    from dataclasses import asdict

    return asdict(m)
