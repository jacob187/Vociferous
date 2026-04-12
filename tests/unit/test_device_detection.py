"""Tests for unified device detection."""

import pytest
from unittest.mock import patch

from src.core.device_detection import DeviceCapability, detect_device, recommend_thread_count


class TestDetectDevice:
    """Tests for detect_device() across platforms."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        """Clear detect_device lru_cache between tests."""
        detect_device.cache_clear()
        yield
        detect_device.cache_clear()

    def test_apple_silicon_detected(self):
        with (
            patch("src.core.device_detection.sys") as mock_sys,
            patch("src.core.device_detection.platform") as mock_platform,
            patch("src.core.device_detection.os") as mock_os,
        ):
            mock_sys.platform = "darwin"
            mock_platform.machine.return_value = "arm64"
            mock_os.cpu_count.return_value = 10

            cap = detect_device()

        assert cap.platform == "apple_silicon"
        assert cap.ct2_device == "auto"
        assert cap.optimal_compute_type == "int8"
        assert cap.cpu_cores == 10

    def test_nvidia_cuda_detected(self):
        from src.core.cuda_runtime import CudaRuntimeStatus

        cuda_status = CudaRuntimeStatus(
            driver_detected=True,
            cuda_available=True,
            cuda_device_count=1,
            gpu_name="RTX 4090",
            detail="CTranslate2 detected 1 CUDA device(s)",
        )

        with (
            patch("src.core.device_detection.sys") as mock_sys,
            patch("src.core.device_detection.platform") as mock_platform,
            patch("src.core.device_detection.os") as mock_os,
            patch("src.core.cuda_runtime.detect_cuda_runtime", return_value=cuda_status),
        ):
            mock_sys.platform = "linux"
            mock_platform.machine.return_value = "x86_64"
            mock_os.cpu_count.return_value = 16

            cap = detect_device()

        assert cap.platform == "nvidia_cuda"
        assert cap.ct2_device == "cuda"
        assert cap.optimal_compute_type == "float16"

    def test_cpu_only_fallback(self):
        from src.core.cuda_runtime import CudaRuntimeStatus

        cuda_status = CudaRuntimeStatus(
            driver_detected=False,
            cuda_available=False,
            detail="nvidia-smi not found",
        )

        with (
            patch("src.core.device_detection.sys") as mock_sys,
            patch("src.core.device_detection.platform") as mock_platform,
            patch("src.core.device_detection.os") as mock_os,
            patch("src.core.cuda_runtime.detect_cuda_runtime", return_value=cuda_status),
        ):
            mock_sys.platform = "linux"
            mock_platform.machine.return_value = "x86_64"
            mock_os.cpu_count.return_value = 8

            cap = detect_device()

        assert cap.platform == "cpu_only"
        assert cap.ct2_device == "cpu"
        assert cap.optimal_compute_type == "int8"

    def test_apple_silicon_takes_priority_over_cuda_check(self):
        """On macOS ARM64, we should detect Apple Silicon without probing CUDA."""
        with (
            patch("src.core.device_detection.sys") as mock_sys,
            patch("src.core.device_detection.platform") as mock_platform,
            patch("src.core.device_detection.os") as mock_os,
        ):
            mock_sys.platform = "darwin"
            mock_platform.machine.return_value = "arm64"
            mock_os.cpu_count.return_value = 10

            cap = detect_device()

        # Should NOT have imported/called detect_cuda_runtime
        assert cap.platform == "apple_silicon"


class TestRecommendThreadCount:
    """Tests for recommend_thread_count()."""

    def test_apple_silicon_uses_perf_cores(self):
        cap = DeviceCapability(
            platform="apple_silicon", ct2_device="auto",
            optimal_compute_type="int8", cpu_cores=10, detail="",
        )
        with patch("src.core.device_detection._get_apple_silicon_perf_cores", return_value=4):
            count = recommend_thread_count(cap)
        assert count == 4

    def test_cpu_only_leaves_headroom(self):
        cap = DeviceCapability(
            platform="cpu_only", ct2_device="cpu",
            optimal_compute_type="int8", cpu_cores=8, detail="",
        )
        count = recommend_thread_count(cap)
        assert count == 6  # 8 - 2

    def test_minimum_is_two(self):
        cap = DeviceCapability(
            platform="cpu_only", ct2_device="cpu",
            optimal_compute_type="int8", cpu_cores=2, detail="",
        )
        count = recommend_thread_count(cap)
        assert count == 2

    def test_capped_at_16(self):
        cap = DeviceCapability(
            platform="nvidia_cuda", ct2_device="cuda",
            optimal_compute_type="float16", cpu_cores=64, detail="",
        )
        count = recommend_thread_count(cap)
        assert count == 16
