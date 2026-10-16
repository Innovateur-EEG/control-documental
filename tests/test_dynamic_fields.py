"""Tests for JSON-driven dynamic field widget configuration."""

import pytest

from app.utils.dynamic_fields import (
    SUPPORTED_FIELD_TYPES,
    checkbox_value,
    dependent_options,
    field_is_visible,
    field_config,
    number_widget_options,
    text_widget_options,
    validate_field_config,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, True),
        (False, False),
        (1, True),
        (0, False),
        ("true", True),
        (" Sí ", True),
        ("false", False),
        ("0", False),
        ("", False),
        (None, False),
    ],
)
def test_checkbox_value_normalizes_stored_values(value, expected):
    assert checkbox_value(value) is expected


def test_field_config_falls_back_to_empty_mapping():
    assert field_config({"section": "Identity"}) == {"section": "Identity"}
    assert field_config(None) == {}
    assert field_config("not-json-object") == {}


def test_supported_field_types_match_current_capture_controls():
    assert SUPPORTED_FIELD_TYPES == (
        "Texto",
        "Fecha",
        "Número",
        "Opciones",
        "Selección única",
        "Selección múltiple",
        "Casilla",
    )


def test_text_widget_options_accept_placeholder_and_max_chars():
    assert text_widget_options(
        {"placeholder": "Enter a name", "max_chars": 80, "unknown": "ignored"}
    ) == {"placeholder": "Enter a name", "max_chars": 80}


@pytest.mark.parametrize("value", [0, -1, 1.5, True, "10"])
def test_text_widget_options_reject_invalid_max_chars(value):
    with pytest.raises(ValueError, match="max_chars"):
        text_widget_options({"max_chars": value})


def test_number_widget_options_accepts_bounds_and_step():
    assert number_widget_options(
        {"min_value": 0.0, "max_value": 100.0, "step": 0.5}
    ) == {"min_value": 0, "max_value": 100, "step": 0.5}


@pytest.mark.parametrize(
    "config",
    [
        {"min_value": "0"},
        {"max_value": True},
        {"step": 0},
        {"step": -1},
        {"min_value": 10, "max_value": 1},
    ],
)
def test_number_widget_options_rejects_invalid_constraints(config):
    with pytest.raises(ValueError):
        number_widget_options(config)



@pytest.mark.parametrize(
    ("field_type", "config"),
    [
        ("Texto", {"max_chars": 120, "placeholder": "Name"}),
        ("Número", {"min_value": 0, "max_value": 10, "step": 1}),
        ("Casilla", {"default": False}),
        ("Selección única", {"options_map": {"depends_on": "tipo", "map": {}}}),
    ],
)
def test_validate_field_config_accepts_supported_type_settings(field_type, config):
    assert validate_field_config(field_type, config) is None


def test_validate_field_config_rejects_unknown_type():
    with pytest.raises(ValueError, match="Unsupported field type"):
        validate_field_config("Color picker", {})


@pytest.mark.parametrize(
    ("config", "values", "expected"),
    [
        ({}, {}, True),
        ({"visible_if": {"field": "tipo", "equals": "Moral"}}, {"tipo": "Moral"}, True),
        ({"visible_if": {"field": "tipo", "equals": "Moral"}}, {"tipo": "Fisica"}, False),
        ({"visible_if": {"field": "roles", "equals": "Admin"}}, {"roles": ["User", "Admin"]}, True),
        ({"visible_if": {"field": "tipo", "equals": "Moral"}}, {}, False),
    ],
)
def test_field_is_visible_evaluates_configured_condition(config, values, expected):
    assert field_is_visible(config, values) is expected


def test_field_is_visible_rejects_malformed_condition():
    with pytest.raises(ValueError, match="visible_if"):
        field_is_visible({"visible_if": {"field": "tipo"}}, {"tipo": "Moral"})


def test_dependent_options_resolve_selected_parent_and_fallback():
    config = {"options_map": {"depends_on": "tipo", "map": {"Moral": ["RFC", "Acta"], "Fisica": ["CURP"]}}}
    assert dependent_options(config, {"tipo": "Moral"}, ["default"]) == ["RFC", "Acta"]
    assert dependent_options(config, {"tipo": "Fisica"}) == ["CURP"]
    assert dependent_options(config, {"tipo": "Otro"}) == []
    assert dependent_options({}, {}, ["A"]) == ["A"]


def test_dependent_options_reject_malformed_configuration():
    with pytest.raises(ValueError, match="options_map"):
        dependent_options({"options_map": {"depends_on": "tipo"}}, {})
