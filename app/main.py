import sys
import os
import streamlit as st
st.set_page_config(page_title="Control Documental", page_icon="📄", layout="centered")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import get_db_session, Usuario, Proyecto
from app.views.auth_view import render_login, logout
from app.views.gestor_view import render_gestor
from app.views.admin_view import render_admin



def dashboard_principal():
    db = get_db_session()
    try:
        user_actual = db.query(Usuario).filter(Usuario.id == st.session_state['usuario_id']).first()
        tipo_usr = st.session_state['tipo_usuario']
        is_super = tipo_usr == "SuperAdmin"
        is_admin = tipo_usr in ["Admin", "SuperAdmin"]
        
        # --- CABECERA ---
        col_usr_info, col_btn_out = st.columns([4, 1])
        col_usr_info.caption(f"👤 **{st.session_state['email']}**  \n`Rol: {tipo_usr}`")
        with col_btn_out:
            st.button("Salir", on_click=logout, key="btn_logout_top", use_container_width=False)
                
        st.divider()

        # Datos globales base
        mis_proyectos = db.query(Proyecto).all() if is_super else (list(user_actual.proyectos_admin) if user_actual else [])
        mis_proy_ids = [p.id for p in mis_proyectos]

        # --- ENRUTADOR DE PESTAÑAS ---
        if is_admin or is_super:
            tab_expedientes, tab_tablero, tab_config = st.tabs(["📋 Mis Expedientes", "📊 Tablero", "⚙️ Configuración"])
            render_admin(db, user_actual, is_super, tab_tablero, tab_config, mis_proyectos, mis_proy_ids)
        else: 
            tab_expedientes = st.container()
            st.markdown("### 📋 Mis Expedientes")

        # El gestor se renderiza para todos
        render_gestor(db, user_actual, tab_expedientes)

    except Exception as e:
        st.error(f"🚨 Error crítico en el sistema: {e}")
        st.exception(e)
    finally:
        db.close()

def main():
    st.title("Sistema de Control Documental")
    if 'autenticado' not in st.session_state:
        st.session_state['autenticado'] = False

    if not st.session_state['autenticado']:
        render_login()
    else:
        dashboard_principal()

if __name__ == "__main__":
    main()