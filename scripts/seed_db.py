"""Populate the minimum dynamic-field configuration required by the base template.

Safe to run repeatedly. Does not create sample users, companies, or business records.
Run with: mise run db-seed
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.models.database import ConfiguracionCampos, SessionLocal


BASE_FIELDS = [
    {
        "nombre_mostrar": "Nombre / Razón Social",
        "llave_jinja": "nombre",
        "tipo_input": "Texto",
        "opciones_json": [],
        "tipo_persona": "Ambas",
        "roles_aplica": [],
        "regla_validacion": None,
        "configuracion_json": {"section": "Datos generales", "order": 10, "help": "", "required": True, "default": None, "visible_if": None, "options_map": None},
    },
    {
        "nombre_mostrar": "RFC",
        "llave_jinja": "rfc",
        "tipo_input": "Texto",
        "opciones_json": [],
        "tipo_persona": "Ambas",
        "roles_aplica": [],
        "regla_validacion": None,
        "configuracion_json": {"section": "Datos generales", "order": 20, "help": "", "required": False, "default": None, "visible_if": None, "options_map": None},
    },
    {
        "nombre_mostrar": "Dirección Registrada",
        "llave_jinja": "direccion",
        "tipo_input": "Texto",
        "opciones_json": [],
        "tipo_persona": "Ambas",
        "roles_aplica": [],
        "regla_validacion": None,
        "configuracion_json": {"section": "Datos generales", "order": 30, "help": "", "required": False, "default": None, "visible_if": None, "options_map": None},
    },
    {
        "nombre_mostrar": "Teléfono de Contacto",
        "llave_jinja": "telefono",
        "tipo_input": "Texto",
        "opciones_json": [],
        "tipo_persona": "Ambas",
        "roles_aplica": [],
        "regla_validacion": None,
        "configuracion_json": {"section": "Datos generales", "order": 40, "help": "", "required": False, "default": None, "visible_if": None, "options_map": None},
    },
    {
        "nombre_mostrar": "Fecha de Constitución",
        "llave_jinja": "fecha_const",
        "tipo_input": "Fecha",
        "opciones_json": [],
        "tipo_persona": "Moral",
        "roles_aplica": [],
        "regla_validacion": None,
        "configuracion_json": {"section": "Datos específicos", "order": 10, "help": "", "required": False, "default": None, "visible_if": None, "options_map": None},
    },
    {
        "nombre_mostrar": "Notario Público",
        "llave_jinja": "notario",
        "tipo_input": "Texto",
        "opciones_json": [],
        "tipo_persona": "Moral",
        "roles_aplica": [],
        "regla_validacion": None,
        "configuracion_json": {"section": "Datos específicos", "order": 20, "help": "", "required": False, "default": None, "visible_if": None, "options_map": None},
    },
    {
        "nombre_mostrar": "CURP",
        "llave_jinja": "curp",
        "tipo_input": "Texto",
        "opciones_json": [],
        "tipo_persona": "Fisica",
        "roles_aplica": [],
        "regla_validacion": None,
        "configuracion_json": {"section": "Datos específicos", "order": 10, "help": "", "required": False, "default": None, "visible_if": None, "options_map": None},
    },
    {
        "nombre_mostrar": "Estado Civil",
        "llave_jinja": "estado_civil",
        "tipo_input": "Opciones",
        "opciones_json": ["Soltero/a", "Casado/a", "Divorciado/a", "Viudo/a", "Unión libre"],
        "tipo_persona": "Fisica",
        "roles_aplica": [],
        "regla_validacion": None,
        "configuracion_json": {"section": "Datos específicos", "order": 20, "help": "", "required": False, "default": None, "visible_if": None, "options_map": None},
    },
]


def seed_database(session: Session) -> int:
    """Insert missing baseline fields; preserve existing administrator configuration."""
    inserted = 0
    for values in BASE_FIELDS:
        existing = (
            session.query(ConfiguracionCampos)
            .filter(
                ConfiguracionCampos.llave_jinja == values["llave_jinja"],
                ConfiguracionCampos.tipo_persona == values["tipo_persona"],
            )
            .first()
        )
        if existing is None:
            session.add(ConfiguracionCampos(**values))
            inserted += 1
    session.commit()
    return inserted


def main() -> None:
    session = SessionLocal()
    try:
        inserted = seed_database(session)
        print(f"Database seed complete. Added {inserted} baseline field(s); existing configuration was preserved.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
