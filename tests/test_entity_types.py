"""Regression tests for canonical entity/person type values."""
import pytest

from app.utils.entity_types import (
    PERSON_SCOPES,
    PERSON_TYPES,
    normalize_person_scope,
    normalize_person_type,
    scope_applies,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Fisica", "Fisica"),
        ("fisica", "Fisica"),
        ("FISICA", "Fisica"),
        (" Física ", "Fisica"),
        ("persona física", "Fisica"),
        ("Moral", "Moral"),
        ("moral", "Moral"),
        ("PERSONA MORAL", "Moral"),
    ],
)
def test_person_type_normalizes_known_variants(value, expected):
    assert normalize_person_type(value) == expected


@pytest.mark.parametrize("value", ["", None, "Ambas", "Otro", "Moral/Fisica"])
def test_person_type_rejects_unknown_values(value):
    with pytest.raises(ValueError, match="Tipo de persona no válido|must be a string"):
        normalize_person_type(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Ambas", "Ambas"),
        ("ambas", "Ambas"),
        ("AMBOS", "Ambas"),
        ("both", "Ambas"),
        ("fisica", "Fisica"),
        ("MORAL", "Moral"),
        ("Física", "Fisica"),
    ],
)
def test_person_scope_normalizes_known_variants(value, expected):
    assert normalize_person_scope(value) == expected


def test_canonical_values_are_explicit():
    assert PERSON_TYPES == ("Fisica", "Moral")
    assert PERSON_SCOPES == ("Ambas", "Fisica", "Moral")


@pytest.mark.parametrize(
    ("scope", "person_type", "expected"),
    [
        ("Ambas", "Fisica", True),
        ("ambas", "fisica", True),
        ("fisica", "Fisica", True),
        ("FÍSICA", "fisica", True),
        ("Moral", "fisica", False),
        ("moral", "MORAL", True),
        ("unknown", "Fisica", False),
        ("Fisica", "unknown", False),
    ],
)
def test_scope_applies_handles_legacy_variants_and_fails_closed(scope, person_type, expected):
    assert scope_applies(scope, person_type) is expected
