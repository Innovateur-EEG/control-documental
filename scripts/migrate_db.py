"""Apply additive database schema updates for existing deployments.

Run with: mise run db-migrate
The migration is idempotent and does not delete or recreate data.
"""
import os
import sys

from sqlalchemy import inspect, text

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.models.database import get_engine


def migrate_schema(engine) -> bool:
    """Add JSON configuration columns when missing. Return True only when changed."""
    inspector = inspect(engine)

    if not inspector.has_table("configuracion_campos"):
        raise RuntimeError(
            "Table 'configuracion_campos' does not exist. "
            "Run 'mise run db-init' first, or use 'mise run db-setup'."
        )

    json_type = "JSONB" if engine.dialect.name == "postgresql" else "JSON"
    changed = False
    with engine.begin() as connection:
        for table_name in ("configuracion_campos", "configuracion_evidencias"):
            if not inspector.has_table(table_name):
                if table_name == "configuracion_campos":
                    raise RuntimeError(
                        "Table 'configuracion_campos' does not exist. "
                        "Run 'mise run db-init' first, or use 'mise run db-setup'."
                    )
                continue
            columns = {column["name"] for column in inspect(engine).get_columns(table_name)}
            if "configuracion_json" not in columns:
                connection.execute(
                    text(
                        f"ALTER TABLE {table_name} "
                        f"ADD COLUMN configuracion_json {json_type} "
                        "NOT NULL DEFAULT '{}' "
                    )
                )
                changed = True
    return changed


def main() -> None:
    if migrate_schema(get_engine()):
        print("Migration complete: configuracion_campos.configuracion_json added.")
    else:
        print("Database schema is already up to date.")


if __name__ == "__main__":
    main()
