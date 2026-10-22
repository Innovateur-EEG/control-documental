"""Database seed and baseline schema regression tests."""
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.database import Base, ConfiguracionCampos
from scripts.seed_db import BASE_FIELDS, seed_database


def make_test_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)()


def test_seed_populates_required_base_fields_and_is_idempotent():
    engine, session = make_test_session()
    try:
        inserted = seed_database(session)
        assert inserted == len(BASE_FIELDS)
        assert session.query(ConfiguracionCampos).count() == len(BASE_FIELDS)

        inserted_again = seed_database(session)
        assert inserted_again == 0
        assert session.query(ConfiguracionCampos).count() == len(BASE_FIELDS)
    finally:
        session.close()
        engine.dispose()


def test_seed_preserves_existing_administrator_configuration():
    engine, session = make_test_session()
    try:
        custom = ConfiguracionCampos(
            nombre_mostrar="Custom company name",
            llave_jinja="nombre",
            tipo_input="Texto",
            opciones_json=[],
            tipo_persona="Ambas",
            roles_aplica=["Admin"],
            regla_validacion=None,
            configuracion_json={
                "section": "Custom section",
                "order": 77,
                "help": "Keep this setting",
                "required": False,
            },
        )
        session.add(custom)
        session.commit()

        seed_database(session)

        stored = (
            session.query(ConfiguracionCampos)
            .filter_by(llave_jinja="nombre", tipo_persona="Ambas")
            .one()
        )
        assert stored.nombre_mostrar == "Custom company name"
        assert stored.roles_aplica == ["Admin"]
        assert stored.configuracion_json["section"] == "Custom section"
        assert stored.configuracion_json["order"] == 77
    finally:
        session.close()
        engine.dispose()


def test_baseline_schema_contains_dynamic_field_configuration_column():
    engine, session = make_test_session()
    try:
        columns = {column["name"] for column in inspect(engine).get_columns("configuracion_campos")}
        assert "configuracion_json" in columns
    finally:
        session.close()
        engine.dispose()


def test_migration_adds_missing_column_and_is_idempotent():
    from sqlalchemy import inspect, text
    from scripts.migrate_db import migrate_schema

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE configuracion_campos "
                    "(id INTEGER PRIMARY KEY, nombre_mostrar VARCHAR NOT NULL)"
                )
            )

        assert migrate_schema(engine) is True
        columns = {column["name"] for column in inspect(engine).get_columns("configuracion_campos")}
        assert "configuracion_json" in columns

        assert migrate_schema(engine) is False
    finally:
        engine.dispose()
