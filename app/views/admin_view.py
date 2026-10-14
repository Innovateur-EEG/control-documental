import streamlit as st
import pandas as pd
from app.models.database import Usuario, Proyecto, Persona, Catalogo, Participacion, JerarquiaParticipacion, DocumentoExpediente, PlantillaFormato, ConfiguracionCampos, ConfiguracionEvidencia, UsuarioPersonaGestor, supabase_client
from app.utils.auth import generar_hash
from sqlalchemy.orm.attributes import flag_modified

def render_admin(db, user_actual, is_super, tab_tablero, tab_config, mis_proyectos, mis_proy_ids):
    # =========================================================
    # --- TABLERO DE AVANCE ---
    # =========================================================
    with tab_tablero:
        st.subheader("Tablero de Avance Documental")
        st.write("Monitoreo en tiempo real del estado de los expedientes por proyecto.")
        
        
        
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

    # =========================================================
    # --- GESTOR DINÁMICO DE PLANTILLAS ---
    # =========================================================
    with tab_config:
        if is_super:
            sub_proy, sub_estruc, sub_plantillas, sub_vars, sub_cats = st.tabs([
                "📁 Proyectos", "👥 Estructura y Accesos", "📄 Plantillas", "📝 Variables y Evidencias", "📚 Catálogos"
            ])
        else:
            sub_proy, sub_estruc = st.tabs([
                "📁 Proyectos", "👥 Estructura y Accesos"
            ])
        
        # =========================================================
        # --- GESTIÓN DE PROYECTOS ---
        # =========================================================
        with sub_proy:
            st.subheader("Gestión de Proyectos")
            st.caption("SuperAdmin: edite celdas, agregue proyectos con el botón `+` o asigne administradores separando correos con comas. Admin: modifique únicamente el estatus entre Activo y Pausado.")
            
            proyectos_lista = db.query(Proyecto).all() if is_super else mis_proyectos
            
            datos_p = []
            for p in proyectos_lista:
                admins_str = ", ".join([a.email for a in p.admins]) if p.admins else ""
                datos_p.append({
                    "ID": p.id,
                    "Nombre": p.nombre,
                    "Estatus": p.estatus_general,
                    "Administradores": admins_str
                })
                
            df_p = pd.DataFrame(datos_p) if datos_p else pd.DataFrame(columns=["ID", "Nombre", "Estatus", "Administradores"])
            
            # Permisos de edición por columna
            if is_super:
                cols_bloqueadas = ["ID"]
                num_filas = "dynamic" # Permite agregar nuevas líneas con '+'
                opciones_estatus = ["Activo", "Pausado", "Concluido"]
            else:
                # Admin: solo puede editar la columna 'Estatus', y solo entre Activo y Pausado
                cols_bloqueadas = ["ID", "Nombre", "Administradores"]
                num_filas = "fixed"
                opciones_estatus = ["Activo", "Pausado"]
                
            df_p_edit = st.data_editor(
                df_p,
                num_rows=num_filas,
                hide_index=True,
                use_container_width=True,
                disabled=cols_bloqueadas,
                column_config={
                    "Estatus": st.column_config.SelectboxColumn("Estatus", options=opciones_estatus, required=True),
                    "Administradores": st.column_config.TextColumn("Administradores (Correos separados por coma)")
                },
                key="editor_proyectos_unificado"
            )
            
            if st.button("💾 Guardar Cambios en Proyectos", key="btn_save_proy_inline"):
                ids_procesados = set()
                
                for _, row in df_p_edit.iterrows():
                    val_id = row.get("ID")
                    nombre_p = row.get("Nombre")
                    estatus_p = row.get("Estatus")
                    admins_raw = row.get("Administradores")
                    
                    if pd.notna(nombre_p) and str(nombre_p).strip():
                        if pd.notna(val_id) and int(val_id) > 0:
                            # Modificar existente
                            proy_obj = db.query(Proyecto).filter(Proyecto.id == int(val_id)).first()
                            if proy_obj:
                                if is_super:
                                    proy_obj.nombre = str(nombre_p).strip()
                                proy_obj.estatus_general = estatus_p
                                
                                # Procesar administradores (Solo SuperAdmin)
                                if is_super and pd.notna(admins_raw):
                                    lista_correos = [c.strip().lower() for c in str(admins_raw).split(",") if c.strip()]
                                    admins_encontrados = db.query(Usuario).filter(Usuario.email.in_(lista_correos), Usuario.tipo_usuario.in_(["Admin", "SuperAdmin"])).all()
                                    proy_obj.admins = admins_encontrados
                                    
                                ids_procesados.add(proy_obj.id)
                        else:
                            # Alta en nueva línea (Solo SuperAdmin)
                            if is_super:
                                nuevo_proy = Proyecto(nombre=str(nombre_p).strip(), estatus_general=estatus_p or "Activo")
                                if pd.notna(admins_raw):
                                    lista_correos = [c.strip().lower() for c in str(admins_raw).split(",") if c.strip()]
                                    admins_encontrados = db.query(Usuario).filter(Usuario.email.in_(lista_correos), Usuario.tipo_usuario.in_(["Admin", "SuperAdmin"])).all()
                                    nuevo_proy.admins = admins_encontrados
                                db.add(nuevo_proy)
                                db.commit()
                                ids_procesados.add(nuevo_proy.id)
                                
                db.commit()
                st.success("Proyectos guardados exitosamente.")
                st.rerun()

        # =========================================================
        # --- ESTRUCTURA Y ACCESOS---
        # =========================================================
        with sub_estruc:
            st.subheader("Estructura Corporativa, Jerarquías y Accesos Web")
            st.write("Visualice el árbol jerárquico, gestione dependencias y administre permisos de acceso.")
            
            if not mis_proyectos:
                st.info("No hay proyectos disponibles.")
            else:
                proy_dict = {p.id: p.nombre for p in mis_proyectos}
                # 1. Filtro superior con opción 'Todos'
                opciones_proy = {"todos": "🌐 Todos los proyectos asignados"}
                opciones_proy.update(proy_dict)
                
                proy_sel = st.selectbox(
                    "Seleccione el Proyecto a visualizar:", 
                    options=list(opciones_proy.keys()), 
                    format_func=lambda x: opciones_proy[x], 
                    key="sel_proy_filtro"
                )
                
                proyectos_activos = mis_proyectos if proy_sel == "todos" else [p for p in mis_proyectos if p.id == proy_sel]
                roles_disponibles = [c.valor for c in db.query(Catalogo).filter_by(categoria="Rol_Participacion").all()]
                relaciones_disponibles = [c.valor for c in db.query(Catalogo).filter_by(categoria="Tipo_Relacion").all()]
                
                # 2. Construcción del Árbol (soporta 1 o N proyectos)
                filas_arbol = []
                parts_dict = {}
                
                for proy in proyectos_activos:
                    parts_proy = db.query(Participacion).filter(Participacion.proyecto_id == proy.id).all()
                    for p in parts_proy: parts_dict[p.id] = p
                    
                    jerarquias = db.query(JerarquiaParticipacion).filter(
                        JerarquiaParticipacion.padre_id.in_([p.id for p in parts_proy])
                    ).all()
                    
                    hijos_map = {}
                    hijos_ids_set = set()
                    for j in jerarquias:
                        if j.hijo_id in parts_dict:
                            hijos_map.setdefault(j.padre_id, []).append((parts_dict[j.hijo_id], j.tipo_relacion))
                            hijos_ids_set.add(j.hijo_id)
                            
                    raices = [p for p in parts_proy if p.id not in hijos_ids_set]
                    visitados = set()
                    
                    def recorrer(part, nivel=0, prefijo="", gestores_padre_dict=None):
                        if part.id in visitados: return
                        visitados.add(part.id)
                        
                        tipo_raw = str(part.persona.tipo or "").strip().lower()
                        tipo_limpio = "Moral" if "moral" in tipo_raw else "Fisica"
                        
                        icono = "🏢 " if tipo_limpio == "Moral" else "👤 "
                        indent = "    " * nivel
                        arbol_visual = f"{indent}{prefijo}{icono}{part.persona.razon_social_nombre}"
                        
                        # --- LECTURA SEGURA DE PERMISOS DESDE SQL ---
                        gestores_propios = part.persona.usuarios_asignados
                        
                        if gestores_propios:
                            gestores_actuales = {a.usuario.email: a.nivel_permiso for a in gestores_propios}
                            textos_usr = [f"{mail}*" if perm == "Solo Lectura" else mail for mail, perm in gestores_actuales.items()]
                            status_usr = ", ".join(textos_usr)
                        elif gestores_padre_dict:
                            gestores_actuales = gestores_padre_dict
                            textos_usr = [f"{mail}*" if perm == "Solo Lectura" else mail for mail, perm in gestores_actuales.items()]
                            status_usr = "↳ Hereda: " + ", ".join(textos_usr)
                        else:
                            gestores_actuales = {}
                            status_usr = "No asignado"
                        
                        filas_arbol.append({
                            "Sel": False,
                            "ID_Part": part.id,
                            "ID_Persona": part.persona.id,
                            "Proyecto": proy.nombre,
                            "Estructura / Jerarquía": arbol_visual,
                            "Tipo": tipo_limpio,
                            "RFC": part.persona.rfc or "",
                            "Rol": part.rol,
                            "Usuario y Permisos": status_usr,
                            "_nombre_puro": part.persona.razon_social_nombre,
                            "_proy_id": proy.id
                        })
                        
                        hijos = hijos_map.get(part.id, [])
                        for idx, (h_part, rel) in enumerate(hijos):
                            simbolo = "└── " if idx == len(hijos) - 1 else "├── "
                            recorrer(h_part, nivel + 1, simbolo, gestores_padre_dict=gestores_actuales)
                            
                    for r in raices: recorrer(r)
                    for p in parts_proy:
                        if p.id not in visitados: recorrer(p, nivel=0, prefijo="⚠️ ")

                # 3. Renderizar Tabla Árbol
                if filas_arbol:
                    df_arbol = pd.DataFrame(filas_arbol)
                    cols_mostrar = ["Sel", "ID_Part", "Proyecto", "Estructura / Jerarquía", "Tipo", "RFC", "Rol", "Usuario y Permisos"] if proy_sel == "todos" else ["Sel", "ID_Part", "Estructura / Jerarquía", "Tipo", "RFC", "Rol", "Usuario y Permisos"]
                    
                    df_edit = st.data_editor(
                        df_arbol[cols_mostrar],
                        hide_index=True,
                        use_container_width=True,
                        disabled=[c for c in cols_mostrar if c != "Sel"],
                        column_config={
                            "Sel": st.column_config.CheckboxColumn("Seleccionar", default=False),
                            "ID_Part": None
                        },
                        key=f"editor_arbol_{proy_sel}"
                    )
                    st.caption("*(Nota: Los usuarios marcados con un asterisco `*` tienen permisos de Solo Lectura).*")
                    
                    seleccionados = df_edit[df_edit["Sel"] == True]
                    
                    if not seleccionados.empty:
                        st.divider()
                        ids_part_sel = seleccionados["ID_Part"].tolist()
                        parts_objs_sel = [parts_dict[pid] for pid in ids_part_sel if pid in parts_dict]
                        
                        col_acc1, col_acc2 = st.columns(2)
                        
                        with col_acc1:
                            with st.expander("🔗 Gestionar Jerarquía / Dependencia", expanded=False):
                                proy_de_sel = parts_objs_sel[0].proyecto_id
                                pad_candidatos = {p.id: f"{p.persona.razon_social_nombre} ({p.rol})" for p in parts_dict.values() if p.proyecto_id == proy_de_sel and p.id not in ids_part_sel}
                                
                                if pad_candidatos:
                                    pad_id = st.selectbox("Subordinar bajo:", options=list(pad_candidatos.keys()), format_func=lambda x: pad_candidatos[x], key="pad_sub_sel")
                                    rel_tipo = st.selectbox("Tipo de relación:", options=relaciones_disponibles if relaciones_disponibles else ["Representa a", "Es socio de"], key="rel_sub_sel")
                                    
                                    if st.button("Establecer Dependencia"):
                                        for h_id in ids_part_sel:
                                            db.query(JerarquiaParticipacion).filter(JerarquiaParticipacion.hijo_id == h_id).delete()
                                            db.add(JerarquiaParticipacion(padre_id=pad_id, hijo_id=h_id, tipo_relacion=rel_tipo))
                                        db.commit()
                                        st.rerun()
                                st.write("---")
                                if st.button("❌ Quitar Dependencia (Hacer Raíz)"):
                                    for h_id in ids_part_sel:
                                        db.query(JerarquiaParticipacion).filter(JerarquiaParticipacion.hijo_id == h_id).delete()
                                    db.commit()
                                    st.rerun()
                                    
                        with col_acc2:
                            with st.expander("👤 Asignar / Modificar Acceso Web", expanded=False):
                                usuarios_ops = db.query(Usuario).all()
                                usr_map = {u.id: f"{u.email} ({u.tipo_usuario})" for u in usuarios_ops}
                                
                                u_id = st.selectbox("Seleccione Usuario:", options=list(usr_map.keys()), format_func=lambda x: usr_map[x], key="usr_vinc_sel")
                                permiso_sel = st.selectbox("Nivel de permiso (Atómico):", ["Lectura y Escritura", "Solo Lectura"], key="perm_hijas_sel")
                                sobreescribir = st.checkbox("Reemplazar gestores anteriores", value=True)
                                
                                col_btn_asig, col_btn_desv = st.columns([1, 1])
                                with col_btn_asig:
                                    if st.button("Vincular / Reasignar", key="btn_asig_usr"):
                                        for p_obj in parts_objs_sel:
                                            pers = p_obj.persona
                                            if sobreescribir:
                                                db.query(UsuarioPersonaGestor).filter_by(persona_id=pers.id).delete()
                                                
                                            asig_existente = db.query(UsuarioPersonaGestor).filter_by(usuario_id=u_id, persona_id=pers.id).first()
                                            if asig_existente:
                                                asig_existente.nivel_permiso = permiso_sel
                                            else:
                                                db.add(UsuarioPersonaGestor(usuario_id=u_id, persona_id=pers.id, nivel_permiso=permiso_sel))
                                                
                                            # Limpieza de basura JSON legacy
                                            d_json = dict(pers.datos_json or {})
                                            d_json.pop("permisos_usuarios", None)
                                            d_json.pop("permiso_hijas", None)
                                            pers.datos_json = d_json
                                            
                                        db.commit()
                                        st.success("Acceso y permisos actualizados.")
                                        st.rerun()
                                        
                                with col_btn_desv:
                                    if st.button("❌ Quitar Acceso", key="btn_desv_usr"):
                                        for p_obj in parts_objs_sel:
                                            db.query(UsuarioPersonaGestor).filter_by(persona_id=p_obj.persona.id).delete()
                                            d_json = dict(p_obj.persona.datos_json or {})
                                            d_json.pop("permisos_usuarios", None)
                                            d_json.pop("permiso_hijas", None)
                                            p_obj.persona.datos_json = d_json
                                        db.commit()
                                        st.success("Accesos desvinculados.")
                                        st.rerun()

                    # 4. Formulario de Vinculación Rápida
                    st.divider()
                    with st.expander("➕ Vincular Persona / Entidad Existente al Proyecto", expanded=False):
                        if roles_disponibles:
                            with st.form("form_vinc_exist"):
                                proy_target = st.selectbox("Proyecto destino:", options=[p.id for p in proyectos_activos], format_func=lambda x: proy_dict.get(x, ""))
                                p_catalogo = db.query(Persona).all()
                                p_id_vinc = st.selectbox("Persona:", options=[p.id for p in p_catalogo], format_func=lambda x: next(f"{p.razon_social_nombre} ({p.tipo})" for p in p_catalogo if p.id == x))
                                r_vinc = st.selectbox("Rol:", options=roles_disponibles)
                                if st.form_submit_button("Vincular al Proyecto"):
                                    if not db.query(Participacion).filter_by(proyecto_id=proy_target, persona_id=p_id_vinc).first():
                                        db.add(Participacion(proyecto_id=proy_target, persona_id=p_id_vinc, rol=r_vinc))
                                        db.commit()
                                        st.rerun()
                                    else:
                                        st.warning("Esta persona ya está en ese proyecto.")
                # =================================================================
                # NUEVA SECCIÓN: CATÁLOGO DE PERSONAS (Editable con agregaciones)
                # =================================================================
                st.divider()
                st.markdown("### 👥 Catálogo Maestro de Entidades y Personas")
                
                personas_query = db.query(Persona).all() if is_super else db.query(Persona).join(Participacion).filter(Participacion.proyecto_id.in_(mis_proy_ids)).distinct().all()
                
                datos_pers = []
                for p in personas_query:
                    p_parts = p.participaciones
                    proys_str = ", ".join(list(set([part.proyecto.nombre for part in p_parts])))
                    roles_str = ", ".join(list(set([part.rol for part in p_parts])))
                    
                    admins_asig = [a.usuario.email for a in p.usuarios_asignados if a.usuario.tipo_usuario in ["Admin", "SuperAdmin"]]
                    users_asig = [a.usuario.email for a in p.usuarios_asignados if a.usuario.tipo_usuario == "Usuario"]
                    
                    datos_pers.append({
                        "Sel": False,
                        "ID": p.id,
                        "Nombre o Razón Social": p.razon_social_nombre,
                        "RFC": p.rfc or "",
                        "Tipo": p.tipo,
                        "Proyectos": proys_str,
                        "Roles": roles_str,
                        "Administrador": ", ".join(admins_asig) if admins_asig else "",
                        "Usuario": ", ".join(users_asig) if users_asig else ""
                    })
                    
                df_pers = pd.DataFrame(datos_pers) if datos_pers else pd.DataFrame(columns=["Sel", "ID", "Nombre o Razón Social", "RFC", "Tipo", "Proyectos", "Roles", "Administrador", "Usuario"])
                
                # Edición de catálogos
                cols_pers_readonly = ["ID", "Proyectos", "Roles", "Administrador", "Usuario"]
                df_pers_edit = st.data_editor(
                    df_pers,
                    hide_index=True,
                    use_container_width=True,
                    disabled=cols_pers_readonly,
                    column_config={
                        "Sel": st.column_config.CheckboxColumn("Seleccionar", default=False),
                        "ID": None,
                        "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Moral", "Fisica"])
                    },
                    key="editor_personas_master"
                )
                
                col_pbtn1, col_pbtn2 = st.columns([1, 1])
                with col_pbtn1:
                    if st.button("💾 Guardar Cambios en Catálogo", key="btn_save_pers_cat"):
                        for _, row in df_pers_edit.iterrows():
                            p_obj = db.query(Persona).filter(Persona.id == row["ID"]).first()
                            if p_obj:
                                p_obj.razon_social_nombre = row["Nombre o Razón Social"]
                                p_obj.rfc = row["RFC"]
                                p_obj.tipo = row["Tipo"]
                        db.commit()
                        st.success("Catálogo actualizado.")
                        st.rerun()
                        
                with col_pbtn2:
                    pers_sel_df = df_pers_edit[df_pers_edit["Sel"] == True]
                    if not pers_sel_df.empty:
                        if st.button("🗑️ Eliminar Entidades Seleccionadas", type="primary"):
                            for pid in pers_sel_df["ID"].tolist():
                                p_obj = db.query(Persona).filter(Persona.id == pid).first()
                                if p_obj:
                                    # Borrado en cascada manual por seguridad
                                    for part in p_obj.participaciones:
                                        db.query(DocumentoExpediente).filter(DocumentoExpediente.participacion_id == part.id).delete()
                                        db.query(JerarquiaParticipacion).filter((JerarquiaParticipacion.padre_id == part.id) | (JerarquiaParticipacion.hijo_id == part.id)).delete()
                                        db.delete(part)
                                    p_obj.gestores = []
                                    db.delete(p_obj)
                            db.commit()
                            st.success("Entidades y sus relaciones eliminadas exitosamente.")
                            st.rerun()
                            
                with st.expander("➕ Alta Rápida en Catálogo (Sin asignar a proyecto)", expanded=False):
                    with st.form("form_alta_catalogo_puro"):
                        c_t1, c_t2 = st.columns(2)
                        t_p = c_t1.selectbox("Tipo", ["Moral", "Fisica"])
                        r_p = c_t2.text_input("RFC (Opcional)")
                        nom_p = st.text_input("Nombre o Razón Social")
                        if st.form_submit_button("Agregar al Catálogo Maestro") and nom_p:
                            db.add(Persona(tipo=t_p, rfc=r_p, razon_social_nombre=nom_p))
                            db.commit()
                            st.rerun()

                # =================================================================
                # NUEVA SECCIÓN: DIRECTORIO DE USUARIOS (Editable)
                # =================================================================
                st.divider()
                st.markdown("### 🔑 Directorio de Usuarios y Accesos")
                st.write("Agregue nuevos usuarios en una fila vacía con el botón `+`, edite los existentes o seleccione casillas para eliminar / restablecer contraseña.")
                
                usuarios_lista = db.query(Usuario).order_by(Usuario.email).all()
                datos_usr = []
                for u in usuarios_lista:
                    estatus_pwd = "⚠️ Temporal" if u.debe_cambiar_password == 1 else "✅ Activa"
                    datos_usr.append({
                        "Sel": False,
                        "ID": u.id,
                        "Correo": u.email,
                        "Teléfono": u.telefono or "",
                        "Estatus Contraseña": estatus_pwd,
                        "Rol": u.tipo_usuario
                    })
                    
                df_usr = pd.DataFrame(datos_usr) if datos_usr else pd.DataFrame(columns=["Sel", "ID", "Correo", "Teléfono", "Estatus Contraseña", "Rol"])
                
                # Para permitir inline-creation, el correo no debe estar en la lista de bloqueados
                cols_usr_readonly = ["ID", "Estatus Contraseña"]
                if not is_super:
                    cols_usr_readonly.append("Rol")
                    
                df_usr_edit = st.data_editor(
                    df_usr,
                    num_rows="dynamic", # Habilita agregar filas con '+'
                    hide_index=True,
                    use_container_width=True,
                    disabled=cols_usr_readonly,
                    column_config={
                        "Sel": st.column_config.CheckboxColumn("Seleccionar", default=False),
                        "ID": None,
                        "Correo": st.column_config.TextColumn("Correo (Editable)", required=True),
                        "Rol": st.column_config.SelectboxColumn("Rol", options=["Usuario", "Admin", "SuperAdmin"], default="Usuario")
                    },
                    key="editor_usuarios_dir"
                )
                
                col_ubtn1, col_ubtn2 = st.columns([1, 1])
                with col_ubtn1:
                    if st.button("💾 Guardar Cambios en Usuarios", key="btn_save_usrs"):
                        for _, row in df_usr_edit.iterrows():
                            val_id = row.get("ID")
                            correo_u = str(row.get("Correo")).strip().lower()
                            tel_u = row.get("Teléfono")
                            rol_u = row.get("Rol") if pd.notna(row.get("Rol")) else "Usuario"
                            
                            if correo_u and correo_u != "nan":
                                if pd.notna(val_id) and str(val_id).strip() != "":
                                    # --- ACTUALIZAR EXISTENTE ---
                                    u_obj = db.query(Usuario).filter(Usuario.id == int(val_id)).first()
                                    if u_obj:
                                        # Actualizar correo solo si no choca con otro existente
                                        if u_obj.email != correo_u:
                                            if not db.query(Usuario).filter(Usuario.email == correo_u).first():
                                                u_obj.email = correo_u
                                        u_obj.telefono = tel_u
                                        if is_super:
                                            u_obj.tipo_usuario = rol_u
                                else:
                                    # --- CREAR NUEVO (Inline) ---
                                    if not db.query(Usuario).filter(Usuario.email == correo_u).first():
                                        nuevo_u = Usuario(
                                            email=correo_u,
                                            telefono=tel_u,
                                            password_hash=generar_hash("Temporal123!"),
                                            tipo_usuario=rol_u if is_super else "Usuario",
                                            debe_cambiar_password=1
                                        )
                                        db.add(nuevo_u)
                        db.commit()
                        st.success("Usuarios actualizados exitosamente.")
                        st.rerun()
                        
                with col_ubtn2:
                    usrs_sel_df = df_usr_edit[df_usr_edit["Sel"] == True]
                    if not usrs_sel_df.empty:
                        if st.button("🗑️ Eliminar Usuarios Seleccionados", type="primary"):
                            for uid in usrs_sel_df["ID"].tolist():
                                if pd.notna(uid):
                                    u_obj = db.query(Usuario).filter(Usuario.id == int(uid)).first()
                                    if u_obj:
                                        if u_obj.id == st.session_state['usuario_id']:
                                            st.error("No puedes eliminar tu propia sesión activa.")
                                            continue
                                            
                                        u_obj.proyectos_admin = []
                                        # Eliminamos las asignaciones de forma segura
                                        db.query(UsuarioPersonaGestor).filter_by(usuario_id=u_obj.id).delete()
                                        db.delete(u_obj)
                            db.commit()
                            st.success("Usuarios eliminados del sistema.")
                            st.rerun()
                            
                # Reset Masivo de Contraseñas
                if not usrs_sel_df.empty:
                    with st.expander(f"🔑 Restablecer Contraseña ({len(usrs_sel_df)} usuarios seleccionados)", expanded=True):
                        st.warning("Se sobrescribirá la contraseña actual. No olvide notificar a los usuarios.")
                        nueva_pwd_temp = st.text_input("Nueva contraseña temporal:", value="Temporal123!")
                        if st.button("Confirmar Restablecimiento Masivo", key="btn_reset_masivo_usr"):
                            for uid in usrs_sel_df["ID"].tolist():
                                if pd.notna(uid):
                                    u_obj = db.query(Usuario).filter(Usuario.id == int(uid)).first()
                                    if u_obj:
                                        u_obj.password_hash = generar_hash(nueva_pwd_temp)
                                        u_obj.debe_cambiar_password = 1
                            db.commit()
                            st.success("Contraseñas actualizadas.")
                            st.rerun()
        
        if is_super:
            # =========================================================
            # -- PLANTILLAS --
            # =========================================================
            with sub_plantillas:
            
                st.subheader("Gestor Dinámico de Plantillas")
                st.write("Configure los documentos individuales (Word/Excel), a quiénes aplican y dónde deben firmar.")
                
                
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
                                roles_validos = [r for r in (tpl.roles_aplica or []) if r in roles_disponibles]
                                nuevos_roles = st.multiselect("Modificar Roles", options=roles_disponibles, default=roles_validos, key=f"roles_{tpl.id}")
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
            
            # =========================================================
            # --- GESTOR DE CAMPOS Y EVIDENCIAS ---
            # =========================================================
            with sub_vars:
                st.subheader("Configuración de Variables y Evidencias")
                st.write("Defina qué información (texto) y qué archivos (PDFs/Imágenes) se solicitarán dinámicamente a los usuarios.")
                
                
                roles_disponibles = [c.valor for c in db.query(Catalogo).filter_by(categoria="Rol_Participacion").all()]
                
                col_izq, col_der = st.columns(2)
                
                with col_izq:
                    st.markdown("### 1️⃣ Campos de Texto (Variables)")
                    with st.expander("➕ Crear Nuevo Campo Obligatorio"):
                        with st.form("form_nuevo_campo_dinamico"):
                            nombre = st.text_input("Nombre a mostrar (Ej. CURP)")
                            llave = st.text_input("Variable Jinja (Ej. curp)")
                            tipo_input = st.selectbox("Tipo de Dato", ["Texto", "Fecha", "Número", "Opciones", "Selección única", "Selección múltiple", "Casilla"])
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
                

                # --- GESTOR DE CAMPOS Y VALIDACIONES ---
                st.subheader("Configuración de Campos y Validaciones")
                st.write("Defina qué información se solicitará a los usuarios en el portal, la etiqueta Jinja que la vinculará a Word/Excel, y si requiere pasar por una regla matemática.")
                
                roles_disponibles = [c.valor for c in db.query(Catalogo).filter_by(categoria="Rol_Participacion").all()]
                
                with st.expander("➕ Crear Nuevo Campo Obligatorio"):
                    with st.form("form_nuevo_campo"):
                        col1, col2 = st.columns(2)
                        nombre = col1.text_input("Nombre a mostrar en formulario (Ej. Fecha de Comprobante)")
                        llave = col2.text_input("Variable en Plantilla (Ej. fecha_comprobante)")
                        
                        col3, col4 = st.columns(2)
                        tipo_input = col3.selectbox("Tipo de Dato (Input)", ["Texto", "Fecha", "Número", "Opciones", "Selección única", "Selección múltiple", "Casilla"])
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
            
            # =========================================================
            # --- VARIABLES DE SISTEMA ---
            # =========================================================
            with sub_cats: 
                st.subheader("Configuración de Catálogos del Sistema")
                st.write("Edite directamente los valores, use el botón `+` en la tabla para agregar nuevos, o seleccione filas y presione Supr/Delete para eliminarlas.")
                
                
                catalogos = db.query(Catalogo).all()
                
                df_cat = pd.DataFrame([{"ID": c.id, "Categoría": c.categoria, "Valor": c.valor} for c in catalogos]) if catalogos else pd.DataFrame(columns=["ID", "Categoría", "Valor"])
                
                df_cat_edit = st.data_editor(
                    df_cat,
                    num_rows="dynamic",
                    hide_index=True,
                    use_container_width=True,
                    disabled=["ID"],
                    column_config={
                        "Categoría": st.column_config.SelectboxColumn("Categoría", options=["Rol_Participacion", "Tipo_Relacion"], required=True),
                        "Valor": st.column_config.TextColumn("Valor del Catálogo", required=True)
                    },
                    key="editor_catalogos_dinamico"
                )
                
                if st.button("💾 Guardar Cambios en Catálogos"):
                    # Identificar IDs presentes en la tabla editada
                    ids_mantenidos = set()
                    
                    for _, row in df_cat_edit.iterrows():
                        val_id = row.get("ID")
                        cat_nombre = row.get("Categoría")
                        cat_val = row.get("Valor")
                        
                        if pd.notna(cat_nombre) and pd.notna(cat_val) and str(cat_val).strip():
                            if pd.notna(val_id) and int(val_id) > 0:
                                # Registro existente: Actualizar
                                c_obj = db.query(Catalogo).filter(Catalogo.id == int(val_id)).first()
                                if c_obj:
                                    c_obj.categoria = cat_nombre
                                    c_obj.valor = str(cat_val).strip()
                                    ids_mantenidos.add(c_obj.id)
                            else:
                                # Registro nuevo (agregado con el botón +)
                                nuevo_c = Catalogo(categoria=cat_nombre, valor=str(cat_val).strip())
                                db.add(nuevo_c)
                                db.commit()
                                ids_mantenidos.add(nuevo_c.id)
                                
                    # Eliminar los que se borraron de la tabla visual
                    for c in catalogos:
                        if c.id not in ids_mantenidos:
                            db.delete(c)
                            
                    db.commit()
                    st.success("Catálogos actualizados correctamente.")
                    st.rerun()