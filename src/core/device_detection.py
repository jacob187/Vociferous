"""
Unified device detection for CTranslate2 inference.

Probes the current platform (Apple Silicon, NVIDIA CUDA, or CPU-only)
and returns a DeviceCapability describing the optimal CT2 device string,
compute type, and thread count recommendations.

Apple Silicon uses the Accelerate framework (vecLib + NEON) via CT2's
CPU backend -- there is no separate "metal" device in CTranslate2.
NVIDIA systems use the CUDA backend.
"""

from __future__ import annotations

import functools
import logging
import os
import platform
import subprocess
import sys
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DeviceCapability:
    """Describes the best inference backend for the current machine."""

    platform: str  # "apple_silicon", "nvidia_cuda", "cpu_only"
    ct2_device: str  # "auto", "cuda", "cpu"
    optimal_compute_type: str  # "int8", "float16", "float32"
    cpu_cores: int  # total logical cores
    detail: str


def _get_apple_silicon_perf_cores() -> int:
    """Return the performance-core count on Apple Silicon (macOS only).

    Falls back to half of os.cpu_count() if the sysctl probe fails.
    """
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.perflevel0.logicalcpu"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0 and result.stdout.strip().isdigit():
            return int(result.stdout.strip())
    except Exception:
        pass
    return max(2, (os.cpu_count() or 4) // 2)


@functools.lru_cache(maxsize=1)
def detect_device() -> DeviceCapability:
    """Detect the best CTranslate2 inference backend for this machine.

    Detection order:
      1. Apple Silicon (arm64 + macOS) -> device="auto", compute="int8"
      2. NVIDIA CUDA (via existing cuda_runtime probe) -> device="cuda", compute="float16"
      3. CPU fallback -> device="cpu", compute="int8"
    """
    cpu_cores = os.cpu_count() or 4

    # 1. Apple Silicon
    if sys.platform == "darwin" and platform.machine() == "arm64":
        return DeviceCapability(
            platform="apple_silicon",
            ct2_device="auto",
            optimal_compute_type="int8",
            cpu_cores=cpu_cores,
            detail="Apple Silicon detected; CT2 uses Accelerate (vecLib + NEON)",
        )

    # 2. NVIDIA CUDA
    from src.core.cuda_runtime import detect_cuda_runtime

    cuda_status = detect_cuda_runtime()
    if cuda_status.cuda_available:
        return DeviceCapability(
            platform="nvidia_cuda",
            ct2_device="cuda",
            optimal_compute_type="float16",
            cpu_cores=cpu_cores,
            detail=cuda_status.detail,
        )

    # 3. CPU fallback
    detail = "CPU-only inference"
    if cuda_status.driver_detected:
        detail += f" (NVIDIA driver present but CUDA unavailable: {cuda_status.detail})"
    return DeviceCapability(
        platform="cpu_only",
        ct2_device="cpu",
        optimal_compute_type="int8",
        cpu_cores=cpu_cores,
        detail=detail,
    )


def recommend_thread_count(cap: DeviceCapability) -> int:
    """Recommend an inference thread count based on detected hardware.

    Apple Silicon: use performance-core count (avoids scheduling onto
    efficiency cores which are slower for sustained compute).
    Other platforms: total cores minus 2, leaving headroom for the
    event loop and audio callback threads.
    """
    if cap.platform == "apple_silicon":
        return _get_apple_silicon_perf_cores()
    return max(2, min(cap.cpu_cores - 2, 16))
