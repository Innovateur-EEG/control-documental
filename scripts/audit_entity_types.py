"""Read-only audit of entity/person type values in the configured database.

This script never updates records. Review its output before any data correction.
Run with: mise exec -- python scripts/audit_entity_types.py
"""
import os
import sys

from sqlalchemy import text

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import get_engine
from app.utils.entity_types import normalize_person_scope, normalize_person_type


COLUMNS = (
    ("personas", "tipo", normalize_person_type),
    ("configuracion_campos", "tipo_persona", normalize_person_scope),
    ("configuracion_evidencias", "tipo_persona", normalize_person_scope),
)


def audit_entity_types(engine):
    """Return rows describing raw values, counts, and safe canonical mappings."""
    results = []
    with engine.connect() as connection:
        for table, column, normalizer in COLUMNS:
            rows = connection.execute(
                text(
                    f'SELECT "{column}" AS raw_value, COUNT(*) AS row_count '
                    f'FROM "{table}" GROUP BY "{column}" ORDER BY "{column}"'
                )
            ).mappings()
            for row in rows:
                raw_value = row["raw_value"]
                try:
                    canonical = normalizer(raw_value)
                    status = "NORMALIZE" if raw_value != canonical else "CANONICAL"
                except ValueError:
                    canonical = None
                    status = "REVIEW REQUIRED"
                results.append(
                    {
                        "table": table,
                        "column": column,
                        "raw_value": raw_value,
                        "count": row["row_count"],
                        "canonical_value": canonical,
                        "status": status,
                    }
                )
    return results


def main():
    rows = audit_entity_types(get_engine())
    if not rows:
        print("No rows found in the audited columns.")
        return
    headers = ("table", "column", "raw_value", "count", "canonical_value", "status")
    widths = {
        key: max(len(key), *(len(str(row[key])) for row in rows))
        for key in headers
    }
    print("READ-ONLY AUDIT — no database values were changed.")
    print(" | ".join(key.ljust(widths[key]) for key in headers))
    print("-+-".join("-" * widths[key] for key in headers))
    for row in rows:
        print(" | ".join(str(row[key] if row[key] is not None else "<NULL>").ljust(widths[key]) for key in headers))
    if any(row["status"] == "REVIEW REQUIRED" for row in rows):
        print("\nManual review is required before correcting unrecognized values.")
    elif any(row["status"] == "NORMALIZE" for row in rows):
        print("\nKnown variants can be mapped to canonical values after reviewing this report.")
    else:
        print("\nAll stored values are already canonical.")


if __name__ == "__main__":
    main()
