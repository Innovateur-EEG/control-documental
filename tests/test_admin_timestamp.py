"""Regression tests for dashboard timestamp formatting."""
from datetime import datetime
from types import SimpleNamespace

from app.views.admin_view import _format_fecha_actualizacion


def test_format_fecha_actualizacion_returns_dash_for_missing_document():
    assert _format_fecha_actualizacion(None) == "-"


def test_format_fecha_actualizacion_returns_dash_for_missing_timestamp():
    doc = SimpleNamespace(fecha_actualizacion=None)

    assert _format_fecha_actualizacion(doc) == "-"


def test_format_fecha_actualizacion_formats_existing_timestamp():
    doc = SimpleNamespace(fecha_actualizacion=datetime(2026, 10, 28, 9, 7))

    assert _format_fecha_actualizacion(doc) == "2026-10-28 09:07"
