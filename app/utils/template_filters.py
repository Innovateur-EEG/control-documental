"""Custom Jinja2 filters for document templates.

These helpers keep checkbox selection and optional text prefixes out of DOCX
template control-flow blocks. Empty values never select a checkbox.
"""
import unicodedata


def _normalize(value):
    """Normalize a value for accent- and case-insensitive comparison."""
    return "".join(
        char
        for char in unicodedata.normalize("NFD", str(value).strip().lower())
        if unicodedata.category(char) != "Mn"
    )


def mark_filter(actual_value, target_value=None, is_not=False, mark="X", default=""):
    """Return a mark when a value matches a target or its truth value.

    Empty/None strings never produce a mark, including when is_not=True.
    Collections are supported on either side of the comparison.
    """
    if actual_value is None:
        return default
    if isinstance(actual_value, str) and not actual_value.strip():
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


def mark_not_filter(actual_value, target_value=None, mark="X", default=""):
    """Return a mark when a non-empty value does not match the target."""
    return mark_filter(actual_value, target_value, is_not=True, mark=mark, default=default)


def prefix_filter(value, prefix=""):
    """Add a prefix only when the value is present and nonblank."""
    if value is None:
        return ""
    text = str(value).strip()
    return f"{prefix}{text}" if text else ""
