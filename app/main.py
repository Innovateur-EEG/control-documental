import sys
import os
import streamlit as st
import pandas as pd

# Agregamos la raiz al PYTHONPATH para que las importaciones de 'app' funcionen al lanzar Streamlit
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import SessionLocal, UsuarioAcceso, Participante

# Configuracion global de la pagina
st.set_page_config(page_title="Control Documental", page_icon="", layout="centered")

def get_db_session():
    """Generador para manejar la sesion de base de datos"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass # Streamlit recarga el script completo; cerraremos explícitamente cuando sea necesario

def login():
    st.title("Portal de Control Documental")
    st.write("Ingrese su correo electronico corporativo para acceder (Ej. representante@empresa.com).")
    
    email = st.text_input("Correo electronico", placeholder="usuario@correo.com")
    
    if st.button("Ingresar"):
        if email:
            db = get_db_session()
            usuario = db.query(UsuarioAcceso).filter(UsuarioAcceso.email == email).first()
            
            if usuario:
                # Guardar datos en la sesión de Streamlit
                st.session_state['autenticado'] = True
                st.session_state['usuario_id'] = usuario.id
                st.session_state['nivel_acceso'] = usuario.nivel_acceso
                st.session_state['participante_id'] = usuario.participante_id
                
                db.close()
                st.rerun() # Fuerza a Streamlit a recargar la página para entrar al Dashboard
            else:
                db.close()
                st.error("Credenciales invalidas o correo no registrado.")
        else:
            st.warning("Por favor ingrese un correo valido.")

def logout():
    st.session_state.clear()
    st.rerun()

def dashboard():
    db = get_db_session()
    
    # 1. Recuperar datos del usuario autenticado
    participante_actual = db.query(Participante).filter(Participante.id == st.session_state['participante_id']).first()
    
    # 2. Logica Jerarquica: Determinar la "Empresa Padre"
    if participante_actual.id_padre:
        # Es un representante o apoderado
        empresa = db.query(Participante).filter(Participante.id == participante_actual.id_padre).first()
    else:
        # Es la empresa raiz logueada directamente
        empresa = participante_actual
        
    # 3. Obtener todos los vinculados a la empresa
    vinculados = db.query(Participante).filter(
        (Participante.id_padre == empresa.id) | (Participante.id == empresa.id)
    ).all()
    
    # --- UI: Barra lateral ---
    st.sidebar.title("Perfil Activo")
    st.sidebar.subheader(f"{participante_actual.razon_social_o_nombre}")
    st.sidebar.write(f"**Rol:** {participante_actual.rol_jerarquico}")
    st.sidebar.button("Cerrar Sesion", on_click=logout)
    
    # --- UI: Panel Principal ---
    st.title(f"Expediente: {empresa.razon_social_o_nombre}")
    st.write(f"**RFC de la Empresa:** {empresa.rfc}")
    st.divider()
    
    st.subheader("Entidades Relacionadas")
    st.write("Seleccione el participante para gestionar sus formatos.")
    
    # Transformar datos a un DataFrame de Pandas para visualizacion limpia
    datos_tabla = []
    for p in vinculados:
        datos_tabla.append({
            "ID": p.id,
            "Nombre / Razon Social": p.razon_social_o_nombre,
            "RFC": p.rfc,
            "Tipo": p.tipo_persona,
            "Rol Jerarquico": p.rol_jerarquico
        })
        
    df = pd.DataFrame(datos_tabla)
    
    # Mostrar tabla sin índice y ocupando el ancho
    st.dataframe(df, hide_index=True, use_container_width=True)
    
    # --- FIX: Mapeo seguro directo de la base de datos ---
    mapa_nombres = {p.id: p.razon_social_o_nombre for p in vinculados}
    
    participante_seleccionado = st.selectbox(
        "Participante a documentar:", 
        options=list(mapa_nombres.keys()), 
        format_func=lambda x: mapa_nombres[x]
    )
    
    # --- UI: Formulario Dinámico ---
    participante_obj = next((p for p in vinculados if p.id == participante_seleccionado), None)
    
    if participante_obj:
        st.divider()
        st.subheader(f"Datos Complementarios - {participante_obj.razon_social_o_nombre}")
        
        with st.form("formulario_captura"):
            st.info(f"Completando información para Persona {participante_obj.tipo_persona}")
            
            # Campos comunes
            col1, col2 = st.columns(2)
            with col1:
                direccion = st.text_input("Dirección Completa")
            with col2:
                telefono = st.text_input("Teléfono de Contacto")
                
            # Campos dinámicos por tipo de persona
            if participante_obj.tipo_persona == "Moral":
                fecha_const = st.date_input("Fecha de Constitución")
                notario = st.text_input("Nombre del Notario")
                datos_dinamicos = {"fecha_const": str(fecha_const), "notario": notario}
            else:
                curp = st.text_input("CURP")
                estado_civil = st.selectbox("Estado Civil", ["Soltero", "Casado", "Otro"])
                datos_dinamicos = {"curp": curp, "estado_civil": estado_civil}
                
            submit_btn = st.form_submit_button("Validar y Guardar Datos")
            
            if submit_btn:
                # Guardamos los datos en sesión para usarlos en la generación del documento (WBS 1.3)
                st.session_state['datos_formulario'] = {
                    "nombre": participante_obj.razon_social_o_nombre,
                    "rfc": participante_obj.rfc,
                    "direccion": direccion,
                    "telefono": telefono,
                    **datos_dinamicos
                }
                st.success("Datos validados correctamente. Listo para generar formato.")

    db.close()
    

def main():
    # Inicializar variable de estado si no existe
    if 'autenticado' not in st.session_state:
        st.session_state['autenticado'] = False

    # Control de flujo de la interfaz
    if not st.session_state['autenticado']:
        login()
    else:
        dashboard()

if __name__ == "__main__":
    main()