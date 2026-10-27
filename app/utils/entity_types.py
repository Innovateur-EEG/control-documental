"""Canonical values and safe normalization for entity/person applicability.

Canonical persisted values:
- personas.tipo: Fisica | Moral
- field/evidence tipo_persona: Ambas | Fisica | Moral

Only known aliases are normalized. Unknown values raise ValueError rather than
silently being treated as a physical person.
"""
import unicodedata


PERSON_TYPES = ("Fisica", "Moral")
PERSON_SCOPES = ("Ambas", "Fisica", "Moral")


def _fold(value):
    if not isinstance(value, str):
        raise ValueError("Entity type must be a string.")
    value = unicodedata.normalize("NFKD", value.strip().casefold())
    return "".join(char for char in value if not unicodedata.combining(char))


def normalize_person_type(value):
    """Return canonical Fisica/Moral for recognized spellings and aliases."""
    folded = _fold(value)
    aliases = {
        "fisica": "Fisica",
        "persona fisica": "Fisica",
        "moral": "Moral",
        "persona moral": "Moral",
    }
    if folded not in aliases:
        raise ValueError(f"Tipo de persona no válido: {value!r}. Use Fisica o Moral.")
    return aliases[folded]


def normalize_person_scope(value):
    """Return canonical Ambas/Fisica/Moral for field/evidence applicability."""
    folded = _fold(value)
    if folded in {"ambas", "ambos", "both"}:
        return "Ambas"
    return normalize_person_type(value)


def scope_applies(scope, person_type):
    """Safely compare a field/evidence scope with an entity's type."""
    try:
        normalized_scope = normalize_person_scope(scope)
        normalized_person_type = normalize_person_type(person_type)
    except ValueError:
        return False
    return normalized_scope == "Ambas" or normalized_scope == normalized_person_type
