import sys
import os
import io
import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate

# Agregamos la raíz al PYTHONPATH para que las importaciones funcionen correctamente
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import SessionLocal, UsuarioAcceso, Participante, ExpedienteDocumento

# Configuración global de la página
st.set_page_config(page_title="Control Documental", page_icon="📄", layout="centered")

def get_db_session():
    """Generador para manejar la sesión de base de datos"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass

def login():
    st.title("Portal de Control Documental")
    st.write("Ingrese su correo electrónico corporativo para acceder (Ej. representante@empresa.com).")
    
    email = st.text_input("Correo electrónico", placeholder="usuario@correo.com")
    
    if st.button("Ingresar"):
        if email:
            db = get_db_session()
            usuario = db.query(UsuarioAcceso).filter(UsuarioAcceso.email == email).first()
            
            if usuario:
                st.session_state['autenticado'] = True
                st.session_state['usuario_id'] = usuario.id
                st.session_state['nivel_acceso'] = usuario.nivel_acceso
                st.session_state['participante_id'] = usuario.participante_id
                
                db.close()
                st.rerun()
            else:
                db.close()
                st.error("Credenciales inválidas o correo no registrado.")
        else:
            st.warning("Por favor ingrese un correo válido.")

def logout():
    st.session_state.clear()
    st.rerun()

def dashboard():
    db = get_db_session()
    
    # 1. Recuperar datos del usuario autenticado
    participante_actual = db.query(Participante).filter(Participante.id == st.session_state['participante_id']).first()
    
    # 2. Lógica Jerárquica: Determinar la "Empresa Padre"
    if participante_actual.id_padre:
        empresa = db.query(Participante).filter(Participante.id == participante_actual.id_padre).first()
    else:
        empresa = participante_actual
        
    # 3. Obtener todas las entidades vinculadas a la empresa
    vinculados = db.query(Participante).filter(
        (Participante.id_padre == empresa.id) | (Participante.id == empresa.id)
    ).all()
    
    # --- UI: Barra lateral ---
    st.sidebar.title("Perfil Activo")
    st.sidebar.subheader(f"{participante_actual.razon_social_o_nombre}")
    st.sidebar.write(f"**Rol:** {participante_actual.rol_jerarquico}")
    st.sidebar.button("Cerrar Sesión", on_click=logout)
    
    # --- UI: Panel Principal ---
    st.title(f"Expediente: {empresa.razon_social_o_nombre}")
    st.write(f"**RFC de la Empresa:** {empresa.rfc}")
    st.divider()
    
    st.subheader("Entidades Relacionadas")
    st.write("Seleccione el participante para gestionar sus formatos.")
    
    datos_tabla = []
    for p in vinculados:
        datos_tabla.append({
            "ID": p.id,
            "Nombre / Razón Social": p.razon_social_o_nombre,
            "RFC": p.rfc,
            "Tipo": p.tipo_persona,
            "Rol Jerárquico": p.rol_jerarquico
        })
        
    df = pd.DataFrame(datos_tabla)
    st.dataframe(df, hide_index=True, use_container_width=True)
    
    # Mapeo seguro directo de participantes
    mapa_nombres = {p.id: p.razon_social_o_nombre for p in vinculados}
    participante_seleccionado = st.selectbox(
        "Participante a documentar:", 
        options=list(mapa_nombres.keys()), 
        format_func=lambda x: mapa_nombres[x]
    )
    
    participante_obj = next((p for p in vinculados if p.id == participante_seleccionado), None)
    
    if participante_obj:
        st.divider()
        st.subheader(f"Datos Complementarios - {participante_obj.razon_social_o_nombre}")
        
        # --- BLOQUE 1: Formulario (Sólo widgets de entrada y su submit button) ---
        with st.form("formulario_captura"):
            st.info(f"Completando información para Persona {participante_obj.tipo_persona}")
            
            col1, col2 = st.columns(2)
            with col1:
                direccion = st.text_input("Dirección Completa")
            with col2:
                telefono = st.text_input("Teléfono de Contacto")
                
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
                st.session_state['datos_formulario'] = {
                    "nombre": participante_obj.razon_social_o_nombre,
                    "rfc": participante_obj.rfc,
                    "direccion": direccion,
                    "telefono": telefono,
                    **datos_dinamicos
                }
                st.session_state['participante_guardado_id'] = participante_obj.id
                st.rerun()

        # --- BLOQUE 2: Generación de Documento (FUERA DEL FORMULARIO) ---
        if 'datos_formulario' in st.session_state and st.session_state.get('participante_guardado_id') == participante_obj.id:
            st.divider()
            st.subheader("Generación de Documento")
            st.success("Datos validados en memoria. Listo para generar el formato oficial.")
            
            if st.button("Generar Formato Único (.docx)"):
                # 1. Cargar plantilla y renderizar datos
                doc = DocxTemplate("app/templates/formato_base.docx")
                doc.render(st.session_state['datos_formulario'])
                
                # 2. Guardar en memoria para descarga
                bio = io.BytesIO()
                doc.save(bio)
                bio.seek(0)
                
                # 3. Guardar copia en el servidor (app/outputs)
                ruta_salida = f"app/outputs/Formato_{participante_obj.rfc}.docx"
                os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
                doc.save(ruta_salida)
                
                # 4. Actualizar estado en la Base de Datos
                db_session = get_db_session()
                expediente = db_session.query(ExpedienteDocumento).filter_by(
                    participante_id=participante_obj.id, 
                    tipo_documento="Formato Unico"
                ).first()
                
                if not expediente:
                    nuevo_exp = ExpedienteDocumento(
                        participante_id=participante_obj.id,
                        tipo_documento="Formato Unico",
                        estatus="Lleno",
                        ruta_archivo=ruta_salida
                    )
                    db_session.add(nuevo_exp)
                else:
                    expediente.estatus = "Lleno"
                    expediente.ruta_archivo = ruta_salida
                    
                db_session.commit()
                db_session.close()
                
                st.success("¡Documento compilado y estatus actualizado en base de datos!")
                
                # 5. Botón de descarga
                st.download_button(
                    label="Descargar Archivo Generado (.docx)",
                    data=bio.getvalue(),
                    file_name=f"Formato_{participante_obj.rfc}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

    db.close()

def main():
    if 'autenticado' not in st.session_state:
        st.session_state['autenticado'] = False

    if not st.session_state['autenticado']:
        login()
    else:
        dashboard()

if __name__ == "__main__":
    main()