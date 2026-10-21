"""Regression tests for storage-backed persistence failure handling."""

import pytest

from app.utils.evidencias import upload_then_persist


def test_failed_storage_upload_rolls_back_without_persisting_or_compensating():
    calls = []

    def upload():
        calls.append("upload")
        raise RuntimeError("simulated storage failure")

    with pytest.raises(RuntimeError, match="simulated storage failure"):
        upload_then_persist(
            upload,
            lambda: calls.append("persist"),
            lambda: calls.append("rollback"),
            lambda: calls.append("compensate"),
        )

    assert calls == ["upload", "rollback"]


def test_persistence_failure_rolls_back_and_compensates_uploaded_object():
    calls = []

    def persist():
        calls.append("persist")
        raise RuntimeError("simulated database failure")

    with pytest.raises(RuntimeError, match="simulated database failure"):
        upload_then_persist(
            lambda: calls.append("upload"),
            persist,
            lambda: calls.append("rollback"),
            lambda: calls.append("compensate"),
        )

    assert calls == ["upload", "persist", "rollback", "compensate"]


def test_compensation_failure_does_not_mask_persistence_failure():
    calls = []

    def persist():
        raise RuntimeError("simulated database failure")

    def compensate():
        calls.append("compensate")
        raise RuntimeError("simulated cleanup failure")

    with pytest.raises(RuntimeError, match="simulated database failure"):
        upload_then_persist(
            lambda: calls.append("upload"),
            persist,
            lambda: calls.append("rollback"),
            compensate,
        )

    assert calls == ["upload", "compensate"] or calls == ["upload", "rollback", "compensate"]


def test_successful_storage_upload_persists_without_compensation():
    calls = []

    upload_then_persist(
        lambda: calls.append("upload"),
        lambda: calls.append("persist"),
        lambda: calls.append("rollback"),
        lambda: calls.append("compensate"),
    )

    assert calls == ["upload", "persist"]
