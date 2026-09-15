import sys
import os

# Agregamos la raíz al PYTHONPATH para importar correctamente 'app'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import SessionLocal, Proyecto, Participante, UsuarioAcceso

def seed():
    db = SessionLocal()
    try:
        # Verificar si ya existe información para ser idempotente
        if db.query(Proyecto).first():
            print("La base de datos ya contiene datos. Saltando el sembrado.")
            return

        print("Creando datos de prueba (Seed)...")

        # 1. Crear Proyecto
        proyecto = Proyecto(nombre_proyecto="Proyecto PoC Control Documental")
        db.add(proyecto)
        db.commit()
        db.refresh(proyecto)

        # 2. Crear Persona Moral (Empresa - Nivel Padre)
        empresa = Participante(
            proyecto_id=proyecto.id,
            tipo_persona="Moral",
            razon_social_o_nombre="Innovateur Corp S.A. de C.V.",
            rfc="INN260915ABC",
            rol_jerarquico="Empresa"
        )
        db.add(empresa)
        db.commit()
        db.refresh(empresa)

        # 3. Crear Persona Física (Representante - Nivel Hijo)
        representante = Participante(
            proyecto_id=proyecto.id,
            tipo_persona="Fisica",
            razon_social_o_nombre="Juan Pérez",
            rfc="PEPJ800101XYZ",
            id_padre=empresa.id,  # Autoreferencia: Juan pertenece a Innovateur Corp
            rol_jerarquico="Representante"
        )
        db.add(representante)
        db.commit()
        db.refresh(representante)

        # 4. Crear Credenciales de Acceso para el Representante
        usuario = UsuarioAcceso(
            participante_id=representante.id,
            email="representante@empresa.com",
            nivel_acceso="Representante"
        )
        db.add(usuario)
        db.commit()

        print("Datos de prueba insertados exitosamente.")
        print(f"- Empresa (Padre): {empresa.razon_social_o_nombre}")
        print(f"- Representante (Hijo): {representante.razon_social_o_nombre}")
        print(f"- Usuario para login: {usuario.email}")

    except Exception as e:
        print(f"Error insertando datos: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed()