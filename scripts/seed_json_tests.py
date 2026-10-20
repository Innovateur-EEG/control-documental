"""Seed reproducible JSON-driven field and evidence configurations for manual testing.

Run with: mise run db-seed-json-tests
Only records prefixed with "TEST JSON —" are managed by this seeder.
It never deletes records and is safe to run repeatedly.
"""
from __future__ import annotations

import os
import sys
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session

from app.models.database import ConfiguracionCampos, ConfiguracionEvidencia, SessionLocal


FIELD_DEFINITIONS: list[dict[str, Any]] = [
    {
        "nombre_mostrar": "TEST JSON — Texto simple",
        "llave_jinja": "test_json_plain_text",
        "tipo_input": "Texto",
        "opciones_json": [],
        "tipo_persona": "Ambas",
        "configuracion_json": {"section": "Pruebas JSON", "order": 10, "help": "Campo de texto básico.", "required": False},
    },
    {
        "nombre_mostrar": "TEST JSON — Texto con placeholder y límite",
        "llave_jinja": "test_json_text_constraints",
        "tipo_input": "Texto",
        "opciones_json": [],
        "tipo_persona": "Ambas",
        "configuracion_json": {"section": "Pruebas JSON", "order": 20, "placeholder": "Escribe hasta 40 caracteres", "max_chars": 40, "required": False},
    },
    {
        "nombre_mostrar": "TEST JSON — Número con límites",
        "llave_jinja": "test_json_number_bounds",
        "tipo_input": "Número",
        "opciones_json": [],
        "tipo_persona": "Ambas",
        "configuracion_json": {"section": "Pruebas JSON", "order": 30, "min_value": 0, "max_value": 100, "step": 5, "required": False},
    },
    {
        "nombre_mostrar": "TEST JSON — Valor predeterminado",
        "llave_jinja": "test_json_default_value",
        "tipo_input": "Texto",
        "opciones_json": [],
        "tipo_persona": "Ambas",
        "configuracion_json": {"section": "Pruebas JSON", "order": 40, "default": "Valor inicial", "required": False},
    },
    {
        "nombre_mostrar": "TEST JSON — Campo obligatorio",
        "llave_jinja": "test_json_required",
        "tipo_input": "Texto",
        "opciones_json": [],
        "tipo_persona": "Ambas",
        "configuracion_json": {"section": "Pruebas JSON", "order": 50, "required": True},
    },
    {
        "nombre_mostrar": "TEST JSON — Casilla desactivada",
        "llave_jinja": "test_json_checkbox",
        "tipo_input": "Casilla",
        "opciones_json": [],
        "tipo_persona": "Ambas",
        "configuracion_json": {"section": "Pruebas JSON", "order": 60, "default": False, "required": False},
    },
    {
        "nombre_mostrar": "TEST JSON — Control estado civil",
        "llave_jinja": "test_json_estado_civil",
        "tipo_input": "Opciones",
        "opciones_json": ["Soltero/a", "Casado/a", "Divorciado/a", "Viudo/a", "Unión libre"],
        "tipo_persona": "Fisica",
        "configuracion_json": {"section": "Pruebas JSON", "order": 70, "required": False},
    },
    {
        "nombre_mostrar": "TEST JSON — Visible si casado",
        "llave_jinja": "test_json_conditional_value",
        "tipo_input": "Texto",
        "opciones_json": [],
        "tipo_persona": "Fisica",
        "configuracion_json": {"section": "Pruebas JSON", "order": 80, "visible_if": {"field": "test_json_estado_civil", "equals": "Casado/a"}, "required": False},
    },
    {
        "nombre_mostrar": "TEST JSON — Visible si soltero",
        "llave_jinja": "test_json_conditional_single",
        "tipo_input": "Texto",
        "opciones_json": [],
        "tipo_persona": "Fisica",
        "configuracion_json": {"section": "Pruebas JSON", "order": 90, "visible_if": {"field": "test_json_estado_civil", "equals": "Soltero/a"}, "required": False},
    },
    {
        "nombre_mostrar": "TEST JSON — Control tipo de persona",
        "llave_jinja": "test_json_tipo_persona",
        "tipo_input": "Opciones",
        "opciones_json": ["Moral", "Fisica", "Otro"],
        "tipo_persona": "Ambas",
        "configuracion_json": {"section": "Pruebas JSON", "order": 100, "required": False},
    },
    {
        "nombre_mostrar": "TEST JSON — Opciones dependientes",
        "llave_jinja": "test_json_dependent_options",
        "tipo_input": "Selección única",
        "opciones_json": [],
        "tipo_persona": "Ambas",
        "configuracion_json": {
            "section": "Pruebas JSON", "order": 110,
            "options_map": {"depends_on": "test_json_tipo_persona", "map": {"Moral": ["RFC", "Acta constitutiva"], "Fisica": ["CURP", "Identificación"], "Otro": ["Otro documento"]}},
            "required": False,
        },
    },
    {
        "nombre_mostrar": "TEST JSON — Selección múltiple",
        "llave_jinja": "test_json_multiple_selection",
        "tipo_input": "Selección múltiple",
        "opciones_json": ["KYC", "FATCA", "Fideicomisos", "Visita ocular"],
        "tipo_persona": "Ambas",
        "configuracion_json": {"section": "Pruebas JSON", "order": 120, "required": False},
    },
    {
        "nombre_mostrar": "TEST JSON — Fecha",
        "llave_jinja": "test_json_date",
        "tipo_input": "Fecha",
        "opciones_json": [],
        "tipo_persona": "Ambas",
        "configuracion_json": {"section": "Pruebas JSON", "order": 130, "required": False},
    },
    {
        "nombre_mostrar": "TEST JSON — Configuración vacía",
        "llave_jinja": "test_json_empty_config",
        "tipo_input": "Texto",
        "opciones_json": [],
        "tipo_persona": "Ambas",
        "configuracion_json": {},
    },
    {
        "nombre_mostrar": "TEST JSON — Configuración combinada",
        "llave_jinja": "test_json_combined",
        "tipo_input": "Texto",
        "opciones_json": [],
        "tipo_persona": "Ambas",
        "configuracion_json": {"section": "Pruebas JSON", "order": 140, "placeholder": "Dato de prueba", "max_chars": 80, "default": "Ejemplo", "required": True},
    },
]

