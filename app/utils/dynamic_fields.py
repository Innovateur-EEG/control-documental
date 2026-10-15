"""Helpers for interpreting JSON-driven dynamic capture field configuration."""

from __future__ import annotations

from numbers import Real
from typing import Any


SUPPORTED_FIELD_TYPES = (
    "Texto",
    "Fecha",
    "Número",
    "Opciones",
    "Selección única",
    "Selección múltiple",
    "Casilla",
)


def field_config(value: Any) -> dict:
    """Return a safe mapping for a field's JSON configuration."""
    return value if isinstance(value, dict) else {}


def checkbox_value(value: Any) -> bool:
    """Normalize stored checkbox values without treating the string 'false' as true."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, Real):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes", "sí", "si", "on"}:
            return True
        if normalized in {"", "false", "0", "no", "off", "none", "null"}:
            return False
    return bool(value)


def text_widget_options(config: dict) -> dict:
    """Build supported Streamlit text-input options from JSON configuration."""
    options = {}
    placeholder = config.get("placeholder")
    if isinstance(placeholder, str):
        options["placeholder"] = placeholder

    max_chars = config.get("max_chars")
    if max_chars is not None:
        if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 1:
            raise ValueError("'max_chars' must be a positive integer.")
        options["max_chars"] = max_chars
    return options


def number_widget_options(config: dict) -> dict:
    """Build validated numeric-input constraints from JSON configuration."""
    options = {}
    for key in ("min_value", "max_value", "step"):
        value = config.get(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError(f"'{key}' must be a number.")
        options[key] = float(value)

    if "step" in options and options["step"] <= 0:
        raise ValueError("'step' must be greater than zero.")
    if (
        "min_value" in options
        and "max_value" in options
        and options["min_value"] > options["max_value"]
    ):
        raise ValueError("'min_value' cannot exceed 'max_value'.")
    return options



def validate_field_config(field_type: str, config: dict) -> None:
    """Validate the type-specific widget options before an administrator saves them."""
    if field_type not in SUPPORTED_FIELD_TYPES:
        raise ValueError(f"Unsupported field type: {field_type!r}.")
    if field_type == "Texto":
        text_widget_options(config)
    elif field_type == "Número":
        number_widget_options(config)
