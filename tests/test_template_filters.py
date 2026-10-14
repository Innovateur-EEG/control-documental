"""Tests for custom Jinja filters used by document templates."""

from app.utils.template_filters import mark_filter, prefix_filter


def test_mark_matches_case_and_accents():
    assert mark_filter("Sí", "si") == "X"
    assert mark_filter("MASCULINO", "Masculino") == "X"


def test_mark_does_not_mark_missing_values_even_when_negated():
    assert mark_filter(None, "Mexicana", is_not=True) == ""
    assert mark_filter("   ", "Mexicana", is_not=True) == ""


def test_mark_supports_boolean_and_exclusion_checks():
    assert mark_filter(True) == "X"
    assert mark_filter(False, is_not=True) == "X"
    assert mark_filter("Bodega Industrial", ["Casa", "Departamento"], is_not=True) == "X"
    assert mark_filter(["Casa", "Oficinas"], "oficinas") == "X"


def test_mark_supports_custom_mark_and_default():
    assert mark_filter("Casa", "Departamento", mark="✓", default="-") == "-"
    assert mark_filter("Casa", "casa", mark="✓", default="-") == "✓"


def test_prefix_omits_prefix_for_empty_values():
    assert prefix_filter(" 4B ", ", interior: ") == ", interior: 4B"
    assert prefix_filter(None, ", interior: ") == ""
    assert prefix_filter("   ", "C.P. ") == ""
    assert prefix_filter("03100", "C.P. ") == "C.P. 03100"
