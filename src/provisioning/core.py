"""
Model Provisioning Core — Download GGUF/GGML models from HuggingFace.

v4.0: No more CTranslate2 conversion pipeline. Models are pre-quantized
GGUF/GGML files downloaded directly from HuggingFace repos.
"""

import hashlib
import logging
from pathlib import Path
from typing import Callable, Optional

from src.core.model_registry import ASRModel, SLMModel, VADModel

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]

_SHA256_BUF_SIZE = 1 << 18  # 256 KiB read chunks for hashing


class ProvisioningError(Exception):
    """Raised when provisioning fails."""


class IntegrityError(ProvisioningError):
    """Raised when a downloaded file fails SHA-256 verification."""


def _compute_sha256(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file without slurping it all into RAM."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_SHA256_BUF_SIZE):
            h.update(chunk)
    return h.hexdigest()


def _verify_integrity(path: Path, expected_sha256: str) -> None:
    """Verify file integrity against an expected SHA-256 hash.

    Deletes the file and raises IntegrityError on mismatch.
    """
    actual = _compute_sha256(path)
    if actual != expected_sha256:
        path.unlink(missing_ok=True)
        raise IntegrityError(
            f"SHA-256 mismatch for {path.name}: "
            f"expected {expected_sha256}, got {actual}. "
            f"Corrupted file removed."
        )


def download_model_file(
    repo_id: str,
    filename: str,
    target_dir: Path,
    progress_callback: Optional[ProgressCallback] = None,
    expected_sha256: str | None = None,
) -> Path:
    """
    Download a single model file from a HuggingFace repository.

    Args:
        repo_id: HuggingFace repo (e.g. 'ggerganov/whisper.cpp').
        filename: File to download (e.g. 'ggml-large-v3-turbo-q5_0.bin').
        target_dir: Local directory for the downloaded file.
        progress_callback: Optional status callback.
        expected_sha256: If provided, verify the file after download.

    Returns:
        Path to the downloaded file.

    Raises:
        ProvisioningError: On download failure.
        IntegrityError: On SHA-256 mismatch (file is deleted automatically).
    """
    from huggingface_hub import hf_hub_download

    target_dir.mkdir(parents=True, exist_ok=True)

    if progress_callback:
        progress_callback(f"Downloading {filename} from {repo_id}...")

    try:
        downloaded = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=str(target_dir),
        )
        result = Path(downloaded)
        logger.info("Downloaded %s -> %s", filename, downloaded)

        # --- SHA-256 integrity check ---
        if expected_sha256:
            if progress_callback:
                progress_callback(f"Verifying integrity of {filename}...")
            _verify_integrity(result, expected_sha256)
            logger.info("SHA-256 verified for %s", filename)

        if progress_callback:
            progress_callback(f"Downloaded {filename} successfully.")

        return result

    except IntegrityError:
        raise
    except Exception as e:
        raise ProvisioningError(f"Failed to download {filename} from {repo_id}: {e}") from e


def provision_asr_model(
    model: ASRModel,
    cache_dir: Path,
    progress_callback: Optional[ProgressCallback] = None,
) -> Path:
    """
    Provision an ASR (whisper.cpp) model.

    Downloads the GGML file from the model's HuggingFace repo.
    """
    return download_model_file(
        repo_id=model.repo,
        filename=model.filename,
        target_dir=cache_dir,
        progress_callback=progress_callback,
        expected_sha256=model.sha256,
    )


def provision_slm_model(
    model: SLMModel,
    cache_dir: Path,
    progress_callback: Optional[ProgressCallback] = None,
) -> Path:
    """
    Provision an SLM (llama.cpp) model.

    Downloads the GGUF file from the model's HuggingFace repo.
    """
    return download_model_file(
        repo_id=model.repo,
        filename=model.filename,
        target_dir=cache_dir,
        progress_callback=progress_callback,
        expected_sha256=model.sha256,
    )


def provision_vad_model(
    model: VADModel,
    cache_dir: Path,
    progress_callback: Optional[ProgressCallback] = None,
) -> Path:
    """
    Provision the Silero VAD ONNX model.

    Downloads the ONNX file from the model's HuggingFace repo.
    """
    return download_model_file(
        repo_id=model.repo,
        filename=model.filename,
        target_dir=cache_dir,
        progress_callback=progress_callback,
        expected_sha256=model.sha256,
    )
