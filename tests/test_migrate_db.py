"""Tests for additive schema migrations needed by JSON configuration."""
from sqlalchemy import create_engine, inspect, text

from scripts.migrate_db import migrate_schema


def test_migrate_schema_adds_missing_json_configuration_columns():
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(text(
                "CREATE TABLE configuracion_campos "
                "(id INTEGER PRIMARY KEY, nombre_mostrar VARCHAR)"
            ))
            connection.execute(text(
                "CREATE TABLE configuracion_evidencias "
                "(id INTEGER PRIMARY KEY, nombre_evidencia VARCHAR, "
                "tipo_persona VARCHAR, roles_aplica JSON)"
            ))

        assert migrate_schema(engine) is True

        for table_name in ("configuracion_campos", "configuracion_evidencias"):
            columns = {column["name"] for column in inspect(engine).get_columns(table_name)}
            assert "configuracion_json" in columns

        assert migrate_schema(engine) is False
    finally:
        engine.dispose()
