import sys
import os
import io
import zipfile
import unicodedata
import re
import datetime
import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate

from app.utils.documentos import procesar_excel, procesar_word, convertir_a_pdf, fusionar_pdfs

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import(
    SessionLocal, Usuario, Proyecto, Persona,
    Catalogo, Participacion, JerarquiaParticipacion, DocumentoExpediente,
    PlantillaFormato, ConfiguracionCampos, ConfiguracionEvidencia,
    supabase_client
)

from app.utils.auth import verificar_password, generar_hash

# ... (Tus importaciones arriba) ...

def limpiar_nombre_archivo(nombre: str) -> str:
    """Sanitiza nombres de archivo quitando acentos, caracteres especiales y espacios"""
    if not nombre:
        return "sin_nombre"
    
    # Asegurar que sea string
    nombre = str(nombre)
    # Quitar acentos, eñes y convertir a minúsculas
    nombre = unicodedata.normalize('NFKD', nombre).encode('ASCII', 'ignore').decode('utf-8').lower()
    # Reemplazar todo lo que no sea alfanumérico, punto o guion por un guion bajo
    nombre = re.sub(r'[^\w\.-]', '_', nombre)
    # Limpiar múltiples guiones bajos seguidos
    nombre = re.sub(r'_+', '_', nombre)
    
    return nombre.strip('_')

# Configuración global de la página
st.set_page_config(page_title="Control Documental", page_icon="??", layout="centered")

def get_db_session():
    return SessionLocal()

def login_y_otp():
    st.title("Portal de Control Documental")
    
    # Manejo del estado del OTP
    if 'usuario_temporal_id' in st.session_state:
        # PANTALLA 2: Cambio de contrase?a obligatorio
        st.warning("?? Por seguridad, debe cambiar su contrase?a temporal antes de continuar.")
        
        with st.form("form_cambio_password"):
            nueva_pwd = st.text_input("Nueva contrase?a", type="password")
            confirmar_pwd = st.text_input("Confirmar contrase?a", type="password")
            btn_cambiar = st.form_submit_button("Actualizar y Entrar")
            
            if btn_cambiar:
                if len(nueva_pwd) < 6:
                    st.error("La contrase?a debe tener al menos 6 caracteres.")
                elif nueva_pwd != confirmar_pwd:
                    st.error("Las contrase?as no coinciden.")
                else:
                    db = get_db_session()
                    usr = db.query(Usuario).filter(Usuario.id == st.session_state['usuario_temporal_id']).first()
                    
                    # Actualizamos base de datos
                    usr.password_hash = generar_hash(nueva_pwd)
                    usr.debe_cambiar_password = 0
                    db.commit()
                    
                    # Pasamos a sesi¨®n autenticada real
                    st.session_state['autenticado'] = True
                    st.session_state['usuario_id'] = usr.id
                    st.session_state['tipo_usuario'] = usr.tipo_usuario
                    st.session_state['email'] = usr.email
                    
                    del st.session_state['usuario_temporal_id']
                    db.close()
                    st.success("Contrase?a actualizada exitosamente.")
                    st.rerun()
    else:
        # PANTALLA 1: Login normal
        st.write("Ingrese sus credenciales de acceso.")
        
        with st.form("login_form"):
            email = st.text_input("Correo electrónico", placeholder="usuario@correo.com")
            password = st.text_input("Contraseña", type="password")
            submit_btn = st.form_submit_button("Ingresar")
            
            if submit_btn:
                if email and password:
                    db = get_db_session()
                    usr = db.query(Usuario).filter(Usuario.email == email).first()
                    
                    if usr and verificar_password(password, usr.password_hash):
                        if usr.debe_cambiar_password == 1:
                            st.session_state['usuario_temporal_id'] = usr.id
                        else:
                            st.session_state['autenticado'] = True
                            st.session_state['usuario_id'] = usr.id
                            st.session_state['tipo_usuario'] = usr.tipo_usuario
                            st.session_state['email'] = usr.email
                        
                        db.close()
                        st.rerun()
                    else:
                        db.close()
                        st.error("Credenciales inválidas.")
                else:
                    st.warning("Ingrese correo y contraseña.")

def logout():
    st.session_state.clear()
    st.rerun()