EVIDENCE_DEFINITIONS: list[dict[str, Any]] = [
    {"nombre_evidencia": "TEST JSON — Vigencia 30 días", "tipo_persona": "Ambas", "roles_aplica": [], "configuracion_json": {"vigencia": 30}},
    {"nombre_evidencia": "TEST JSON — Vigencia cero", "tipo_persona": "Ambas", "roles_aplica": [], "configuracion_json": {"vigencia": 0}},
    {"nombre_evidencia": "TEST JSON — Vigencia indefinida", "tipo_persona": "Ambas", "roles_aplica": [], "configuracion_json": {"vigencia": "Indefinida"}},
    {"nombre_evidencia": "TEST JSON — Sin vigencia", "tipo_persona": "Ambas", "roles_aplica": [], "configuracion_json": {}},
    {"nombre_evidencia": "TEST JSON — Vigencia nula", "tipo_persona": "Ambas", "roles_aplica": [], "configuracion_json": {"vigencia": None}},
    {"nombre_evidencia": "TEST JSON — Vigencia decimal", "tipo_persona": "Ambas", "roles_aplica": [], "configuracion_json": {"vigencia": 2.5}},
    {"nombre_evidencia": "TEST JSON — Vigencia booleana", "tipo_persona": "Ambas", "roles_aplica": [], "configuracion_json": {"vigencia": True}},
]


def _upsert(session: Session, model: type, lookup: dict[str, Any], values: dict[str, Any]) -> bool:
    record = session.query(model).filter_by(**lookup).first()
    if record is None:
        session.add(model(**values))
        return True
    for key, value in values.items():
        if key not in lookup:
            setattr(record, key, value)
    return False


def seed_json_tests(session: Session) -> dict[str, int]:
    """Create or refresh only the seeder-owned test records; return counts."""
    fields_added = fields_updated = 0
    for definition in FIELD_DEFINITIONS:
        values = {
            **definition,
            "roles_aplica": [],
            "regla_validacion": None,
        }
        created = _upsert(
            session,
            ConfiguracionCampos,
            {"llave_jinja": definition["llave_jinja"], "tipo_persona": definition["tipo_persona"]},
            values,
        )
        if created:
            fields_added += 1
        else:
            fields_updated += 1

    evidence_added = evidence_updated = 0
    for definition in EVIDENCE_DEFINITIONS:
        created = _upsert(
            session,
            ConfiguracionEvidencia,
            {"nombre_evidencia": definition["nombre_evidencia"], "tipo_persona": definition["tipo_persona"]},
            definition,
        )
        if created:
            evidence_added += 1
        else:
            evidence_updated += 1

    session.commit()
    return {
        "fields_added": fields_added,
        "fields_updated": fields_updated,
        "evidence_added": evidence_added,
        "evidence_updated": evidence_updated,
    }


def main() -> None:
    session = SessionLocal()
    try:
        result = seed_json_tests(session)
        print(
            "JSON test configuration ready: "
            f"{result['fields_added']} field(s) added, "
            f"{result['fields_updated']} refreshed, "
            f"{result['evidence_added']} evidence type(s) added, "
            f"{result['evidence_updated']} refreshed."
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
