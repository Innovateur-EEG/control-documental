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

    changed = False
    with engine.begin() as connection:
        if inspector.has_table("usuarios"):
            user_columns = {column["name"] for column in inspect(engine).get_columns("usuarios")}
            if "nombre" not in user_columns:
                connection.execute(text("ALTER TABLE usuarios ADD COLUMN nombre VARCHAR"))
                changed = True

        for table_name in ("configuracion_campos", "configuracion_evidencias"):
            if not inspect(connection).has_table(table_name):
                if table_name == "configuracion_campos":
                    raise RuntimeError(
                        "Table 'configuracion_campos' does not exist. "
                        "Run 'mise run db-init' first, or use 'mise run db-setup'."
                    )
                continue

            columns = {
                column["name"]
                for column in inspect(connection).get_columns(table_name)
            }

            if engine.dialect.name == "postgresql":
                # Always let PostgreSQL check the exact relation resolved by the
                # unqualified ORM query. This also repairs cases where a cached or
                # schema-scoped inspector reports a different table definition.
                connection.execute(
                    text(
                        f"ALTER TABLE {table_name} "
                        "ADD COLUMN IF NOT EXISTS configuracion_json "
                        "JSONB NOT NULL DEFAULT '{}'::jsonb"
                    )
                )
            elif "configuracion_json" not in columns:
                connection.execute(
                    text(
                        f"ALTER TABLE {table_name} "
                        "ADD COLUMN configuracion_json JSON NOT NULL DEFAULT '{}'"
                    )
                )

            # Verify the column on the relation that an unqualified query resolves.
            connection.execute(text(f"SELECT configuracion_json FROM {table_name} LIMIT 0"))
            if "configuracion_json" not in columns:
                changed = True

    return changed


def main() -> None:
    if migrate_schema(get_engine()):
        print("Migration complete: schema updated.")
    else:
        print("Database schema is already up to date.")


if __name__ == "__main__":
    main()