def dashboard_principal():
    st.sidebar.title("Perfil Activo")
    st.sidebar.subheader(f"{st.session_state['email']}")
    st.sidebar.write(f"**Rol:** {st.session_state['tipo_usuario']}")
    st.sidebar.button("Cerrar Sesión", on_click=logout)
    
    st.title("Panel de Control Principal")
    
    if st.session_state['tipo_usuario'] in ["SuperAdmin", "Admin"]:
        tabs = st.tabs(["📊 Tablero de Control", "📄 Plantillas", "📝 Variables y Evidencias", "📝 Campos Dinámicos", "📁 Proyectos",
        "👥 Personas", "⚙️ Catálogos", "🔗 Asignaciones y Jerarquías", "🔐 Accesos Web"])
        
        # --- TABLERO DE AVANCE ---
        with tabs[0]:
            st.subheader("Tablero de Avance Documental")
            st.write("Monitoreo en tiempo real del estado de los expedientes por proyecto.")
            
            db = get_db_session()
            
            # Recuperar todas las participaciones con sus documentos asociados
            participaciones = db.query(Participacion).all()
            
            if not participaciones:
                st.info("No hay participaciones asignadas en los proyectos.")
            else:
                datos_tablero = []
                for part in participaciones:
                    # Buscar el documento principal (Paquete Unificado o Formato Unico)
                    doc = db.query(DocumentoExpediente).filter(
                        DocumentoExpediente.participacion_id == part.id,
                        DocumentoExpediente.tipo_documento.in_(["Paquete Unificado", "Formato Unico"])
                    ).first()
                    
                    estatus_doc = doc.estatus if doc else "No empezado"
                    ultima_act = doc.fecha_actualizacion.strftime('%Y-%m-%d %H:%M') if doc else "-"
                    
                    datos_tablero.append({
                        "Proyecto": part.proyecto.nombre,
                        "Entidad / Persona": part.persona.razon_social_nombre,
                        "Rol": part.rol,
                        "Estatus Documental": estatus_doc,
                        "Última Actualización": ultima_act
                    })
                
                df_tablero = pd.DataFrame(datos_tablero)
                
                # Opciones de filtrado rápido
                col_f1, col_f2 = st.columns(2)
                filtro_proy = col_f1.selectbox("Filtrar por Proyecto", ["Todos"] + list(df_tablero["Proyecto"].unique()))
                filtro_estatus = col_f2.selectbox("Filtrar por Estatus", ["Todos"] + list(df_tablero["Estatus Documental"].unique()))
                
                # Aplicar filtros
                if filtro_proy != "Todos":
                    df_tablero = df_tablero[df_tablero["Proyecto"] == filtro_proy]
                if filtro_estatus != "Todos":
                    df_tablero = df_tablero[df_tablero["Estatus Documental"] == filtro_estatus]
                
                # Renderizar tabla coloreada según estatus (Opcional visual)
                def color_estatus(val):
                    color = 'green' if val == 'Firmado y Cargado' else 'orange' if val in ['Generado', 'Actualizado'] else 'red' if val == 'No empezado' else 'black'
                    return f'color: {color}'
             
            # ... (Código existente donde se renderiza la tabla del tablero de control) ...
                st.dataframe(df_tablero.style.map(color_estatus, subset=['Estatus Documental']), hide_index=True, use_container_width=True)

            # --- NUEVA SECCIÓN WBS 3.4.2: REVISIÓN DE EXPEDIENTES Y DESCARGA ---
            st.divider()
            st.subheader("🔍 Revisión de Expedientes Individuales")
            st.write("Seleccione un participante para revisar y descargar sus archivos de forma segura.")
            
            part_opts = {p.id: f"[{p.proyecto.nombre}] {p.persona.razon_social_nombre} ({p.rol})" for p in participaciones}
            if part_opts:
                part_sel_id = st.selectbox("Expediente a revisar:", options=list(part_opts.keys()), format_func=lambda x: part_opts[x])
                
                # Buscar todos los documentos de esa participación
                docs_part = db.query(DocumentoExpediente).filter_by(participacion_id=part_sel_id).all()
                
                if docs_part:
                    for d in docs_part:
                        with st.container():
                            col_d1, col_d2 = st.columns([3, 1])
                            with col_d1:
                                st.write(f"**{d.tipo_documento}** ({d.categoria_documento}) - Estatus: `{d.estatus}`")
                            with col_d2:
                                if d.ruta_archivo:
                                    if st.button("Generar Enlace de Descarga", key=f"btn_dl_sec_{d.id}"):
                                        try:
                                            # Genera URL que caduca en 60 segundos por máxima seguridad
                                            url_segura = supabase_client.storage.from_("expedientes").create_signed_url(d.ruta_archivo, 60)
                                            st.markdown(f"📥 [Clic para descargar (Expira en 60s)]({url_segura['signedURL']})", unsafe_allow_html=True)
                                        except Exception as e:
                                            st.error("Error al conectar con la bóveda segura.")
                else:
                    st.info("Este participante aún no ha subido ningún documento ni generado formatos.")

            # --- NUEVA SECCIÓN: WBS 2.5.3 Exportación de Datos ---
            st.divider()
            st.subheader("Herramientas de Exportación")
            
            with st.expander("📥 Exportar Base de Datos (Para Combinar Correspondencia)"):
                st.write("Descarga un archivo plano (CSV) con toda la información capturada de los participantes (incluyendo campos dinámicos) para usarlo en Microsoft Word u otros sistemas.")
                
                if participaciones:
                    datos_export = []
                    for part in participaciones:
                        # Datos Relacionales Fijos
                        fila = {
                            "ID_Proyecto": part.proyecto.id,
                            "Proyecto": part.proyecto.nombre,
                            "ID_Persona": part.persona.id,
                            "Razón Social / Nombre": part.persona.razon_social_nombre,
                            "RFC": part.persona.rfc,
                            "Tipo Persona": part.persona.tipo,
                            "Rol en Proyecto": part.rol
                        }
                        
                        # Aplanar Datos Dinámicos (JSONB) y convertirlos en columnas
                        datos_dinamicos = part.persona.datos_json or {}
                        for key, value in datos_dinamicos.items():
                            fila[f"Variable_{key.upper()}"] = value
                            
                        datos_export.append(fila)
                    
                    df_export = pd.DataFrame(datos_export)
                    # Convertir a CSV en memoria
                    csv_data = df_export.to_csv(index=False).encode('utf-8-sig') # utf-8-sig asegura que Excel lea bien los acentos
                    
                    st.download_button(
                        label="Descargar Base de Datos (.csv)",
                        data=csv_data,
                        file_name=f"exportacion_control_documental_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                    )
                else:
                    st.info("No hay datos para exportar.")

            db.close()
        # --- GESTOR DINÁMICO DE PLANTILLAS ---
        with tabs[1]:
            st.subheader("Gestor Dinámico de Plantillas")
            st.write("Configure los documentos individuales (Word/Excel), a quiénes aplican y dónde deben firmar.")
            
            db = get_db_session()
            roles_disponibles = [c.valor for c in db.query(Catalogo).filter_by(categoria="Rol_Participacion").all()]
            
            with st.expander("➕ Subir y Crear Nueva Plantilla"):
                with st.form("form_nueva_plantilla"):
                    nombre_tpl = st.text_input("Nombre del Formato (Ej. Declaración de Entidad)")
                    roles_sel = st.multiselect("Este formato aplica para los Roles:", options=roles_disponibles)
                    
                    # Carga del archivo físico
                    archivo_tpl = st.file_uploader("Subir Archivo de Plantilla (.docx, .xlsx)", type=["docx", "xlsx"])
                    
                    col_p1, col_p2 = st.columns(2)
                    paginas_tot = col_p1.number_input("Páginas Totales del Formato", min_value=1, step=1)
                    rubricar = col_p2.selectbox("¿Rubricar todas las páginas?", ["✅ Sí", "❌ No"])
                    
                    if st.form_submit_button("Subir y Crear Plantilla"):
                        if nombre_tpl and roles_sel and archivo_tpl:
                            # 1. Guardar el archivo físicamente EN SUPABASE STORAGE
                            ruta_guardado = f"templates/{archivo_tpl.name}"
                            try:
                                supabase_client.storage.from_("expedientes").upload(
                                    file=archivo_tpl.getvalue(),
                                    path=ruta_guardado,
                                    file_options={"content-type": archivo_tpl.type, "x-upsert": "true"}
                                )
                            except Exception as e:
                                st.error(f"Error subiendo archivo a la nube: {e}")
                                st.stop()
                                
                            # 2. Registrar en la base de datos            
                            nueva_tpl = PlantillaFormato(
                                nombre=nombre_tpl,
                                roles_aplica=roles_sel,
                                paginas_totales=paginas_tot,
                                rubricar_todas=rubricar,
                                firmas_json=[],
                                ruta_plantilla_word=ruta_guardado
                            )
                            db.add(nueva_tpl)
                            db.commit()
                            st.success("Plantilla creada exitosamente. Configura las firmas abajo.")
                            st.rerun()
                        else:
                            st.error("El nombre, los roles y el archivo son obligatorios.")
                            
            # Listar y editar plantillas existentes (Mantenemos tu código anterior del st.data_editor aquí)
            plantillas = db.query(PlantillaFormato).all()
            if plantillas:
                st.write("**Configuración de Firmas por Documento:**")
                for tpl in plantillas:
                    with st.expander(f"📄 {tpl.nombre} (Aplica a: {', '.join(tpl.roles_aplica)})", expanded=True):
                        st.caption(f"Archivo: {tpl.ruta_plantilla_word} | Longitud: {tpl.paginas_totales} págs.")
                        # ... [Mantén aquí todo tu código actual del st.data_editor y el guardado de firmas] ...
                        
                        if tpl.firmas_json:
                            df_firmas = pd.DataFrame(tpl.firmas_json)
                        else:
                            df_firmas = pd.DataFrame(columns=["pag_formato", "tipo_firma"])
                        
                        df_editado = st.data_editor(
                            df_firmas,
                            num_rows="dynamic",
                            column_config={
                                "pag_formato": st.column_config.NumberColumn("Página (dentro de este formato)", min_value=1, max_value=tpl.paginas_totales, step=1, required=True),
                                "tipo_firma": st.column_config.SelectboxColumn("Tipo de Firma", options=["Firma Simple", "Nombre y Firma", "Nombre, Firma y Huella", "Solo Rúbrica"], required=True)
                            },
                            key=f"editor_firmas_{tpl.id}",
                            use_container_width=True
                        )
                        
                        # Controles de edición rápida
                        col_a, col_b, col_c, col_d = st.columns([2, 1, 1, 1])
                        with col_a:
                            nuevos_roles = st.multiselect("Modificar Roles", options=roles_disponibles, default=tpl.roles_aplica, key=f"roles_{tpl.id}")
                        with col_b:
                            nueva_pag = st.number_input("Modificar Páginas", min_value=1, value=tpl.paginas_totales, key=f"pags_{tpl.id}")
                        with col_c:
                            st.write("") 
                            st.write("")
                            if st.button("💾 Guardar", key=f"btn_save_{tpl.id}"):
                                tpl.roles_aplica = nuevos_roles
                                tpl.paginas_totales = nueva_pag
                                tpl.firmas_json = df_editado.to_dict(orient="records")
                                db.commit()
                                st.success("Configuración actualizada.")
                                st.rerun()
                        with col_d:
                            st.write("") 
                            st.write("")
                            if st.button("🗑️ Eliminar", key=f"btn_del_{tpl.id}"):
                                db.delete(tpl)
                                db.commit()
                                st.success("Plantilla eliminada.")
                                st.rerun()
            db.close()
            
        # --- GESTOR DE CAMPOS Y EVIDENCIAS ---
        with tabs[2]:
            st.subheader("Configuración de Variables y Evidencias")
            st.write("Defina qué información (texto) y qué archivos (PDFs/Imágenes) se solicitarán dinámicamente a los usuarios.")
            
            db = get_db_session()
            roles_disponibles = [c.valor for c in db.query(Catalogo).filter_by(categoria="Rol_Participacion").all()]
            
            col_izq, col_der = st.columns(2)
            
            with col_izq:
                st.markdown("### 1️⃣ Campos de Texto (Variables)")
                with st.expander("➕ Crear Nuevo Campo Obligatorio"):
                    with st.form("form_nuevo_campo_dinamico"):
                        nombre = st.text_input("Nombre a mostrar (Ej. CURP)")
                        llave = st.text_input("Variable Jinja (Ej. curp)")
                        tipo_input = st.selectbox("Tipo de Dato", ["Texto", "Fecha", "Número", "Opciones"])
                        tipo_pers = st.selectbox("Aplica para:", ["Ambas", "Fisica", "Moral"], key="tp_campo")
                        roles_sel = st.multiselect("Aplica a Roles:", options=roles_disponibles)
                        opciones = st.text_input("Opciones (separadas por coma)")
                        regla = st.selectbox("Regla de Validación", ["ninguna", "max_90_dias", "vigente_futuro"])
                        
                        if st.form_submit_button("Guardar Campo") and nombre and llave:
                            opc_lista = [o.strip() for o in opciones.split(",")] if tipo_input == "Opciones" and opciones else []
                            db.add(ConfiguracionCampos(
                                nombre_mostrar=nombre, llave_jinja=llave.lower().replace(" ", "_"),
                                tipo_input=tipo_input, opciones_json=opc_lista, tipo_persona=tipo_pers,
                                roles_aplica=roles_sel, regla_validacion=regla
                            ))
                            db.commit()
                            st.rerun()

                # Lista de Campos
                campos_registrados = db.query(ConfiguracionCampos).all()
                for c in campos_registrados:
                    with st.expander(f"📌 {c.nombre_mostrar} `{{{{{c.llave_jinja}}}}}`"):
                        st.write(f"Input: {c.tipo_input} | Persona: {c.tipo_persona}")
                        if st.button("🗑️ Eliminar", key=f"del_campo_txt_{c.id}"):
                            db.delete(c)
                            db.commit()
                            st.rerun()

            with col_der:
                st.markdown("### 2️⃣ Evidencias Adjuntas (Archivos)")
                with st.expander("➕ Crear Nueva Evidencia Requerida"):
                    with st.form("form_nueva_evidencia"):
                        nombre_evidencia = st.text_input("Nombre del Documento (Ej. Identificación Oficial)")
                        tipo_pers_ev = st.selectbox("Aplica para:", ["Ambas", "Fisica", "Moral"], key="tp_evidencia")
                        roles_sel_ev = st.multiselect("Aplica a Roles:", options=roles_disponibles, key="roles_ev")
                        
                        if st.form_submit_button("Guardar Evidencia") and nombre_evidencia:
                            db.add(ConfiguracionEvidencia(
                                nombre_evidencia=nombre_evidencia,
                                tipo_persona=tipo_pers_ev,
                                roles_aplica=roles_sel_ev
                            ))
                            db.commit()
                            st.rerun()

                # Lista de Evidencias
                evidencias_registradas = db.query(ConfiguracionEvidencia).all()
                for ev in evidencias_registradas:
                    with st.expander(f"📎 {ev.nombre_evidencia}"):
                        st.write(f"Persona: {ev.tipo_persona} | Roles: {', '.join(ev.roles_aplica) if ev.roles_aplica else 'Todos'}")
                        if st.button("🗑️ Eliminar", key=f"del_ev_adj_{ev.id}"):
                            db.delete(ev)
                            db.commit()
                            st.rerun()
            db.close()
        
        # --- GESTOR DE CAMPOS Y VALIDACIONES (WBS 3.2.2) ---
        with tabs[3]:
            st.subheader("Configuración de Campos y Validaciones")
            st.write("Defina qué información se solicitará a los usuarios en el portal, la etiqueta Jinja que la vinculará a Word/Excel, y si requiere pasar por una regla matemática.")
            
            db = get_db_session()
            roles_disponibles = [c.valor for c in db.query(Catalogo).filter_by(categoria="Rol_Participacion").all()]
            
            with st.expander("➕ Crear Nuevo Campo Obligatorio"):
                with st.form("form_nuevo_campo"):
                    col1, col2 = st.columns(2)
                    nombre = col1.text_input("Nombre a mostrar en formulario (Ej. Fecha de Comprobante)")
                    llave = col2.text_input("Variable en Plantilla (Ej. fecha_comprobante)")
                    
                    col3, col4 = st.columns(2)
                    tipo_input = col3.selectbox("Tipo de Dato (Input)", ["Texto", "Fecha", "Número", "Opciones"])
                    tipo_pers = col4.selectbox("Aplica para el tipo de persona:", ["Ambas", "Fisica", "Moral"])
                    
                    roles_sel = st.multiselect("Aplica a los Roles:", options=roles_disponibles, help="Si lo dejas vacío, se le pedirá a todos los roles.")
                    
                    col5, col6 = st.columns(2)
                    opciones = col5.text_input("Opciones (Separadas por coma, solo si elegiste 'Opciones')")
                    regla = col6.selectbox("Regla de Validación Matemática", ["ninguna", "max_90_dias (Antigüedad)", "vigente_futuro (Caducidad)"])
                    
                    if st.form_submit_button("Guardar Campo"):
                        if nombre and llave:
                            opc_lista = [o.strip() for o in opciones.split(",")] if tipo_input == "Opciones" and opciones else []
                            nuevo_campo = ConfiguracionCampos(
                                nombre_mostrar=nombre,
                                llave_jinja=llave.lower().replace(" ", "_"),
                                tipo_input=tipo_input,
                                opciones_json=opc_lista,
                                tipo_persona=tipo_pers,
                                roles_aplica=roles_sel,
                                regla_validacion=regla.split(" ")[0] # Guardamos solo la llave ("max_90_dias")
                            )
                            db.add(nuevo_campo)
                            db.commit()
                            st.success("Campo creado exitosamente.")
                            st.rerun()
                        else:
                            st.error("El nombre y la variable Jinja son obligatorios.")

            # Listado de Campos
            campos_registrados = db.query(ConfiguracionCampos).all()
            if campos_registrados:
                st.write("**Catálogo de Campos Configurados:**")
                for c in campos_registrados:
                    with st.expander(f"📌 {c.nombre_mostrar} `{{{{{c.llave_jinja}}}}}`"):
                        st.write(f"**Input:** {c.tipo_input} | **Aplica a:** {c.tipo_persona} | **Validación:** {c.regla_validacion}")
                        st.write(f"**Roles Específicos:** {', '.join(c.roles_aplica) if c.roles_aplica else 'Todos los roles'}")
                        if c.opciones_json:
                            st.write(f"**Valores:** {', '.join(c.opciones_json)}")
                            
                        if st.button("🗑️ Eliminar", key=f"del_campo_{c.id}"):
                            db.delete(c)
                            db.commit()
                            st.rerun()
            db.close()
            
        # --- GESTIÓN DE PROYECTOS ---
        with tabs[4]:
            st.subheader("Gestión de Proyectos")
            # ... (tu código actual de Proyectos)
            with st.expander("➕ Crear Nuevo Proyecto"):
                with st.form("form_nuevo_proyecto"):
                    nombre_proyecto = st.text_input("Nombre del Proyecto")
                    if st.form_submit_button("Guardar Proyecto") and nombre_proyecto:
                        db = get_db_session()
                        db.add(Proyecto(nombre=nombre_proyecto))
                        db.commit()
                        db.close()
                        st.success(f"Proyecto '{nombre_proyecto}' creado.")
                        st.rerun()
            db = get_db_session()
            proyectos = db.query(Proyecto).all()
            if proyectos:
                st.dataframe(pd.DataFrame([{"ID": p.id, "Nombre": p.nombre, "Estatus": p.estatus_general} for p in proyectos]), hide_index=True, use_container_width=True)
            db.close()

        # --- CATÁLOGO MAESTRO ---
        with tabs[5]:
            st.subheader("Catálogo Maestro de Personas")
            # ... (tu código actual de Personas)
            with st.expander("➕ Registrar Nueva Persona"):
                with st.form("form_nueva_persona"):
                    col1, col2 = st.columns(2)
                    tipo_persona = col1.selectbox("Tipo de Persona", ["Moral", "Fisica"])
                    rfc = col2.text_input("RFC (Opcional)")
                    razon_social = st.text_input("Nombre o Razón Social")
                    if st.form_submit_button("Guardar Persona") and razon_social:
                        db = get_db_session()
                        db.add(Persona(tipo=tipo_persona, rfc=rfc, razon_social_nombre=razon_social))
                        db.commit()
                        db.close()
                        st.success("Persona registrada.")
                        st.rerun()
            db = get_db_session()
            personas = db.query(Persona).all()
            if personas:
                st.dataframe(pd.DataFrame([{"ID": p.id, "Tipo": p.tipo, "Razón Social / Nombre": p.razon_social_nombre} for p in personas]), hide_index=True, use_container_width=True)
            db.close()

        # --- VARIABLES DE SISTEMA ---
        with tabs[6]:
            st.subheader("Configuración de Variables del Sistema")
            # ... (tu código actual de Catálogos)
            db = get_db_session()
            with st.form("form_catalogo"):
                col1, col2 = st.columns(2)
                categoria = col1.selectbox("Categoría", ["Rol_Participacion", "Tipo_Relacion"], format_func=lambda x: "Roles en Proyecto" if x == "Rol_Participacion" else "Relación entre Personas")
                nuevo_valor = col2.text_input("Nuevo Valor")
                if st.form_submit_button("Agregar al Catálogo") and nuevo_valor:
                    if not db.query(Catalogo).filter_by(categoria=categoria, valor=nuevo_valor).first():
                        db.add(Catalogo(categoria=categoria, valor=nuevo_valor))
                        db.commit()
                        st.success("Valor agregado.")
                        st.rerun()
            catalogos = db.query(Catalogo).all()
            if catalogos:
                st.dataframe(pd.DataFrame([{"Categoría": c.categoria, "Valor": c.valor} for c in catalogos]), hide_index=True)
            db.close()

        # --- EXPEDIENTES ---
        with tabs[7]:
            st.subheader("Construcción del Expediente")
            db = get_db_session()
            
            proyectos_opts = {p.id: p.nombre for p in db.query(Proyecto).all()}
            personas_opts = {p.id: f"{p.razon_social_nombre} ({p.tipo})" for p in db.query(Persona).all()}
            roles_opts = [c.valor for c in db.query(Catalogo).filter_by(categoria="Rol_Participacion").all()]
            relaciones_opts = [c.valor for c in db.query(Catalogo).filter_by(categoria="Tipo_Relacion").all()]
            
            # Bloque 1: Asignar al proyecto
            with st.expander("1. Asignar Persona a Proyecto"):
                with st.form("form_participacion"):
                    col1, col2, col3 = st.columns(3)
                    sel_proy = col1.selectbox("Proyecto", options=list(proyectos_opts.keys()), format_func=lambda x: proyectos_opts[x])
                    sel_pers = col2.selectbox("Persona", options=list(personas_opts.keys()), format_func=lambda x: personas_opts[x])
                    sel_rol = col3.selectbox("Rol", options=roles_opts if roles_opts else ["Sin opciones"])
                    
                    if st.form_submit_button("Asignar al Proyecto") and roles_opts:
                        if not db.query(Participacion).filter_by(proyecto_id=sel_proy, persona_id=sel_pers).first():
                            db.add(Participacion(proyecto_id=sel_proy, persona_id=sel_pers, rol=sel_rol))
                            db.commit()
                            st.rerun()

            # Bloque 2: Jerarquías Dinámicas
            participaciones = db.query(Participacion).all()
            part_opts = {p.id: f"[{p.proyecto.nombre}] {p.persona.razon_social_nombre} - {p.rol}" for p in participaciones}
            
            if part_opts and relaciones_opts:
                st.divider()
                st.write("**2. Establecer Relaciones Jerárquicas**")
                with st.form("form_jerarquia"):
                    st.write("Ejemplo: [Juan Pérez - Apoderado] -> Representa a -> [Empresa S.A. - Fideicomitente]")
                    col1, col2, col3 = st.columns(3)
                    hijo_id = col1.selectbox("Entidad / Persona", options=list(part_opts.keys()), format_func=lambda x: part_opts[x])
                    tipo_rel = col2.selectbox("Tipo de Relación", options=relaciones_opts)
                    padre_id = col3.selectbox("Se vincula hacia", options=list(part_opts.keys()), format_func=lambda x: part_opts[x])
                    
                    if st.form_submit_button("Vincular Entidades"):
                        if hijo_id != padre_id:
                            if not db.query(JerarquiaParticipacion).filter_by(padre_id=padre_id, hijo_id=hijo_id).first():
                                db.add(JerarquiaParticipacion(padre_id=padre_id, hijo_id=hijo_id, tipo_relacion=tipo_rel))
                                db.commit()
                                st.success("Vínculo creado.")
                                st.rerun()
                        else:
                            st.error("Una entidad no puede vincularse consigo misma.")
                            
                # Mostrar Matriz de Jerarquías
                jerarquias = db.query(JerarquiaParticipacion).all()
                if jerarquias:
                    st.write("Matriz de Relaciones Activas:")
                    df_jer = pd.DataFrame([{
                        "De (Hijo)": j.hijo.persona.razon_social_nombre,
                        "Relación": j.tipo_relacion,
                        "Hacia (Padre)": j.padre.persona.razon_social_nombre,
                        "Proyecto": j.padre.proyecto.nombre
                    } for j in jerarquias])
                    st.dataframe(df_jer, hide_index=True)

            db.close()

        # --- ACCESOS WEB PARA GESTORES ---
        with tabs[8]:
            st.subheader("Otorgar Acceso a Usuarios Operativos")
            st.write("Vincula un correo electrónico con una Persona del catálogo. Si el correo no existe, el sistema le creará una cuenta temporal.")
            db = get_db_session()
            
            personas_maestro_opts = {p.id: f"{p.razon_social_nombre} ({p.tipo})" for p in db.query(Persona).all()}
            
            with st.form("form_accesos"):
                email_gestor = st.text_input("Correo Electrónico del Gestor / Responsable")
                persona_asignada = st.selectbox("Persona que podrá administrar", options=list(personas_maestro_opts.keys()), format_func=lambda x: personas_maestro_opts[x])
                
                if st.form_submit_button("Conceder Acceso"):
                    if email_gestor:
                        email_gestor = email_gestor.strip().lower()
                        # Buscar o crear usuario
                        usuario = db.query(Usuario).filter(Usuario.email == email_gestor).first()
                        if not usuario:
                            usuario = Usuario(
                                email=email_gestor,
                                password_hash=generar_hash("Temporal123!"), # Contraseña OTP por defecto
                                tipo_usuario="Usuario",
                                debe_cambiar_password=1
                            )
                            db.add(usuario)
                            db.commit()
                            st.info(f"Usuario nuevo creado. Contraseña temporal: Temporal123!")
                            
                        # Buscar a la persona y vincularla
                        persona = db.query(Persona).filter(Persona.id == persona_asignada).first()
                        if persona not in usuario.personas_gestor:
                            usuario.personas_gestor.append(persona)
                            db.commit()
                            st.success(f"Acceso concedido a {email_gestor} para administrar a {persona.razon_social_nombre}.")
                        else:
                            st.warning("Este usuario ya tiene acceso a esta entidad.")
            
            db.close()

    # ---------------------------------------------------------
    # VISTA PARA USUARIOS OPERATIVOS (Externos)
    # ---------------------------------------------------------
    else:
        st.subheader("Mis Expedientes Asignados")
        st.write("Aquí visualizarás y llenarás los formatos de las entidades que tienes a tu cargo.")
        
        db = get_db_session()
        usr = db.query(Usuario).filter(Usuario.id == st.session_state['usuario_id']).first()
        
        if usr.personas_gestor:
            # 1. Obtener participaciones DIRECTAS e HIJAS
            personas_ids = [p.id for p in usr.personas_gestor]
            part_directas = db.query(Participacion).filter(Participacion.persona_id.in_(personas_ids)).all()
            part_directas_ids = [p.id for p in part_directas]
            jerarquias = db.query(JerarquiaParticipacion).filter(JerarquiaParticipacion.padre_id.in_(part_directas_ids)).all()
            part_hijas = [j.hijo for j in jerarquias]
            
            # 2. Unir y agrupar por Proyecto
            todas_participaciones = {p.id: p for p in (part_directas + part_hijas)}.values()
            proyectos_asignados = {}
            for part in todas_participaciones:
                if part.proyecto.id not in proyectos_asignados:
                    proyectos_asignados[part.proyecto.id] = {"nombre": part.proyecto.nombre, "participantes": []}
                proyectos_asignados[part.proyecto.id]["participantes"].append(part)

            # 3. Renderizar Interfaz
            for proy_id, proy_data in proyectos_asignados.items():
                st.markdown(f"### 📁 Proyecto: {proy_data['nombre']}")
                
                for part in proy_data["participantes"]:
                    with st.expander(f"👤 {part.persona.razon_social_nombre} ({part.persona.tipo}) - Rol: {part.rol}"):
                        
                        # --- MOTOR DE FORMULARIO DINÁMICO Y VALIDACIONES (WBS 3.2.3) ---
                        st.caption("Complete los datos requeridos para generar los formatos.")
                        datos_actuales = part.persona.datos_json or {}
                        
                        # 1. Filtramos los campos que le aplican a esta entidad
                        todos_campos = db.query(ConfiguracionCampos).all()
                        campos_aplicables = []
                        for c in todos_campos:
                            # Validar Tipo de Persona
                            if c.tipo_persona not in ["Ambas", part.persona.tipo]:
                                continue
                            # Validar Rol
                            if c.roles_aplica and part.rol not in c.roles_aplica:
                                continue
                            campos_aplicables.append(c)
                        
                        if not campos_aplicables:
                            st.info("No hay datos adicionales requeridos para el perfil de esta entidad.")
                        else:
                            nuevos_datos = {}
                            with st.form(f"form_datos_{part.id}"):
                                cols = st.columns(2)
                                
                                for i, c in enumerate(campos_aplicables):
                                    col = cols[i % 2]
                                    val_previo = datos_actuales.get(c.llave_jinja, "")
                                    
                                    with col:
                                        if c.tipo_input == "Texto":
                                            nuevos_datos[c.llave_jinja] = st.text_input(c.nombre_mostrar, value=val_previo)
                                            
                                        elif c.tipo_input == "Número":
                                            try: val_num = float(val_previo) if val_previo else 0.0
                                            except: val_num = 0.0
                                            nuevos_datos[c.llave_jinja] = st.number_input(c.nombre_mostrar, value=val_num)
                                            
                                        elif c.tipo_input == "Opciones":
                                            opciones = c.opciones_json if c.opciones_json else ["Sin opciones"]
                                            idx = opciones.index(val_previo) if val_previo in opciones else 0
                                            nuevos_datos[c.llave_jinja] = st.selectbox(c.nombre_mostrar, options=opciones, index=idx)
                                            
                                        elif c.tipo_input == "Fecha":
                                            val_fecha = datetime.date.today()
                                            if val_previo:
                                                try: val_fecha = datetime.datetime.strptime(val_previo, "%Y-%m-%d").date()
                                                except: pass
                                            nuevos_datos[c.llave_jinja] = st.date_input(c.nombre_mostrar, value=val_fecha)
                                
                                # Botón estrictamente dentro del bloque 'with st.form'
                                submit_btn = st.form_submit_button("Validar y Guardar Datos")
                                
                                if submit_btn:
                                    errores = []
                                    for c in campos_aplicables:
                                        val = nuevos_datos[c.llave_jinja]
                                        
                                        if c.tipo_input == "Fecha":
                                            if c.regla_validacion == "max_90_dias":
                                                diferencia = (datetime.date.today() - val).days
                                                if diferencia > 90:
                                                    errores.append(f"❌ '{c.nombre_mostrar}' excede los 90 días de antigüedad.")
                                                elif diferencia < 0:
                                                    errores.append(f"❌ '{c.nombre_mostrar}' no puede ser una fecha futura.")
                                                    
                                            elif c.regla_validacion == "vigente_futuro":
                                                if val < datetime.date.today():
                                                    errores.append(f"❌ '{c.nombre_mostrar}' indica que el documento ya está vencido.")
                                    
                                    if errores:
                                        for e in errores:
                                            st.error(e)
                                    else:
                                        for k, v in nuevos_datos.items():
                                            if isinstance(v, datetime.date):
                                                nuevos_datos[k] = v.strftime("%Y-%m-%d")
                                                
                                        part.persona.datos_json = nuevos_datos
                                        db.commit()
                                        st.success("✅ Datos validados y guardados exitosamente.")
                                        st.rerun()

                        # --- GENERACIÓN DE PAQUETE PDF E INSTRUCCIONES ---
                        st.divider()
                        st.write("📄 **Gestión del Paquete Documental**")
                        
                        doc_exp = db.query(DocumentoExpediente).filter_by(
                            participacion_id=part.id, 
                            tipo_documento="Paquete Unificado"
                        ).first()
                        
                        plantillas_aplicables = [
                            tpl for tpl in db.query(PlantillaFormato).all() 
                            if tpl.roles_aplica and part.rol in tpl.roles_aplica
                        ]

                        col_izq, col_der = st.columns([1, 1])
                        
                        with col_izq:
                            if doc_exp:
                                st.info(f"Estatus: **{doc_exp.estatus}**")
                            else:
                                st.warning("Estatus: **No generado**")
                                
                            if not plantillas_aplicables:
                                st.error("No hay formatos configurados para este rol.")
                            else:
                                if st.button(f"Generar Paquete PDF Unificado", key=f"btn_gen_{part.id}"):
                                    context = {"nombre": part.persona.razon_social_nombre, "rfc": part.persona.rfc or "", **datos_actuales}
                                    
                                    lista_pdfs = []
                                    
                                    # st.spinner muestra una animación mientras hace el trabajo pesado
                                    with st.spinner("Compilando documentos y convirtiendo a PDF... Esto puede tomar unos segundos."):
                                        for tpl in plantillas_aplicables:
                                            if tpl.ruta_plantilla_word:
                                                extension = os.path.splitext(tpl.ruta_plantilla_word)[1].lower()
                                                try:
                                                    # 1. Descargar de la nube
                                                    archivo_bytes = supabase_client.storage.from_("expedientes").download(tpl.ruta_plantilla_word)
                                                    
                                                    # 2. Procesar (Inyectar datos)
                                                    if extension == ".docx":
                                                        doc_procesado = procesar_word(archivo_bytes, context)
                                                    elif extension == ".xlsx":
                                                        doc_procesado = procesar_excel(archivo_bytes, context)
                                                    else:
                                                        continue
                                                        
                                                    # 3. Convertir a PDF nativo
                                                    pdf_bytes = convertir_a_pdf(doc_procesado, extension)
                                                    lista_pdfs.append(pdf_bytes)
                                                    
                                                except Exception as e:
                                                    st.error(f"Error procesando '{tpl.nombre}': {e}")
                                        
                                        # 4. Unir todos los PDFs en uno solo
                                        if lista_pdfs:
                                            pdf_final_bytes = fusionar_pdfs(lista_pdfs)
                                            st.session_state[f'pdf_bytes_{part.id}'] = pdf_final_bytes
                                            
                                            if not doc_exp:
                                                db.add(DocumentoExpediente(
                                                    participacion_id=part.id,
                                                    categoria_documento="Paquete",
                                                    tipo_documento="Paquete Unificado",
                                                    estatus="Generado"
                                                ))
                                            else:
                                                doc_exp.estatus = "Actualizado"
                                            db.commit()
                                            st.rerun()
                                        else:
                                            st.error("No se pudo generar ningún documento. Verifique las plantillas.")

                                # Mostrar botón de descarga del PDF
                                if doc_exp or f'pdf_bytes_{part.id}' in st.session_state:
                                    if f'pdf_bytes_{part.id}' in st.session_state:
                                        st.download_button(
                                            label="⬇️ 1. Descargar Paquete (.pdf)",
                                            data=st.session_state[f'pdf_bytes_{part.id}'],
                                            file_name=f"Paquete_{part.persona.razon_social_nombre.replace(' ', '_')}.pdf",
                                            mime="application/pdf",
                                            key=f"dl_{part.id}"
                                        )
                                    else:
                                        st.info("Por favor, vuelve a dar clic en 'Generar Paquete PDF' para cargar el archivo en memoria.")
                                        
                        with col_der:
                            # Carga del PDF escaneado (Se mantiene intacto)
                            archivo_subido = st.file_uploader("⬆️ 3. Subir Paquete Firmado (.pdf)", type=["pdf"], key=f"up_{part.id}")
                            if archivo_subido is not None:
                                if st.button("Confirmar Entrega de Documento", key=f"btn_up_{part.id}"):
                                    timestamp = int(datetime.datetime.now().timestamp())
                                    proy_limpio = limpiar_nombre_archivo(part.proyecto.nombre)
                                    pers_limpio = limpiar_nombre_archivo(part.persona.razon_social_nombre)
                                    
                                    ruta_pdf = f"firmados/{proy_limpio}-{pers_limpio}-formatos-{timestamp}.pdf"
                                    
                                    try:
                                        supabase_client.storage.from_("expedientes").upload(
                                            file=archivo_subido.getvalue(),
                                            path=ruta_pdf,
                                            file_options={"content-type": "application/pdf", "x-upsert": "true"}
                                        )
                                        
                                        doc_exp.estatus = "Firmado y Cargado"
                                        doc_exp.ruta_archivo = ruta_pdf
                                        db.commit()
                                        st.success("¡Documento enviado y resguardado en la nube de forma segura!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error subiendo a la nube: {e}")

                        # Mostrar Instrucciones Actualizadas (Con Doble Paginación restaurada)
                        if doc_exp and plantillas_aplicables:
                            st.markdown("### 📋 Instrucciones de Firma")
                            st.write("2. Descargue el paquete único en formato PDF e imprímalo. Firme según la siguiente tabla:")
                            
                            filas_tabla = []
                            total_firmas_paquete = 0
                            offset_paginas = 0
                            
                            for formato in plantillas_aplicables:
                                firmas = formato.firmas_json or []
                                num_firmas = len(firmas)
                                total_firmas_paquete += num_firmas
                                
                                for i, firma in enumerate(firmas):
                                    pag_documento = offset_paginas + int(firma.get("pag_formato", 0))
                                    
                                    filas_tabla.append({
                                        "Documento": formato.nombre if i == 0 else "",
                                        "Núm. Firmas": num_firmas if i == 0 else "",
                                        "Pág (Formato)": firma.get("pag_formato", ""),
                                        "Pág (Documento)": pag_documento,
                                        "Tipo de Firma": firma.get("tipo_firma", ""),
                                        "Rubricar todas": formato.rubricar_todas if i == 0 else ""
                                    })
                                
                                if num_firmas == 0:
                                    filas_tabla.append({
                                        "Documento": formato.nombre,
                                        "Núm. Firmas": 0,
                                        "Pág (Formato)": "-",
                                        "Pág (Documento)": "-",
                                        "Tipo de Firma": "-",
                                        "Rubricar todas": formato.rubricar_todas
                                    })
                                
                                # Actualizamos el offset sumando las páginas del formato actual
                                offset_paginas += formato.paginas_totales
                                    
                            filas_tabla.append({
                                "Documento": "TOTAL PAQUETE",
                                "Núm. Firmas": f"**{total_firmas_paquete}**",
                                "Pág (Formato)": "",
                                "Pág (Documento)": "",
                                "Tipo de Firma": "",
                                "Rubricar todas": ""
                            })
                            
                            st.markdown(pd.DataFrame(filas_tabla).style.hide(axis="index").to_html(), unsafe_allow_html=True)
                        
                        # --- NUEVA SECCIÓN WBS 3.3: TRAZABILIDAD FÍSICA ---
                        if doc_exp and doc_exp.estatus in ["Firmado y Cargado", "Enviado Físicamente", "Recibido", "Validado Original"]:
                            st.divider()
                            st.markdown("### 📦 Trazabilidad del Documento Original")
                            
                            meta = doc_exp.metadata_json or {}
                            
                            # MODO 1: YA FUE ENVIADO (Vista de Solo Lectura y Reinicio)
                            if doc_exp.estatus in ["Enviado Físicamente", "Recibido", "Validado Original"]:
                                st.success(f"✅ Estatus físico actual: **{doc_exp.estatus}**")
                                st.write(f"**Método:** {meta.get('metodo', 'N/A')} | **Fecha de envío/entrega:** {meta.get('fecha_envio', 'N/A')}")
                                
                                if meta.get('metodo') == "Enviado por paquetería":
                                    st.write(f"**Paquetería:** {meta.get('empresa', 'N/A')} | **Guía:** {meta.get('guia', 'N/A')}")
                                    
                                st.warning("⚠️ Si cometió un error o la documentación fue rechazada, puede reiniciar el flujo. Deberá volver a generar y firmar los documentos.")
                                if st.button("🔄 Reiniciar Flujo", key=f"btn_restart_{part.id}"):
                                    # Lo devolvemos al estado de "Actualizado" (para que tenga que volver a subir el PDF)
                                    doc_exp.estatus = "Actualizado"
                                    # Limpiamos los datos del envío
                                    meta.pop("metodo", None)
                                    meta.pop("fecha_envio", None)
                                    meta.pop("empresa", None)
                                    meta.pop("guia", None)
                                    doc_exp.metadata_json = meta
                                    db.commit()
                                    st.rerun()

                            # MODO 2: CAPTURA DE ENVÍO
                            elif doc_exp.estatus == "Firmado y Cargado":
                                st.write("Registre los datos del envío físico de los documentos originales al corporativo.")
                                
                                metodo = st.radio("Método de entrega", ["Entregado a responsable", "Enviado por paquetería"], key=f"metodo_{part.id}")
                                
                                admins_proyecto = [admin.email for admin in part.proyecto.admins]
                                admin_texto = ", ".join(admins_proyecto) if admins_proyecto else "Administrador de Proyecto (Pendiente de asignar)"
                                
                                empresa, guia = "", ""
                                if metodo == "Entregado a responsable":
                                    st.info(f"👤 Entregar a: **{admin_texto}**")
                                else:
                                    col_a, col_b = st.columns(2)
                                    empresa = col_a.text_input("Empresa de paquetería", key=f"emp_{part.id}")
                                    guia = col_b.text_input("Número de guía", key=f"guia_{part.id}")
                                    
                                fecha_envio = st.date_input("Fecha de entrega/envío", value=datetime.date.today(), key=f"fecha_{part.id}")
                                
                                if st.button("Registrar Envío/Entrega", key=f"btn_track_{part.id}"):
                                    nuevos_meta = meta.copy()
                                    nuevos_meta["metodo"] = metodo
                                    nuevos_meta["fecha_envio"] = fecha_envio.strftime("%Y-%m-%d")
                                    if metodo == "Enviado por paquetería":
                                        nuevos_meta["empresa"] = empresa
                                        nuevos_meta["guia"] = guia
                                        
                                    doc_exp.metadata_json = nuevos_meta
                                    doc_exp.estatus = "Enviado Físicamente"
                                    db.commit()
                                    # El rerun ahora nos llevará automáticamente al MODO 1
                                    st.rerun()
        
                        # --- NUEVA SECCIÓN WBS 3.4.1: EVIDENCIAS ADJUNTAS ---
                        st.divider()
                        st.write("📎 **Evidencias Adjuntas Requeridas**")
                        
                        todas_evidencias = db.query(ConfiguracionEvidencia).all()
                        evidencias_aplicables = [
                            e for e in todas_evidencias 
                            if e.tipo_persona in ["Ambas", part.persona.tipo] 
                            and (not e.roles_aplica or part.rol in e.roles_aplica)
                        ]
                        
                        if not evidencias_aplicables:
                            st.info("No se requieren documentos probatorios adicionales para este perfil.")
                        else:
                            for ev in evidencias_aplicables:
                                # Buscar si ya se subió
                                doc_ev = db.query(DocumentoExpediente).filter_by(
                                    participacion_id=part.id,
                                    categoria_documento="Evidencia_Adjunta",
                                    tipo_documento=ev.nombre_evidencia
                                ).first()
                                
                                col_ev1, col_ev2 = st.columns([1, 1])
                                
                                with col_ev1:
                                    st.markdown(f"**{ev.nombre_evidencia}**")
                                    if doc_ev and doc_ev.estatus == "Cargado":
                                        st.success(f"✅ Archivo en la nube ({doc_ev.fecha_actualizacion.strftime('%Y-%m-%d')})")
                                    else:
                                        st.warning("⚠️ Pendiente de carga")
                                        
                                with col_ev2:
                                    if not doc_ev or doc_ev.estatus != "Cargado":
                                        archivo_ev = st.file_uploader("Subir Archivo (.pdf, .jpg, .png)", type=["pdf", "jpg", "jpeg", "png"], key=f"up_ev_{part.id}_{ev.id}", label_visibility="collapsed")
                                        if archivo_ev:
                                            if st.button("Guardar Evidencia", key=f"btn_ev_{part.id}_{ev.id}"):
                                                timestamp = int(datetime.datetime.now().timestamp())
                                                proy_limpio = limpiar_nombre_archivo(part.proyecto.nombre)
                                                nombre_limpio = limpiar_nombre_archivo(ev.nombre_evidencia)
                                                pers_limpio = limpiar_nombre_archivo(part.persona.razon_social_nombre)
                                                extension = os.path.splitext(archivo_ev.name)[1].lower()
                                                
                                                ruta_ev = f"evidencias/{proy_limpio}-{pers_limpio}-{nombre_limpio}-{timestamp}{extension}"
                                                
                                                try:
                                                    supabase_client.storage.from_("expedientes").upload(
                                                        file=archivo_ev.getvalue(),
                                                        path=ruta_ev,
                                                        file_options={"content-type": archivo_ev.type, "x-upsert": "true"}
                                                    )
                                                    
                                                    if not doc_ev:
                                                        nuevo_ev = DocumentoExpediente(
                                                            participacion_id=part.id,
                                                            categoria_documento="Evidencia_Adjunta",
                                                            tipo_documento=ev.nombre_evidencia,
                                                            estatus="Cargado",
                                                            ruta_archivo=ruta_ev
                                                        )
                                                        db.add(nuevo_ev)
                                                    else:
                                                        doc_ev.estatus = "Cargado"
                                                        doc_ev.ruta_archivo = ruta_ev
                                                    db.commit()
                                                    st.rerun()
                                                except Exception as e:
                                                    st.error(f"Error subiendo evidencia: {e}")
                        
        else:
            st.warning("Aún no tienes entidades asignadas. Contacta al Administrador.")
        
        db.close()

def main():
    if 'autenticado' not in st.session_state:
        st.session_state['autenticado'] = False

    if not st.session_state['autenticado']:
        login_y_otp()
    else:
        dashboard_principal()

if __name__ == "__main__":
    main()
