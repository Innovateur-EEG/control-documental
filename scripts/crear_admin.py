import sys
import os
import getpass

# Ajustar PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import SessionLocal, Usuario
from app.utils.auth import generar_hash

def crear_superadmin():
    db = SessionLocal()
    try:
        print("--- Creación de Primer SuperAdmin ---")
        email = input("Ingresa el correo corporativo (SuperAdmin): ")
        
        existente = db.query(Usuario).filter(Usuario.email == email).first()
        if existente:
            print("El usuario ya existe.")
            return

        pwd_temporal = getpass.getpass("Ingresa una contraseña temporal (OTP): ")
        
        nuevo_admin = Usuario(
            email=email,
            password_hash=generar_hash(pwd_temporal),
            tipo_usuario="SuperAdmin",
            debe_cambiar_password=1  # Forzamos el cambio en el primer inicio de sesión
        )
        
        db.add(nuevo_admin)
        db.commit()
        print(f"SuperAdmin {email} creado exitosamente. ¡Listo para el primer login!")
        
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    crear_superadmin()