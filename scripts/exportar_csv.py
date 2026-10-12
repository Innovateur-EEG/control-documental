import sys
import os
import pandas as pd
from sqlalchemy import inspect

# Agregamos la raíz al PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import engine

def exportar_todas_las_tablas():
    print("Conectando a Supabase...")
    
    # Crear carpeta de exportación si no existe
    os.makedirs("app/outputs/exportacion_masiva", exist_ok=True)
    
    # Inspeccionar la base de datos para sacar los nombres de las tablas
    inspector = inspect(engine)
    tablas = inspector.get_table_names()
    
    if not tablas:
        print("No se encontraron tablas.")
        return

    print(f"Se encontraron {len(tablas)} tablas. Iniciando exportación...")
    
    # Iterar, descargar y guardar como CSV
    with engine.connect() as conexion:
        for tabla in tablas:
            print(f"Exportando: {tabla}.csv ...", end="")
            df = pd.read_sql_table(tabla, conexion)
            ruta_csv = f"app/outputs/exportacion_masiva/{tabla}.csv"
            # utf-8-sig para que Excel lea los acentos sin problema
            df.to_csv(ruta_csv, index=False, encoding='utf-8-sig')
            print(" ¡Listo!")
            
    print("\n✅ Exportación masiva completada en 'app/outputs/exportacion_masiva/'")

if __name__ == "__main__":
    exportar_todas_las_tablas()