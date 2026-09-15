import sys
import os

# Agregamos la raíz al PYTHONPATH para importar correctamente 'app'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import init_db

if __name__ == "__main__":
    print("Inicializando base de datos...")
    init_db()
    print("Base de datos y tablas creadas exitosamente.")