"""Custom Jinja2 filters for document templates.

These helpers keep checkbox selection and optional text prefixes out of DOCX
template control-flow blocks. Empty values never select a checkbox.
"""
import unicodedata

from jinja2 import Undefined


def _is_empty(value):
    """Return whether a value is missing or blank, including Jinja undefineds."""
    return (
        value is None
        or isinstance(value, Undefined)
        or (isinstance(value, str) and not value.strip())
    )


def _normalize(value):
    """Normalize a value for accent- and case-insensitive comparison."""
    return "".join(
        char
        for char in unicodedata.normalize("NFD", str(value).strip().lower())
        if unicodedata.category(char) != "Mn"
    )


def mark_filter(actual_value, target_value=None, is_not=False, mark="X", default=""):
    """Return a mark when a value matches a target or its truth value.

    Missing or blank actual values never produce a mark, including when
    is_not=True. Collections are supported on either side of the comparison.
    """
    if _is_empty(actual_value):
        return default

    if target_value is None:
        matches = bool(actual_value)
    elif isinstance(actual_value, (list, tuple, set)):
        target = _normalize(target_value)
        matches = target in {_normalize(item) for item in actual_value}
    elif isinstance(target_value, (list, tuple, set)):
        actual = _normalize(actual_value)
        matches = actual in {_normalize(item) for item in target_value}
    else:
        matches = _normalize(actual_value) == _normalize(target_value)

    selected = not matches if is_not else matches
    return mark if selected else default


def mark_not_filter(actual_value, target_value=None, is_not=True, mark="X", default=""):
    """Compatibility alias for mark_filter with inverse matching enabled by default.

    Accepts is_not explicitly so existing templates using mark_not(..., is_not=True)
    continue to work. Prefer mark(..., is_not=True) for new templates.
    """
    return mark_filter(actual_value, target_value, is_not=is_not, mark=mark, default=default)


def prefix_filter(value, prefix=""):
    """Add a prefix only when the value is present and nonblank."""
    if _is_empty(value):
        return ""
    text = str(value).strip()
    return f"{prefix}{text}" if text else ""
