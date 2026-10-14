"""Apply additive database schema updates for existing deployments.

Run with: mise run db-migrate
This script is intentionally idempotent and does not delete or recreate data.
"""
import sys
import os
from sqlalchemy import inspect, text

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.models.database import get_engine


def main():
    engine = get_engine()
    inspector = inspect(engine)

    if not inspector.has_table("configuracion_campos"):
        raise RuntimeError(
            "Table 'configuracion_campos' does not exist. "
            "Run 'mise run db-init' first, then retry this migration."
        )

    columns = {column["name"] for column in inspector.get_columns("configuracion_campos")}
    if "configuracion_json" in columns:
        print("Database schema is already up to date.")
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE configuracion_campos "
                "ADD COLUMN IF NOT EXISTS configuracion_json "
                "JSONB NOT NULL DEFAULT '{}'::jsonb"
            )
        )

    print("Migration complete: configuracion_campos.configuracion_json added.")


if __name__ == "__main__":
    main()
