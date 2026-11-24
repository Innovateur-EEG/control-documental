"""Helpers for interpreting JSON-driven dynamic capture field configuration."""

from __future__ import annotations

import datetime
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



def field_is_visible(config: dict, values: dict) -> bool:
    """Evaluate a field's optional equality-based visibility rule."""
    condition = config.get("visible_if")
    if condition is None:
        return True
    if not isinstance(condition, dict) or not condition.get("field") or "equals" not in condition:
        raise ValueError("'visible_if' must contain 'field' and 'equals'.")
    actual = values.get(str(condition["field"]))
    expected = condition["equals"]
    return expected in actual if isinstance(actual, list) else actual == expected


def dependent_options(config: dict, values: dict, fallback: list | None = None) -> list:
    """Resolve options from an optional dependency map; otherwise use base options."""
    mapping = config.get("options_map")
    if mapping is None:
        return list(fallback or [])
    if not isinstance(mapping, dict) or not mapping.get("depends_on") or not isinstance(mapping.get("map"), dict):
        raise ValueError("'options_map' must contain 'depends_on' and an options 'map'.")
    selected = values.get(str(mapping["depends_on"]))
    options = mapping["map"].get(str(selected), [])
    if not isinstance(options, list) or any(not isinstance(option, (str, int, float)) for option in options):
        raise ValueError("Each dependent option list must contain scalar values.")
    return options


def validate_submitted_value(config: dict, value: Any, values: dict, base_options: list | None = None) -> bool:
    """Return whether a submitted selection belongs to its currently allowed options."""
    mapping = config.get("options_map")
    if mapping is None:
        return True
    options = dependent_options(config, values, base_options)
    if isinstance(value, list):
        return all(item in options for item in value)
    return value in options


def validate_capture_submission(
    fields: list[dict],
    submitted_values: dict,
    values: dict,
    today: datetime.date | None = None,
) -> list[str]:
    """Validate visible submitted capture values before persistence."""
    current_date = today or datetime.date.today()
    submitted_values = submitted_values or {}
    validation_values = dict(values or {})
    validation_values.update(submitted_values)
    errors = []

    for field in fields:
        key = field.get("key")
        if not key or key not in submitted_values:
            # Hidden fields are omitted by the UI and must not block saving.
            continue

        value = submitted_values.get(key)
        label = field.get("label") or key
        config = field_config(field.get("config"))
        field_type = field.get("type")

        empty = value is None or value == "" or value == []
        if field_type == "Casilla" and not checkbox_value(value):
            empty = True
        if config.get("required", False) and empty:
            errors.append(f"❌ '{label}' es obligatorio.")

        if "options_map" in config:
            try:
                valid = validate_submitted_value(
                    config,
                    value,
                    validation_values,
                    field.get("options") or [],
                )
                if not valid:
                    errors.append(
                        f"❌ '{label}' contiene una opción no permitida para la selección actual."
                    )
            except ValueError as exc:
                errors.append(f"❌ Configuración inválida para '{label}': {exc}")

        if field_type == "Fecha" and isinstance(value, datetime.date):
            rule = field.get("validation_rule")
            if rule == "max_90_dias":
                difference = (current_date - value).days
                if difference > 90:
                    errors.append(f"❌ '{label}' excede 90 días de antigüedad.")
                elif difference < 0:
                    errors.append(f"❌ '{label}' no puede ser fecha futura.")
            elif rule == "vigente_futuro" and value < current_date:
                errors.append(f"❌ '{label}' ya está vencido.")

    return errors


def merge_capture_values(existing: dict, submitted: dict) -> dict:
    """Merge visible submitted fields while retaining unrelated/hidden saved values."""
    merged = dict(existing or {})
    merged.update(submitted or {})
    return merged


def validate_field_config(field_type: str, config: dict) -> None:
    """Validate the type-specific widget options before an administrator saves them."""
    if field_type not in SUPPORTED_FIELD_TYPES:
        raise ValueError(f"Unsupported field type: {field_type!r}.")
    if field_type == "Texto":
        text_widget_options(config)
    elif field_type == "Número":
        number_widget_options(config)
    if "visible_if" in config:
        condition = config["visible_if"]
        if not isinstance(condition, dict) or not condition.get("field") or "equals" not in condition:
            raise ValueError("'visible_if' must contain 'field' and 'equals'.")
    if "options_map" in config:
        mapping = config["options_map"]
        if field_type not in ("Opciones", "Selección única", "Selección múltiple"):
            raise ValueError("'options_map' is only supported for selection fields.")
        if not isinstance(mapping, dict) or not mapping.get("depends_on") or not isinstance(mapping.get("map"), dict):
            raise ValueError("'options_map' must contain 'depends_on' and an options 'map'.")
        for options in mapping["map"].values():
            if not isinstance(options, list) or any(not isinstance(option, (str, int, float)) for option in options):
                raise ValueError("Each dependent option list must contain scalar values.")
