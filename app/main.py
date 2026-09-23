#$2b$12$f2GbKgrT6kOKtda1vu/Qhe7XS1iZtsFRh5GLvJGf8ZddXPbEDXe0a - Temporal123!
#$2b$12$l.9uoOyt/Pnx4JO5Pc2lVeiMyj7EI.U83XZc9WnS31UMPn8TXAeFq - 123456
#$2b$12$jVIBaDCx7bOzPNs/piM26.lzjtLSLi3c9RZuD0LcFlUJPID0x2fF. - ???

import sys
import os
import io
import zipfile
import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import(
    SessionLocal, Usuario, Proyecto, Persona,
    Catalogo, Participacion, JerarquiaParticipacion, DocumentoExpediente,
    PlantillaFormato, supabase_client
)

from app.utils.auth import verificar_password, generar_hash

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
        tabs = st.tabs(["📊 Tablero de Control", "📄 Plantillas", "📁 Proyectos",
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
                
                st.dataframe(df_tablero.style.map(color_estatus, subset=['Estatus Documental']), hide_index=True, use_container_width=True)

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
                        
                        col_a, col_b, col_c = st.columns([2, 1, 1])
                        with col_a:
                            nuevos_roles = st.multiselect("Modificar Roles", options=roles_disponibles, default=tpl.roles_aplica, key=f"roles_{tpl.id}")
                        with col_b:
                            nueva_pag = st.number_input("Modificar Páginas", min_value=1, value=tpl.paginas_totales, key=f"pags_{tpl.id}")
                        with col_c:
                            st.write("") 
                            st.write("")
                            if st.button("💾 Guardar Cambios", key=f"btn_save_{tpl.id}"):
                                tpl.roles_aplica = nuevos_roles
                                tpl.paginas_totales = nueva_pag
                                tpl.firmas_json = df_editado.to_dict(orient="records")
                                db.commit()
                                st.success("Configuración actualizada.")
                                st.rerun()
            db.close()
            
        # --- GESTIÓN DE PROYECTOS ---
        with tabs[2]:
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
        with tabs[3]:
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
        with tabs[4]:
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
        with tabs[5]:
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
        with tabs[6]:
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
                        
                        # --- FORMULARIO FLEXIBLE ---
                        st.caption("Complete los datos requeridos para generar los formatos.")
                        datos_actuales = part.persona.datos_json or {}
                        
                        with st.form(f"form_datos_{part.id}"):
                            col1, col2 = st.columns(2)
                            direccion = col1.text_input("Dirección Fiscal", value=datos_actuales.get("direccion", ""))
                            telefono = col2.text_input("Teléfono", value=datos_actuales.get("telefono", ""))
                            
                            if part.persona.tipo == "Moral":
                                fecha_const = col1.text_input("Fecha de Constitución", value=datos_actuales.get("fecha_const", ""))
                                notario = col2.text_input("Notario Público", value=datos_actuales.get("notario", ""))
                                nuevos_datos = {"direccion": direccion, "telefono": telefono, "fecha_const": fecha_const, "notario": notario}
                            else:
                                curp = col1.text_input("CURP", value=datos_actuales.get("curp", ""))
                                edo_civil = col2.selectbox("Estado Civil", ["Soltero", "Casado", "Otro"], index=["Soltero", "Casado", "Otro"].index(datos_actuales.get("estado_civil", "Soltero")) if datos_actuales.get("estado_civil") in ["Soltero", "Casado", "Otro"] else 0)
                                nuevos_datos = {"direccion": direccion, "telefono": telefono, "curp": curp, "estado_civil": edo_civil}
                                
                            if st.form_submit_button("Guardar Datos"):
                                part.persona.datos_json = nuevos_datos
                                db.commit()
                                st.success("Datos guardados en el expediente.")
                                st.rerun()

                        # --- GENERACIÓN DE PAQUETE ZIP E INSTRUCCIONES ---
                        st.divider()
                        st.write("📄 **Gestión del Paquete Documental**")
                        
                        doc_exp = db.query(DocumentoExpediente).filter_by(
                            participacion_id=part.id, 
                            tipo_documento="Paquete Unificado"
                        ).first()
                        
                        # Obtenemos las plantillas que aplican a este rol (Filtrado seguro en memoria)
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
                                if st.button(f"Generar Paquete (.zip)", key=f"btn_gen_{part.id}"):
                                    context = {"nombre": part.persona.razon_social_nombre, "rfc": part.persona.rfc or "", **datos_actuales}
                                    
                                    # 1. Crear el ZIP en memoria consultando Supabase
                                    zip_buffer = io.BytesIO()
                                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                                        for tpl in plantillas_aplicables:
                                            if tpl.ruta_plantilla_word:
                                                extension = os.path.splitext(tpl.ruta_plantilla_word)[1].lower()
                                                try:
                                                    # Descargar de la nube directo a la memoria RAM (0 uso de disco)
                                                    archivo_bytes = supabase_client.storage.from_("expedientes").download(tpl.ruta_plantilla_word)
                                                    
                                                    if extension == ".docx":
                                                        doc = DocxTemplate(io.BytesIO(archivo_bytes))
                                                        doc.render(context)
                                                        doc_io = io.BytesIO()
                                                        doc.save(doc_io)
                                                        zip_file.writestr(f"{tpl.nombre}.docx", doc_io.getvalue())
                                                    else:
                                                        zip_file.writestr(f"{tpl.nombre}{extension}", archivo_bytes)
                                                except Exception as e:
                                                    st.error(f"No se pudo anexar '{tpl.nombre}': Archivo no encontrado en la nube.")
                                    
                                    zip_buffer.seek(0)
                                    st.session_state[f'zip_bytes_{part.id}'] = zip_buffer.getvalue()
                                    
                                    # 2. Trazabilidad
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

                                # Mostrar botón de descarga del ZIP
                                if doc_exp or f'zip_bytes_{part.id}' in st.session_state:
                                    if f'zip_bytes_{part.id}' in st.session_state:
                                        st.download_button(
                                            label="⬇️ 1. Descargar Paquete (.zip)",
                                            data=st.session_state[f'zip_bytes_{part.id}'],
                                            file_name=f"Paquete_{part.persona.razon_social_nombre.replace(' ', '_')}.zip",
                                            mime="application/zip",
                                            key=f"dl_{part.id}"
                                        )
                                    else:
                                        st.info("Por favor, vuelve a dar clic en 'Generar Paquete' para cargar el archivo en memoria.")
                                        
                        with col_der:
                            # Carga del PDF escaneado
                            archivo_subido = st.file_uploader("⬆️ 3. Subir Paquete Firmado (.pdf)", type=["pdf"], key=f"up_{part.id}")
                            if archivo_subido is not None:
                                if st.button("Confirmar Entrega de Documento", key=f"btn_up_{part.id}"):
                                    nombre_limpio = part.persona.razon_social_nombre.replace(' ', '_')
                                    ruta_pdf = f"firmados/{part.id}_Firmado_{nombre_limpio}.pdf"
                                    
                                    try:
                                        # Subir a la bóveda privada de Supabase
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

                        # Mostrar Instrucciones Actualizadas
                        if doc_exp and plantillas_aplicables:
                            st.markdown("### 📋 Instrucciones de Firma")
                            st.write("2. Extraiga el contenido del ZIP. Firme cada documento según la siguiente tabla:")
                            
                            filas_tabla = []
                            total_firmas_paquete = 0
                            
                            for formato in plantillas_aplicables:
                                firmas = formato.firmas_json or []
                                num_firmas = len(firmas)
                                total_firmas_paquete += num_firmas
                                
                                for i, firma in enumerate(firmas):
                                    filas_tabla.append({
                                        "Documento": formato.nombre if i == 0 else "",
                                        "Núm. Firmas": num_firmas if i == 0 else "",
                                        "Página a Firmar": firma.get("pag_formato", ""),
                                        "Tipo de Firma": firma.get("tipo_firma", ""),
                                        "Rubricar todas": formato.rubricar_todas if i == 0 else ""
                                    })
                                
                                if num_firmas == 0:
                                    filas_tabla.append({
                                        "Documento": formato.nombre,
                                        "Núm. Firmas": 0,
                                        "Página a Firmar": "-",
                                        "Tipo de Firma": "-",
                                        "Rubricar todas": formato.rubricar_todas
                                    })
                                    
                            filas_tabla.append({
                                "Documento": "TOTAL",
                                "Núm. Firmas": f"**{total_firmas_paquete}**",
                                "Página a Firmar": "",
                                "Tipo de Firma": "",
                                "Rubricar todas": ""
                            })
                            
                            st.markdown(pd.DataFrame(filas_tabla).style.hide(axis="index").to_html(), unsafe_allow_html=True)
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