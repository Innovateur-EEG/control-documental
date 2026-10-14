import os
import io
import zipfile
import datetime
import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from sqlalchemy.orm.attributes import flag_modified
from app.models.database import Participacion, JerarquiaParticipacion, DocumentoExpediente, PlantillaFormato, ConfiguracionCampos, ConfiguracionEvidencia, supabase_client
from app.utils.documentos import procesar_excel, procesar_word, convertir_a_pdf, fusionar_pdfs

def limpiar_nombre_archivo(nombre: str) -> str:
    import unicodedata, re
    if not nombre: return "sin_nombre"
    nombre = str(nombre)
    nombre = unicodedata.normalize('NFKD', nombre).encode('ASCII', 'ignore').decode('utf-8').lower()
    nombre = re.sub(r'[^\w\.-]', '_', nombre)
    nombre = re.sub(r'_+', '_', nombre)
    return nombre.strip('_')

def render_gestor(db, user_actual, tab_expedientes):
    with tab_expedientes:
        st.subheader("Expedientes Asignados")
        
        # --- SOLUCIÓN PUNTOS 1 y 4: Restaurar herencia ---
        personas_directas = [asig.persona for asig in user_actual.personas_asignadas] if user_actual else []
        personas_ids = [p.id for p in personas_directas]
        
        part_directas = db.query(Participacion).filter(Participacion.persona_id.in_(personas_ids)).all() if personas_ids else []
        part_directas_ids = [p.id for p in part_directas]
        
        # Buscar descendientes recursivamente
        jerarquias = db.query(JerarquiaParticipacion).all()
        hijos_rel_map = {}
        for j in jerarquias:
            hijos_rel_map.setdefault(j.padre_id, []).append(j.hijo_id)
            
        def obtener_desc(p_ids, visitados=None):
            if visitados is None: visitados = set()
            desc = set()
            for pid in p_ids:
                if pid in visitados: continue
                visitados.add(pid)
                for hid in hijos_rel_map.get(pid, []):
                    desc.add(hid)
                    desc.update(obtener_desc([hid], visitados))
            return desc
            
        hijas_ids = obtener_desc(part_directas_ids)
        part_hijas = db.query(Participacion).filter(Participacion.id.in_(hijas_ids)).all() if hijas_ids else []
        
        # UNIMOS AMBOS PARA LA VISTA DEL GESTOR
        todas_parts = {p.id: p for p in (part_directas + part_hijas)}.values()
        
        proy_map = {}
        for part_item in todas_parts:
            proy_map.setdefault(part_item.proyecto_id, {"nombre": part_item.proyecto.nombre, "parts": []})["parts"].append(part_item)
            
        if not proy_map:
            st.info("No tienes entidades asignadas a tu cargo actualmente.")
        else:
            col_sel1, col_sel2 = st.columns(2)
            proy_sel_id = col_sel1.selectbox("📁 Proyecto:", options=list(proy_map.keys()), format_func=lambda pid: proy_map[pid]["nombre"])
            participantes_disp = proy_map[proy_sel_id]["parts"]
            part_sel_id = col_sel2.selectbox("👤 Persona / Entidad:", options=[p.id for p in participantes_disp], format_func=lambda pid: next(f"{p.persona.razon_social_nombre} ({p.persona.tipo}) - Rol: {p.rol}" for p in participantes_disp if p.id == pid))
            part = next(p for p in participantes_disp if p.id == part_sel_id)
            
            # --- PERMISOS ATÓMICOS DESDE BD RELACIONAL ---
            if part.persona_id in personas_ids:
                # Permiso directo asignado
                asignacion = next((a for a in user_actual.personas_asignadas if a.persona_id == part.persona_id), None)
                permiso_actual = asignacion.nivel_permiso if asignacion else "Solo Lectura"
            else:
                # Heredado del padre
                padre_rel = db.query(JerarquiaParticipacion).filter(JerarquiaParticipacion.hijo_id == part.id).first()
                if padre_rel:
                    asignacion_padre = db.query(UsuarioPersonaGestor).filter_by(usuario_id=user_actual.id, persona_id=padre_rel.padre.persona_id).first()
                    permiso_actual = asignacion_padre.nivel_permiso if asignacion_padre else "Solo Lectura"
                else:
                    permiso_actual = "Solo Lectura" # Fail-secure: Por defecto bloqueado
                    
            es_solo_lectura = (permiso_actual == "Solo Lectura")
                
            st.divider()
            c_head1, c_head2 = st.columns([3, 1])
            c_head1.markdown(f"### Expediente: **{part.persona.razon_social_nombre}**")
            c_head1.caption(f"RFC: {part.persona.rfc or 'Sin RFC'} | Rol: {part.rol}")
            
            if es_solo_lectura:
                c_head2.warning("🔒 Solo Lectura")
            else:
                c_head2.success("✏️ Edición Completa")

            # --- SUB-PESTAÑAS DE EXPEDIENTE ---
            subtab_form, subtab_evid, subtab_paquete = st.tabs(["📝 Formulario de Captura", "📎 Evidencias Adjuntas", "📦 Paquete Documental"])
            
            # ==========================================
            # TAB 1: FORMULARIO DINÁMICO
            # ==========================================
            with subtab_form:
                if es_solo_lectura:
                    st.info("ℹ️ Modo Consulta: Los formularios están bloqueados.")
                    
                datos_actuales = part.persona.datos_json or {}
                todos_campos = db.query(ConfiguracionCampos).all()
                campos_aplicables = [c for c in todos_campos if c.tipo_persona in ["Ambas", part.persona.tipo] and (not c.roles_aplica or part.rol in c.roles_aplica)]
                
                if campos_aplicables:
                    # Configuration is metadata-driven. Conditional fields need reruns, so widgets
                    # are intentionally outside st.form and use stable keys.
                    def _field_config(field):
                        raw = getattr(field, "configuracion_json", None) or {}
                        return raw if isinstance(raw, dict) else {}

                    campos_ordenados = sorted(
                        campos_aplicables,
                        key=lambda field: (
                            str(_field_config(field).get("section") or "General"),
                            int(_field_config(field).get("order", 100) or 100),
                            field.id
                        )
                    )
                    campo_por_llave = {field.llave_jinja: field for field in campos_ordenados}
                    nuevos_datos = {}
                    columnas = st.columns(2)
                    seccion_actual = None
                    indice_columna = 0

                    for c in campos_ordenados:
                        config = _field_config(c)
                        seccion = str(config.get("section") or "General").strip() or "General"
                        if seccion != seccion_actual:
                            st.markdown(f"#### {seccion}")
                            seccion_actual = seccion
                            columnas = st.columns(2)
                            indice_columna = 0

                        condicion = config.get("visible_if")
                        if isinstance(condicion, dict) and condicion.get("field"):
                            clave_condicion = str(condicion["field"])
                            campo_cond = campo_por_llave.get(clave_condicion)
                            clave_widget_cond = f"field_{part.id}_{campo_cond.id}" if campo_cond else None
                            valor_condicion = st.session_state.get(
                                clave_widget_cond,
                                nuevos_datos.get(clave_condicion, datos_actuales.get(clave_condicion))
                            )
                            esperado = condicion.get("equals")
                            visible = esperado in valor_condicion if isinstance(valor_condicion, list) else valor_condicion == esperado
                            if not visible:
                                continue

                        col = columnas[indice_columna % 2]
                        indice_columna += 1
                        widget_key = f"field_{part.id}_{c.id}"
                        val_previo = st.session_state.get(widget_key, datos_actuales.get(c.llave_jinja, config.get("default")))
                        ayuda = str(config.get("help") or "") or None

                        with col:
                            tipo = c.tipo_input
                            opciones = c.opciones_json or []
                            mapa_opciones = config.get("options_map")
                            if isinstance(mapa_opciones, dict) and mapa_opciones.get("depends_on"):
                                clave_dep = str(mapa_opciones["depends_on"])
                                campo_dep = campo_por_llave.get(clave_dep)
                                clave_widget_dep = f"field_{part.id}_{campo_dep.id}" if campo_dep else None
                                valor_dep = st.session_state.get(
                                    clave_widget_dep,
                                    nuevos_datos.get(clave_dep, datos_actuales.get(clave_dep))
                                )
                                mapa = mapa_opciones.get("map") or {}
                                opciones = mapa.get(str(valor_dep), []) if isinstance(mapa, dict) else []

                            if tipo == "Texto":
                                nuevos_datos[c.llave_jinja] = st.text_input(c.nombre_mostrar, value=str(val_previo or ""), help=ayuda, disabled=es_solo_lectura, key=widget_key)
                            elif tipo == "Número":
                                try:
                                    val_num = float(val_previo) if val_previo not in (None, "") else 0.0
                                except (TypeError, ValueError):
                                    val_num = 0.0
                                nuevos_datos[c.llave_jinja] = st.number_input(c.nombre_mostrar, value=val_num, help=ayuda, disabled=es_solo_lectura, key=widget_key)
                            elif tipo in ("Opciones", "Selección única"):
                                if not opciones:
                                    st.warning(f"'{c.nombre_mostrar}' no tiene opciones disponibles para la selección actual.")
                                    nuevos_datos[c.llave_jinja] = val_previo
                                else:
                                    if widget_key in st.session_state and st.session_state[widget_key] not in opciones:
                                        st.session_state[widget_key] = opciones[0]
                                    idx = opciones.index(val_previo) if val_previo in opciones else 0
                                    nuevos_datos[c.llave_jinja] = st.selectbox(c.nombre_mostrar, options=opciones, index=idx, help=ayuda, disabled=es_solo_lectura, key=widget_key)
                            elif tipo == "Selección múltiple":
                                previo = val_previo if isinstance(val_previo, list) else []
                                seleccion_previa = [v for v in previo if v in opciones]
                                if not opciones:
                                    st.warning(f"'{c.nombre_mostrar}' no tiene opciones disponibles para la selección actual.")
                                    nuevos_datos[c.llave_jinja] = previo
                                else:
                                    if widget_key in st.session_state:
                                        st.session_state[widget_key] = [v for v in st.session_state[widget_key] if v in opciones]
                                    nuevos_datos[c.llave_jinja] = st.multiselect(c.nombre_mostrar, options=opciones, default=seleccion_previa, help=ayuda, disabled=es_solo_lectura, key=widget_key)
                            elif tipo == "Casilla":
                                nuevos_datos[c.llave_jinja] = st.checkbox(c.nombre_mostrar, value=bool(val_previo), help=ayuda, disabled=es_solo_lectura, key=widget_key)
                            elif tipo == "Fecha":
                                val_fecha = datetime.date.today()
                                if val_previo:
                                    try:
                                        val_fecha = datetime.datetime.strptime(str(val_previo), "%Y-%m-%d").date()
                                    except (TypeError, ValueError):
                                        pass
                                nuevos_datos[c.llave_jinja] = st.date_input(c.nombre_mostrar, value=val_fecha, help=ayuda, disabled=es_solo_lectura, key=widget_key)
                            else:
                                st.warning(f"Tipo de campo no compatible: '{tipo}' ({c.nombre_mostrar}).")
                                nuevos_datos[c.llave_jinja] = val_previo

                    submit_btn = st.button("Validar y Guardar Datos", key=f"save_datos_{part.id}", disabled=es_solo_lectura)
                    if submit_btn and not es_solo_lectura:
                        errores = []
                        for c in campos_ordenados:
                            if c.llave_jinja not in nuevos_datos:
                                continue
                            val = nuevos_datos.get(c.llave_jinja)
                            config = _field_config(c)
                            if config.get("required", False) and (val is None or val == "" or val == [] or (c.tipo_input == "Casilla" and val is not True)):
                                errores.append(f"❌ '{c.nombre_mostrar}' es obligatorio.")
                            if c.tipo_input == "Fecha" and isinstance(val, datetime.date):
                                if c.regla_validacion == "max_90_dias":
                                    diff = (datetime.date.today() - val).days
                                    if diff > 90:
                                        errores.append(f"❌ '{c.nombre_mostrar}' excede 90 días de antigüedad.")
                                    elif diff < 0:
                                        errores.append(f"❌ '{c.nombre_mostrar}' no puede ser fecha futura.")
                                elif c.regla_validacion == "vigente_futuro":
                                    if val < datetime.date.today():
                                        errores.append(f"❌ '{c.nombre_mostrar}' ya está vencido.")
                        if errores:
                            for e in errores:
                                st.error(e)
                        else:
                            # Merge submitted values so unrelated and hidden conditional fields are preserved.
                            datos_guardados = dict(datos_actuales)
                            for k, v in nuevos_datos.items():
                                datos_guardados[k] = v.strftime("%Y-%m-%d") if isinstance(v, datetime.date) else v
                            part.persona.datos_json = datos_guardados
                            flag_modified(part.persona, "datos_json")
                            db.commit()
                            st.success("✅ Datos guardados.")
                            st.rerun()

            # ==========================================
            # TAB 2: EVIDENCIAS ADJUNTAS
            # ==========================================
            with subtab_evid:
                st.write("📎 **Evidencias Adjuntas Requeridas**")
                todas_evidencias = db.query(ConfiguracionEvidencia).all()
                evidencias_aplicables = [e for e in todas_evidencias if e.tipo_persona in ["Ambas", part.persona.tipo] and (not e.roles_aplica or part.rol in e.roles_aplica)]
                
                if not evidencias_aplicables:
                    st.info("No se requieren documentos probatorios adicionales para este perfil.")
                else:
                    for ev in evidencias_aplicables:
                        doc_ev = db.query(DocumentoExpediente).filter_by(participacion_id=part.id, categoria_documento="Evidencia_Adjunta", tipo_documento=ev.nombre_evidencia).first()
                        col_ev1, col_ev2 = st.columns([1, 1])
                        with col_ev1:
                            st.markdown(f"**{ev.nombre_evidencia}**")
                            if doc_ev and doc_ev.estatus == "Cargado": st.success(f"✅ Archivo en la nube ({doc_ev.fecha_actualizacion.strftime('%Y-%m-%d')})")
                            else: st.warning("⚠️ Pendiente de carga")
                        with col_ev2:
                            if not doc_ev or doc_ev.estatus != "Cargado":
                                archivo_ev = st.file_uploader("Subir Archivo (.pdf, .jpg, .png)", type=["pdf", "jpg", "jpeg", "png"], key=f"up_ev_{part.id}_{ev.id}", label_visibility="collapsed", disabled=es_solo_lectura)
                                if archivo_ev:
                                    if st.button("Guardar Evidencia", key=f"btn_ev_{part.id}_{ev.id}", disabled=es_solo_lectura):
                                        ts = int(datetime.datetime.now().timestamp())
                                        proy_limpio = limpiar_nombre_archivo(part.proyecto.nombre)
                                        nombre_limpio = limpiar_nombre_archivo(ev.nombre_evidencia)
                                        pers_limpio = limpiar_nombre_archivo(part.persona.razon_social_nombre)
                                        ext = os.path.splitext(archivo_ev.name)[1].lower()
                                        ruta_ev = f"evidencias/{proy_limpio}-{pers_limpio}-{nombre_limpio}-{ts}{ext}"
                                        try:
                                            supabase_client.storage.from_("expedientes").upload(file=archivo_ev.getvalue(), path=ruta_ev, file_options={"content-type": archivo_ev.type, "x-upsert": "true"})
                                            if not doc_ev: db.add(DocumentoExpediente(participacion_id=part.id, categoria_documento="Evidencia_Adjunta", tipo_documento=ev.nombre_evidencia, estatus="Cargado", ruta_archivo=ruta_ev))
                                            else: doc_ev.estatus = "Cargado"; doc_ev.ruta_archivo = ruta_ev
                                            db.commit()
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error subiendo evidencia: {e}")

            # ==========================================
            # TAB 3: PAQUETE DOCUMENTAL Y TRAZABILIDAD
            # ==========================================
            with subtab_paquete:
                st.write("📄 **Gestión del Paquete Documental**")
                
                doc_exp = db.query(DocumentoExpediente).filter_by(participacion_id=part.id, tipo_documento="Paquete Unificado").first()
                plantillas_aplicables = [tpl for tpl in db.query(PlantillaFormato).all() if tpl.roles_aplica and part.rol in tpl.roles_aplica]

                col_izq, col_der = st.columns([1, 1])
                with col_izq:
                    if doc_exp: st.info(f"Estatus: **{doc_exp.estatus}**")
                    else: st.warning("Estatus: **No generado**")
                        
                    if not plantillas_aplicables:
                        st.error("No hay formatos configurados para este rol.")
                    else:
                        if st.button(f"Generar Paquete PDF Unificado", key=f"btn_gen_{part.id}"):
                            context = {"nombre": part.persona.razon_social_nombre, "rfc": part.persona.rfc or "", **datos_actuales}
                            lista_pdfs = []
                            with st.spinner("Compilando documentos y convirtiendo a PDF... Esto puede tomar unos segundos."):
                                for tpl in plantillas_aplicables:
                                    if tpl.ruta_plantilla_word:
                                        ext = os.path.splitext(tpl.ruta_plantilla_word)[1].lower()
                                        try:
                                            archivo_bytes = supabase_client.storage.from_("expedientes").download(tpl.ruta_plantilla_word)
                                            doc_procesado = procesar_word(archivo_bytes, context) if ext == ".docx" else procesar_excel(archivo_bytes, context) if ext == ".xlsx" else None
                                            if doc_procesado:
                                                lista_pdfs.append(convertir_a_pdf(doc_procesado, ext))
                                        except Exception as e:
                                            st.error(f"Error procesando '{tpl.nombre}': {e}")
                                if lista_pdfs:
                                    pdf_final_bytes = fusionar_pdfs(lista_pdfs)
                                    st.session_state[f'pdf_bytes_{part.id}'] = pdf_final_bytes
                                    if not doc_exp:
                                        db.add(DocumentoExpediente(participacion_id=part.id, categoria_documento="Paquete", tipo_documento="Paquete Unificado", estatus="Generado"))
                                    else:
                                        doc_exp.estatus = "Actualizado"
                                    db.commit()
                                    st.rerun()
                                else:
                                    st.error("No se pudo generar ningún documento. Verifique las plantillas.")

                        if doc_exp or f'pdf_bytes_{part.id}' in st.session_state:
                            if f'pdf_bytes_{part.id}' in st.session_state:
                                st.download_button("⬇️ 1. Descargar Paquete (.pdf)", data=st.session_state[f'pdf_bytes_{part.id}'], file_name=f"Paquete_{part.persona.razon_social_nombre.replace(' ', '_')}.pdf", mime="application/pdf", key=f"dl_{part.id}")
                            else:
                                st.info("Por favor, vuelve a dar clic en 'Generar Paquete PDF' para cargar el archivo en memoria.")
                                
                with col_der:
                    archivo_subido = st.file_uploader("⬆️ 3. Subir Paquete Firmado (.pdf)", type=["pdf"], key=f"up_{part.id}", disabled=es_solo_lectura)
                    if archivo_subido is not None:
                        if st.button("Confirmar Entrega de Documento", key=f"btn_up_{part.id}", disabled=es_solo_lectura):
                            ts = int(datetime.datetime.now().timestamp())
                            proy_limpio = limpiar_nombre_archivo(part.proyecto.nombre)
                            pers_limpio = limpiar_nombre_archivo(part.persona.razon_social_nombre)
                            ruta_pdf = f"firmados/{proy_limpio}-{pers_limpio}-formatos-{ts}.pdf"
                            try:
                                supabase_client.storage.from_("expedientes").upload(file=archivo_subido.getvalue(), path=ruta_pdf, file_options={"content-type": "application/pdf", "x-upsert": "true"})
                                doc_exp.estatus = "Firmado y Cargado"
                                doc_exp.ruta_archivo = ruta_pdf
                                db.commit()
                                st.success("¡Documento enviado y resguardado en la nube de forma segura!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error subiendo a la nube: {e}")

                if doc_exp and plantillas_aplicables:
                    st.markdown("### 📋 Instrucciones de Firma")
                    st.write("2. Descargue el paquete único en formato PDF e imprímalo. Firme según la siguiente tabla:")
                    filas_tabla = []
                    total_firmas_paquete, offset_paginas = 0, 0
                    for formato in plantillas_aplicables:
                        firmas = formato.firmas_json or []
                        num_firmas = len(firmas)
                        total_firmas_paquete += num_firmas
                        for i, firma in enumerate(firmas):
                            pag_documento = offset_paginas + int(firma.get("pag_formato", 0))
                            filas_tabla.append({
                                "Documento": formato.nombre if i == 0 else "", "Núm. Firmas": num_firmas if i == 0 else "",
                                "Pág (Formato)": firma.get("pag_formato", ""), "Pág (Documento)": pag_documento,
                                "Tipo de Firma": firma.get("tipo_firma", ""), "Rubricar todas": formato.rubricar_todas if i == 0 else ""
                            })
                        if num_firmas == 0:
                            filas_tabla.append({"Documento": formato.nombre, "Núm. Firmas": 0, "Pág (Formato)": "-", "Pág (Documento)": "-", "Tipo de Firma": "-", "Rubricar todas": formato.rubricar_todas})
                        offset_paginas += formato.paginas_totales
                    filas_tabla.append({"Documento": "TOTAL PAQUETE", "Núm. Firmas": f"**{total_firmas_paquete}**", "Pág (Formato)": "", "Pág (Documento)": "", "Tipo de Firma": "", "Rubricar todas": ""})
                    st.markdown(pd.DataFrame(filas_tabla).style.hide(axis="index").to_html(), unsafe_allow_html=True)
                
                if doc_exp and doc_exp.estatus in ["Firmado y Cargado", "Enviado Físicamente", "Recibido", "Validado Original"]:
                    st.divider()
                    st.markdown("### 📦 Trazabilidad del Documento Original")
                    meta = doc_exp.metadata_json or {}
                    
                    if doc_exp.estatus in ["Enviado Físicamente", "Recibido", "Validado Original"]:
                        st.success(f"✅ Estatus físico actual: **{doc_exp.estatus}**")
                        st.write(f"**Método:** {meta.get('metodo', 'N/A')} | **Fecha de envío/entrega:** {meta.get('fecha_envio', 'N/A')}")
                        if meta.get('metodo') == "Enviado por paquetería":
                            st.write(f"**Paquetería:** {meta.get('empresa', 'N/A')} | **Guía:** {meta.get('guia', 'N/A')}")
                        st.warning("⚠️ Si cometió un error o la documentación fue rechazada, puede reiniciar el flujo.")
                        if st.button("🔄 Reiniciar Flujo", key=f"btn_restart_{part.id}", disabled=es_solo_lectura):
                            doc_exp.estatus = "Actualizado"
                            meta.pop("metodo", None); meta.pop("fecha_envio", None); meta.pop("empresa", None); meta.pop("guia", None)
                            doc_exp.metadata_json = meta
                            flag_modified(doc_exp, "metadata_json")
                            db.commit()
                            st.rerun()
                    elif doc_exp.estatus == "Firmado y Cargado":
                        metodo = st.radio("Método de entrega", ["Entregado a responsable", "Enviado por paquetería"], key=f"metodo_{part.id}", disabled=es_solo_lectura)
                        admins_proyecto = [admin.email for admin in part.proyecto.admins]
                        admin_texto = ", ".join(admins_proyecto) if admins_proyecto else "Administrador de Proyecto (Pendiente)"
                        empresa, guia = "", ""
                        if metodo == "Entregado a responsable":
                            st.info(f"👤 Entregar a: **{admin_texto}**")
                        else:
                            col_a, col_b = st.columns(2)
                            empresa = col_a.text_input("Empresa de paquetería", key=f"emp_{part.id}", disabled=es_solo_lectura)
                            guia = col_b.text_input("Número de guía", key=f"guia_{part.id}", disabled=es_solo_lectura)
                        fecha_envio = st.date_input("Fecha de entrega/envío", value=datetime.date.today(), key=f"fecha_{part.id}", disabled=es_solo_lectura)
                        if st.button("Registrar Envío/Entrega", key=f"btn_track_{part.id}", disabled=es_solo_lectura):
                            nuevos_meta = meta.copy()
                            nuevos_meta["metodo"] = metodo
                            nuevos_meta["fecha_envio"] = fecha_envio.strftime("%Y-%m-%d")
                            if metodo == "Enviado por paquetería":
                                nuevos_meta["empresa"] = empresa; nuevos_meta["guia"] = guia
                            doc_exp.metadata_json = nuevos_meta
                            doc_exp.estatus = "Enviado Físicamente"
                            flag_modified(doc_exp, "metadata_json")
                            db.commit()
                            st.rerun()