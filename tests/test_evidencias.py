"""Regression tests for evidence upload failure handling."""

import pytest

from app.utils.evidencias import upload_then_persist


def test_failed_storage_upload_rolls_back_without_persisting_document():
    calls = []
    
    def upload():
        calls.append("upload")
        raise RuntimeError("simulated storage failure")

    def persist():
        calls.append("persist")

    def rollback():
        calls.append("rollback")

    with pytest.raises(RuntimeError, match="simulated storage failure"):
        upload_then_persist(upload, persist, rollback)

    assert calls == ["upload", "rollback"]


def test_successful_storage_upload_persists_document():
    calls = []

    upload_then_persist(
        lambda: calls.append("upload"),
        lambda: calls.append("persist"),
        lambda: calls.append("rollback"),
    )

    assert calls == ["upload", "persist"]
