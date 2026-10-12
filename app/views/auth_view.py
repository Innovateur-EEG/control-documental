import streamlit as st
from app.models.database import SessionLocal, Usuario
from app.utils.auth import verificar_password, generar_hash

def logout():
    st.session_state.clear()
    # Sin st.rerun() para evitar el warning 'no-op'


def render_login():
    db = SessionLocal()
    try:
        st.title("Portal de Control Documental")
        
        if 'usuario_temporal_id' in st.session_state:
            st.warning("🔒 Por seguridad, debe cambiar su contraseña temporal antes de continuar.")
            with st.form("form_cambio_password"):
                nueva_pwd = st.text_input("Nueva contraseña", type="password")
                confirmar_pwd = st.text_input("Confirmar contraseña", type="password")
                submit_btn = st.form_submit_button("Actualizar y Entrar")
                
                if submit_btn:
                    if len(nueva_pwd) < 6:
                        st.error("La contraseña debe tener al menos 6 caracteres.")
                    elif nueva_pwd != confirmar_pwd:
                        st.error("Las contraseñas no coinciden.")
                    else:
                        usr = db.query(Usuario).filter(Usuario.id == st.session_state['usuario_temporal_id']).first()
                        usr.password_hash = generar_hash(nueva_pwd)
                        usr.debe_cambiar_password = 0
                        db.commit()
                        
                        st.session_state['autenticado'] = True
                        st.session_state['usuario_id'] = usr.id
                        st.session_state['tipo_usuario'] = usr.tipo_usuario
                        st.session_state['email'] = usr.email
                        del st.session_state['usuario_temporal_id']
                        st.success("Contraseña actualizada exitosamente.")
                        st.rerun()
        else:
            st.write("Ingrese sus credenciales de acceso.")
            with st.form("login_form"):
                email = st.text_input("Correo electrónico", placeholder="usuario@correo.com")
                password = st.text_input("Contraseña", type="password")
                submit_btn = st.form_submit_button("Ingresar")
                
                if submit_btn:
                    if email and password:
                        email_limpio = email.strip().lower()
                        usr = db.query(Usuario).filter(Usuario.email == email_limpio).first()
                        if usr and verificar_password(password, usr.password_hash):
                            if usr.debe_cambiar_password == 1:
                                st.session_state['usuario_temporal_id'] = usr.id
                            else:
                                st.session_state['autenticado'] = True
                                st.session_state['usuario_id'] = usr.id
                                st.session_state['tipo_usuario'] = usr.tipo_usuario
                                st.session_state['email'] = usr.email
                            st.rerun()
                        else:
                            st.error("Credenciales inválidas.")
                    else:
                        st.warning("Ingrese correo y contraseña.")
    finally:
        db.close()