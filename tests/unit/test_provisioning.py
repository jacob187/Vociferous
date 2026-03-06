"""
Tests for the model provisioning pipeline.

Covers:
  - src.provisioning.core (download_model_file, provision_asr_model, provision_slm_model)
  - src.provisioning.requirements (check_dependencies, verify_environment_integrity)
  - src.core.model_registry (catalog lookups, data integrity)

All HuggingFace downloads are mocked — no network calls.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.model_registry import (
    ASR_MODELS,
    SILERO_VAD,
    SLM_MODELS,
    ASRModel,
    SLMModel,
    VADModel,
    get_asr_model,
    get_model_catalog,
    get_slm_model,
)
from src.provisioning.core import (
    IntegrityError,
    ProvisioningError,
    _compute_sha256,
    _verify_integrity,
    download_model_file,
    provision_asr_model,
    provision_slm_model,
    provision_vad_model,
)
from src.provisioning.requirements import (
    REQUIRED_DEPENDENCIES,
    check_dependencies,
    get_missing_dependency_message,
    verify_environment_integrity,
)

# ======================================================================
# Model Registry
# ======================================================================


class TestModelRegistry:
    """Catalog integrity and lookup behaviour."""

    def test_asr_catalog_not_empty(self):
        assert len(ASR_MODELS) > 0

    def test_slm_catalog_not_empty(self):
        assert len(SLM_MODELS) > 0

    def test_asr_model_ids_match_keys(self):
        for key, model in ASR_MODELS.items():
            assert model.id == key, f"Key '{key}' != model.id '{model.id}'"

    def test_slm_model_ids_match_keys(self):
        for key, model in SLM_MODELS.items():
            assert model.id == key, f"Key '{key}' != model.id '{model.id}'"

    def test_asr_models_have_required_fields(self):
        for model in ASR_MODELS.values():
            assert model.name
            assert model.filename
            assert model.repo
            assert model.size_mb > 0
            assert model.tier in ("fast", "balanced", "quality")

    def test_slm_models_have_required_fields(self):
        for model in SLM_MODELS.values():
            assert model.name
            assert model.filename
            assert model.repo
            assert model.size_mb > 0
            assert model.tier in ("fast", "balanced", "quality", "pro")
            assert model.quant  # non-empty quant string

    def test_asr_filenames_are_ggml(self):
        """ASR models must be GGML binaries."""
        for model in ASR_MODELS.values():
            assert model.filename.startswith("ggml-"), model.filename
            assert model.filename.endswith(".bin"), model.filename

    def test_slm_filenames_are_gguf(self):
        """SLM models must be GGUF files."""
        for model in SLM_MODELS.values():
            assert model.filename.endswith(".gguf"), model.filename

    def test_get_asr_model_found(self):
        key = next(iter(ASR_MODELS))
        result = get_asr_model(key)
        assert result is not None
        assert result.id == key

    def test_get_asr_model_missing(self):
        assert get_asr_model("nonexistent-model") is None

    def test_get_slm_model_found(self):
        key = next(iter(SLM_MODELS))
        result = get_slm_model(key)
        assert result is not None
        assert result.id == key

    def test_get_slm_model_missing(self):
        assert get_slm_model("nonexistent-model") is None

    def test_get_model_catalog_structure(self):
        catalog = get_model_catalog()
        assert "asr" in catalog
        assert "slm" in catalog
        assert len(catalog["asr"]) == len(ASR_MODELS)
        assert len(catalog["slm"]) == len(SLM_MODELS)

    def test_catalog_entries_are_dicts(self):
        catalog = get_model_catalog()
        for entry in catalog["asr"].values():
            assert isinstance(entry, dict)
            assert "id" in entry
            assert "filename" in entry
        for entry in catalog["slm"].values():
            assert isinstance(entry, dict)
            assert "id" in entry
            assert "filename" in entry

    def test_models_are_frozen(self):
        model = next(iter(ASR_MODELS.values()))
        with pytest.raises(AttributeError):
            model.name = "hacked"

    def test_no_duplicate_filenames_within_type(self):
        asr_filenames = [m.filename for m in ASR_MODELS.values()]
        assert len(asr_filenames) == len(set(asr_filenames)), "Duplicate ASR filenames"
        slm_filenames = [m.filename for m in SLM_MODELS.values()]
        assert len(slm_filenames) == len(set(slm_filenames)), "Duplicate SLM filenames"

    def test_no_duplicate_repos_per_asr(self):
        """All ASR models currently come from the same repo — sanity check."""
        repos = {m.repo for m in ASR_MODELS.values()}
        assert len(repos) >= 1  # at least one repo

    def test_size_ordering_within_asr(self):
        """Models should be listed from smallest to largest."""
        sizes = [m.size_mb for m in ASR_MODELS.values()]
        assert sizes == sorted(sizes), "ASR models not in ascending size order"

    def test_asr_sha256_format(self):
        """All ASR models must have valid 64-char hex SHA-256 hashes."""
        import re

        for key, model in ASR_MODELS.items():
            assert model.sha256 is not None, f"ASR model '{key}' missing sha256"
            assert re.fullmatch(r"[0-9a-f]{64}", model.sha256), (
                f"ASR model '{key}' has malformed sha256: {model.sha256!r}"
            )

    def test_slm_sha256_format(self):
        """All SLM models must have valid 64-char hex SHA-256 hashes."""
        import re

        for key, model in SLM_MODELS.items():
            assert model.sha256 is not None, f"SLM model '{key}' missing sha256"
            assert re.fullmatch(r"[0-9a-f]{64}", model.sha256), (
                f"SLM model '{key}' has malformed sha256: {model.sha256!r}"
            )

    def test_vad_model_entry(self):
        """SILERO_VAD constant has required fields and valid sha256."""
        import re

        assert isinstance(SILERO_VAD, VADModel)
        assert SILERO_VAD.filename == "silero_vad.onnx"
        assert SILERO_VAD.repo  # non-empty
        assert SILERO_VAD.size_mb > 0
        assert SILERO_VAD.sha256 is not None
        assert re.fullmatch(r"[0-9a-f]{64}", SILERO_VAD.sha256)

    def test_no_duplicate_sha256_across_all_models(self):
        """Each model file must have a unique hash."""
        all_hashes = [m.sha256 for m in ASR_MODELS.values() if m.sha256]
        all_hashes += [m.sha256 for m in SLM_MODELS.values() if m.sha256]
        if SILERO_VAD.sha256:
            all_hashes.append(SILERO_VAD.sha256)
        assert len(all_hashes) == len(set(all_hashes)), "Duplicate SHA-256 hash in registry"


# ======================================================================
# download_model_file
# ======================================================================


class TestDownloadModelFile:
    """Core download function — hf_hub_download is always mocked."""

    HF_PATCH = "huggingface_hub.hf_hub_download"

    @patch(HF_PATCH)
    def test_successful_download(self, mock_hf: MagicMock, tmp_path: Path):
        expected = tmp_path / "model.bin"
        mock_hf.return_value = str(expected)

        result = download_model_file(
            repo_id="org/repo",
            filename="model.bin",
            target_dir=tmp_path,
        )

        assert result == expected
        mock_hf.assert_called_once_with(
            repo_id="org/repo",
            filename="model.bin",
            local_dir=str(tmp_path),
        )

    @patch(HF_PATCH)
    def test_creates_target_directory(self, mock_hf: MagicMock, tmp_path: Path):
        nested = tmp_path / "deep" / "nested" / "dir"
        mock_hf.return_value = str(nested / "model.bin")

        download_model_file(
            repo_id="org/repo",
            filename="model.bin",
            target_dir=nested,
        )

        assert nested.exists()

    @patch(HF_PATCH)
    def test_progress_callback_called(self, mock_hf: MagicMock, tmp_path: Path):
        mock_hf.return_value = str(tmp_path / "model.bin")
        callback = MagicMock()

        download_model_file(
            repo_id="org/repo",
            filename="model.bin",
            target_dir=tmp_path,
            progress_callback=callback,
        )

        # Should be called at least for "Downloading..." and "Downloaded...successfully"
        assert callback.call_count >= 2
        first_msg = callback.call_args_list[0][0][0]
        assert "Downloading" in first_msg
        last_msg = callback.call_args_list[-1][0][0]
        assert "successfully" in last_msg

    @patch(HF_PATCH)
    def test_no_callback_no_crash(self, mock_hf: MagicMock, tmp_path: Path):
        mock_hf.return_value = str(tmp_path / "model.bin")

        # Should not raise when progress_callback is None
        result = download_model_file(
            repo_id="org/repo",
            filename="model.bin",
            target_dir=tmp_path,
            progress_callback=None,
        )
        assert result == tmp_path / "model.bin"

    @patch(HF_PATCH)
    def test_hf_error_wraps_in_provisioning_error(self, mock_hf: MagicMock, tmp_path: Path):
        mock_hf.side_effect = ConnectionError("network down")

        with pytest.raises(ProvisioningError, match="Failed to download"):
            download_model_file(
                repo_id="org/repo",
                filename="model.bin",
                target_dir=tmp_path,
            )

    @patch(HF_PATCH)
    def test_provisioning_error_preserves_cause(self, mock_hf: MagicMock, tmp_path: Path):
        original = OSError("disk full")
        mock_hf.side_effect = original

        with pytest.raises(ProvisioningError) as exc_info:
            download_model_file(
                repo_id="org/repo",
                filename="model.bin",
                target_dir=tmp_path,
            )
        assert exc_info.value.__cause__ is original

    @patch(HF_PATCH)
    def test_callback_not_called_on_failure(self, mock_hf: MagicMock, tmp_path: Path):
        mock_hf.side_effect = RuntimeError("boom")
        callback = MagicMock()

        with pytest.raises(ProvisioningError):
            download_model_file(
                repo_id="org/repo",
                filename="model.bin",
                target_dir=tmp_path,
                progress_callback=callback,
            )

        # "Downloading..." message fires before attempt, "Downloaded...successfully" does NOT
        assert callback.call_count == 1
        assert "Downloading" in callback.call_args_list[0][0][0]


# ======================================================================
# SHA-256 integrity verification
# ======================================================================


class TestIntegrityVerification:
    """_compute_sha256, _verify_integrity, and download_model_file with hashes."""

    def test_compute_sha256_known_content(self, tmp_path: Path):
        """Hash of known content must match pre-computed value."""
        import hashlib

        content = b"hello world"
        expected = hashlib.sha256(content).hexdigest()
        f = tmp_path / "test.bin"
        f.write_bytes(content)
        assert _compute_sha256(f) == expected

    def test_compute_sha256_empty_file(self, tmp_path: Path):
        """Empty file has the well-known SHA-256 of empty bytes."""
        import hashlib

        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        assert _compute_sha256(f) == hashlib.sha256(b"").hexdigest()

    def test_verify_integrity_pass(self, tmp_path: Path):
        """No exception when hash matches."""
        import hashlib

        content = b"good data"
        expected = hashlib.sha256(content).hexdigest()
        f = tmp_path / "ok.bin"
        f.write_bytes(content)
        _verify_integrity(f, expected)  # should not raise
        assert f.exists()  # file preserved

    def test_verify_integrity_mismatch_deletes_and_raises(self, tmp_path: Path):
        """Mismatched hash: file deleted, IntegrityError raised."""
        f = tmp_path / "bad.bin"
        f.write_bytes(b"corrupted data")

        with pytest.raises(IntegrityError, match="SHA-256 mismatch"):
            _verify_integrity(f, "0" * 64)

        assert not f.exists(), "Corrupted file should be deleted"

    @patch("huggingface_hub.hf_hub_download")
    def test_download_with_matching_hash(self, mock_hf: MagicMock, tmp_path: Path):
        """Full pipeline: download + verification passes when hash matches."""
        import hashlib

        content = b"model weights here"
        expected_hash = hashlib.sha256(content).hexdigest()
        model_path = tmp_path / "model.bin"
        model_path.write_bytes(content)
        mock_hf.return_value = str(model_path)

        result = download_model_file(
            repo_id="org/repo",
            filename="model.bin",
            target_dir=tmp_path,
            expected_sha256=expected_hash,
        )
        assert result == model_path
        assert model_path.exists()

    @patch("huggingface_hub.hf_hub_download")
    def test_download_with_mismatched_hash(self, mock_hf: MagicMock, tmp_path: Path):
        """Full pipeline: mismatched hash deletes file and raises IntegrityError."""
        model_path = tmp_path / "model.bin"
        model_path.write_bytes(b"corrupted download")
        mock_hf.return_value = str(model_path)

        with pytest.raises(IntegrityError, match="SHA-256 mismatch"):
            download_model_file(
                repo_id="org/repo",
                filename="model.bin",
                target_dir=tmp_path,
                expected_sha256="0" * 64,
            )
        assert not model_path.exists()

    @patch("huggingface_hub.hf_hub_download")
    def test_download_with_none_hash_skips_verification(self, mock_hf: MagicMock, tmp_path: Path):
        """When expected_sha256 is None, verification is skipped entirely."""
        mock_hf.return_value = str(tmp_path / "model.bin")

        result = download_model_file(
            repo_id="org/repo",
            filename="model.bin",
            target_dir=tmp_path,
            expected_sha256=None,
        )
        # File doesn't exist (mock), but no IntegrityError is raised
        assert result == tmp_path / "model.bin"

    @patch("huggingface_hub.hf_hub_download")
    def test_download_verification_callback(self, mock_hf: MagicMock, tmp_path: Path):
        """Progress callback fires 'Verifying integrity' message."""
        import hashlib

        content = b"valid content"
        model_path = tmp_path / "model.bin"
        model_path.write_bytes(content)
        mock_hf.return_value = str(model_path)
        callback = MagicMock()

        download_model_file(
            repo_id="org/repo",
            filename="model.bin",
            target_dir=tmp_path,
            expected_sha256=hashlib.sha256(content).hexdigest(),
            progress_callback=callback,
        )

        messages = [call[0][0] for call in callback.call_args_list]
        assert any("Verifying" in m for m in messages), f"Expected 'Verifying' in {messages}"


# ======================================================================
# provision_asr_model / provision_slm_model / provision_vad_model
# ======================================================================


class TestProvisionWrappers:
    """Thin wrappers that delegate to download_model_file.

    _verify_integrity is patched out because these tests focus on
    delegation behaviour, not SHA-256 verification (tested above).
    The models in the registry now carry non-None sha256 values, so
    without the patch the mock paths would trigger file-not-found.
    """

    HF_PATCH = "huggingface_hub.hf_hub_download"
    VERIFY_PATCH = "src.provisioning.core._verify_integrity"

    @patch(VERIFY_PATCH)
    @patch(HF_PATCH)
    def test_provision_asr_delegates(self, mock_hf: MagicMock, _mock_verify: MagicMock, tmp_path: Path):
        model = next(iter(ASR_MODELS.values()))
        mock_hf.return_value = str(tmp_path / model.filename)

        result = provision_asr_model(model, tmp_path)

        mock_hf.assert_called_once_with(
            repo_id=model.repo,
            filename=model.filename,
            local_dir=str(tmp_path),
        )
        assert result == tmp_path / model.filename

    @patch(VERIFY_PATCH)
    @patch(HF_PATCH)
    def test_provision_slm_delegates(self, mock_hf: MagicMock, _mock_verify: MagicMock, tmp_path: Path):
        model = next(iter(SLM_MODELS.values()))
        mock_hf.return_value = str(tmp_path / model.filename)

        result = provision_slm_model(model, tmp_path)

        mock_hf.assert_called_once_with(
            repo_id=model.repo,
            filename=model.filename,
            local_dir=str(tmp_path),
        )
        assert result == tmp_path / model.filename

    @patch(VERIFY_PATCH)
    @patch(HF_PATCH)
    def test_provision_vad_delegates(self, mock_hf: MagicMock, _mock_verify: MagicMock, tmp_path: Path):
        mock_hf.return_value = str(tmp_path / SILERO_VAD.filename)

        result = provision_vad_model(SILERO_VAD, tmp_path)

        mock_hf.assert_called_once_with(
            repo_id=SILERO_VAD.repo,
            filename=SILERO_VAD.filename,
            local_dir=str(tmp_path),
        )
        assert result == tmp_path / SILERO_VAD.filename

    @patch(VERIFY_PATCH)
    @patch(HF_PATCH)
    def test_provision_asr_with_callback(self, mock_hf: MagicMock, _mock_verify: MagicMock, tmp_path: Path):
        model = next(iter(ASR_MODELS.values()))
        mock_hf.return_value = str(tmp_path / model.filename)
        cb = MagicMock()

        provision_asr_model(model, tmp_path, progress_callback=cb)

        assert cb.call_count >= 2

    @patch(VERIFY_PATCH)
    @patch(HF_PATCH)
    def test_provision_slm_with_callback(self, mock_hf: MagicMock, _mock_verify: MagicMock, tmp_path: Path):
        model = next(iter(SLM_MODELS.values()))
        mock_hf.return_value = str(tmp_path / model.filename)
        cb = MagicMock()

        provision_slm_model(model, tmp_path, progress_callback=cb)

        assert cb.call_count >= 2

    @patch(VERIFY_PATCH)
    @patch(HF_PATCH)
    def test_provision_asr_propagates_error(self, mock_hf: MagicMock, _mock_verify: MagicMock, tmp_path: Path):
        mock_hf.side_effect = Exception("fail")
        model = next(iter(ASR_MODELS.values()))

        with pytest.raises(ProvisioningError):
            provision_asr_model(model, tmp_path)

    @patch(VERIFY_PATCH)
    @patch(HF_PATCH)
    def test_provision_slm_propagates_error(self, mock_hf: MagicMock, _mock_verify: MagicMock, tmp_path: Path):
        mock_hf.side_effect = Exception("fail")
        model = next(iter(SLM_MODELS.values()))

        with pytest.raises(ProvisioningError):
            provision_slm_model(model, tmp_path)


# ======================================================================
# Requirements checking
# ======================================================================


class TestRequirements:
    """Dependency detection and environment verification."""

    def test_check_dependencies_default_list(self):
        """Should check the REQUIRED_DEPENDENCIES list by default."""
        installed, missing = check_dependencies()
        assert len(installed) + len(missing) == len(REQUIRED_DEPENDENCIES)

    def test_check_dependencies_custom_list(self):
        installed, missing = check_dependencies(["sys", "os", "nonexistent_pkg_xyz"])
        assert "sys" in installed
        assert "os" in installed
        assert "nonexistent_pkg_xyz" in missing

    def test_check_all_installed(self):
        """All stdlib packages should report as installed."""
        installed, missing = check_dependencies(["sys", "os", "json"])
        assert len(installed) == 3
        assert len(missing) == 0

    def test_check_all_missing(self):
        installed, missing = check_dependencies(["fake_pkg_aaa", "fake_pkg_bbb"])
        assert len(installed) == 0
        assert len(missing) == 2

    def test_check_empty_list(self):
        installed, missing = check_dependencies([])
        assert installed == []
        assert missing == []

    def test_missing_message_empty_when_none_missing(self):
        msg = get_missing_dependency_message([])
        assert msg == ""

    def test_missing_message_contains_package_names(self):
        msg = get_missing_dependency_message(["fake_a", "fake_b"])
        assert "fake_a" in msg
        assert "fake_b" in msg

    def test_missing_message_contains_install_hint(self):
        msg = get_missing_dependency_message(["fake_a"])
        assert "pip install" in msg

    def test_verify_environment_passes_when_all_present(self):
        """If all deps are importable, no error is raised."""
        with patch(
            "src.provisioning.requirements.check_dependencies",
            return_value=(REQUIRED_DEPENDENCIES, []),
        ):
            verify_environment_integrity()  # should not raise

    def test_verify_environment_raises_when_missing(self):
        with patch(
            "src.provisioning.requirements.check_dependencies",
            return_value=([], ["missing_pkg"]),
        ):
            with pytest.raises(RuntimeError, match="Missing runtime dependencies"):
                verify_environment_integrity()

    def test_required_dependencies_list_not_empty(self):
        assert len(REQUIRED_DEPENDENCIES) > 0

    def test_required_dependencies_contains_core_packages(self):
        """Sanity check: key runtime deps are in the list."""
        for pkg in ("pywhispercpp", "huggingface_hub", "numpy"):
            assert pkg in REQUIRED_DEPENDENCIES, f"Expected '{pkg}' in requirements"
