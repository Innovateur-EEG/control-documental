"""Tests for the repeatable JSON test-data seeder."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.database import Base, ConfiguracionCampos, ConfiguracionEvidencia
from scripts.seed_json_tests import (
    EVIDENCE_DEFINITIONS,
    FIELD_DEFINITIONS,
    seed_json_tests,
)


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)()


def test_seed_creates_expected_fields_and_evidence_records():
    engine, session = make_session()
    try:
        result = seed_json_tests(session)
        assert result == {
            "fields_added": len(FIELD_DEFINITIONS),
            "fields_updated": 0,
            "evidence_added": len(EVIDENCE_DEFINITIONS),
            "evidence_updated": 0,
        }
        assert session.query(ConfiguracionCampos).filter(
            ConfiguracionCampos.nombre_mostrar.like("TEST JSON — %")
        ).count() == len(FIELD_DEFINITIONS)
        assert session.query(ConfiguracionEvidencia).filter(
            ConfiguracionEvidencia.nombre_evidencia.like("TEST JSON — %")
        ).count() == len(EVIDENCE_DEFINITIONS)
    finally:
        session.close()
        engine.dispose()


def test_seed_is_idempotent_and_refreshes_only_test_records():
    engine, session = make_session()
    try:
        first = seed_json_tests(session)
        assert first["fields_added"] == len(FIELD_DEFINITIONS)
        assert first["evidence_added"] == len(EVIDENCE_DEFINITIONS)

        second = seed_json_tests(session)
        assert second == {
            "fields_added": 0,
            "fields_updated": len(FIELD_DEFINITIONS),
            "evidence_added": 0,
            "evidence_updated": len(EVIDENCE_DEFINITIONS),
        }
        assert session.query(ConfiguracionCampos).count() == len(FIELD_DEFINITIONS)
        assert session.query(ConfiguracionEvidencia).count() == len(EVIDENCE_DEFINITIONS)
    finally:
        session.close()
        engine.dispose()


def test_seed_does_not_overwrite_non_test_records():
    engine, session = make_session()
    try:
        custom = ConfiguracionCampos(
            nombre_mostrar="Nombre / Razón Social",
            llave_jinja="nombre",
            tipo_input="Texto",
            opciones_json=[],
            tipo_persona="Ambas",
            roles_aplica=[],
            regla_validacion=None,
            configuracion_json={"section": "Datos generales", "required": True},
        )
        session.add(custom)
        session.commit()

        seed_json_tests(session)

        stored = session.query(ConfiguracionCampos).filter_by(
            llave_jinja="nombre", tipo_persona="Ambas"
        ).one()
        assert stored.nombre_mostrar == "Nombre / Razón Social"
        assert stored.configuracion_json == {"section": "Datos generales", "required": True}
    finally:
        session.close()
        engine.dispose()
