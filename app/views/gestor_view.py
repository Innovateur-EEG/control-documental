import os
import io
import zipfile
import datetime
import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from sqlalchemy.orm.attributes import flag_modified
from app.models.database import Participacion, JerarquiaParticipacion, DocumentoExpediente, PlantillaFormato, ConfiguracionCampos, ConfiguracionEvidencia, UsuarioPersonaGestor, supabase_client
from app.utils.gestor import EDIT_PERMISSION, READ_ONLY_PERMISSION, descendant_participation_ids, effective_permission
from app.utils.documentos import procesar_plantillas_a_pdf, fusionar_pdfs, obtener_ruta_paquete_generado, limpiar_metadatos_reinicio_paquete
from app.utils.dynamic_fields import checkbox_value, dependent_options, field_config, field_is_visible, merge_capture_values, number_widget_options, text_widget_options, validate_submitted_value
from app.utils.evidencias import upload_then_persist
from app.utils.entity_types import normalize_person_type, scope_applies

def limpiar_nombre_archivo(nombre: str) -> str:
    import unicodedata, re
    if not nombre: return "sin_nombre"
    nombre = str(nombre)
    nombre = unicodedata.normalize('NFKD', nombre).encode('ASCII', 'ignore').decode('utf-8').lower()
    nombre = re.sub(r'[^\w\.-]', '_', nombre)
    nombre = re.sub(r'_+', '_', nombre)
    return nombre.strip('_')

def render_gestor(db, user_actual, tab_expedientes, allowed_project_ids=None):
    with tab_expedientes:
        st.subheader("📋 Mis Expedientes")
        
        # --- SOLUCIÓN PUNTOS 1 y 4: Restaurar herencia ---
        personas_directas = [asig.persona for asig in user_actual.personas_asignadas] if user_actual else []
        personas_ids = [p.id for p in personas_directas]
        
        # "Mis Expedientes" is driven by explicit user assignments, not the
        # separate project-admin scope used by administrative tools.
        part_directas = (
            db.query(Participacion).filter(Participacion.persona_id.in_(personas_ids)).all()
            if personas_ids else []
        )
        part_directas_ids = [p.id for p in part_directas]

        # Build the hierarchy from participation IDs. The helper guards against cycles.
        jerarquias = db.query(JerarquiaParticipacion).all()
        hierarchy_edges = [(rel.padre_id, rel.hijo_id) for rel in jerarquias]
        hijas_ids = descendant_participation_ids(part_directas_ids, hierarchy_edges)
        part_hijas_query = db.query(Participacion).filter(Participacion.id.in_(hijas_ids)) if hijas_ids else None
        part_hijas = part_hijas_query.all() if part_hijas_query is not None else []

        # Combine direct assignments and descendants without duplicates.
        todas_parts = list({p.id: p for p in (part_directas + part_hijas)}.values())
        
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
            try:
                normalize_person_type(part.persona.tipo)
            except ValueError:
                st.error(
                    f"El tipo de entidad de {part.persona.razon_social_nombre!r} no es válido. "
                    "Corrígelo en el Catálogo Maestro antes de capturar información."
                )
                st.stop()
            
            # Resolve direct and inherited permissions. Unknown values fail closed.
            direct_permissions = {
                assignment.persona_id: assignment.nivel_permiso
                for assignment in (user_actual.personas_asignadas if user_actual else [])
            }
            parents_by_child = {}
            for parent_id, child_id in hierarchy_edges:
                parents_by_child.setdefault(child_id, []).append(parent_id)
            participation_persona_ids = {item.id: item.persona_id for item in todas_parts}
            permiso_actual = effective_permission(
                part.id,
                part.persona_id,
                direct_permissions,
                parents_by_child,
                participation_persona_ids,
            )
            es_solo_lectura = permiso_actual != EDIT_PERMISSION
                
            st.divider()
            c_head1, c_head2 = st.columns([3, 1])
            c_head1.markdown(f"### Expediente: **{part.persona.razon_social_nombre}**")
            c_head1.caption(f"RFC: {part.persona.rfc or 'Sin RFC'} | Rol: {part.rol}")
            
            if es_solo_lectura:
                c_head2.warning("🔒 Solo Lectura")
            else:
                c_head2.success("✏️ Edición Completa")

            # --- Gate the signing-package workflow on persisted required capture fields. ---
            datos_guardados_gate = part.persona.datos_json or {}
            campos_gate = [
                campo for campo in db.query(ConfiguracionCampos).all()
                if scope_applies(campo.tipo_persona, part.persona.tipo)
                and (not campo.roles_aplica or part.rol in campo.roles_aplica)
            ]
            campos_requeridos_pendientes = []
            for campo_gate in campos_gate:
                config_gate = field_config(getattr(campo_gate, "configuracion_json", None))
                if not config_gate.get("required", False):
                    continue
                try:
                    visible_gate = field_is_visible(config_gate, datos_guardados_gate)
                except ValueError as exc:
                    campos_requeridos_pendientes.append(
                        f"{campo_gate.nombre_mostrar} (configuración condicional inválida: {exc})"
                    )
                    continue
                if not visible_gate:
                    continue
                valor_gate = datos_guardados_gate.get(campo_gate.llave_jinja)
                vacio_gate = valor_gate is None or valor_gate == "" or valor_gate == []
                if campo_gate.tipo_input == "Casilla" and not checkbox_value(valor_gate):
                    vacio_gate = True
                if not vacio_gate and "options_map" in config_gate:
                    try:
                        vacio_gate = not validate_submitted_value(
                            config_gate, valor_gate, datos_guardados_gate, campo_gate.opciones_json or []
                        )
                    except ValueError:
                        vacio_gate = True
                if not vacio_gate and campo_gate.tipo_input == "Fecha" and valor_gate:
                    try:
                        fecha_gate = (
                            valor_gate if isinstance(valor_gate, datetime.date)
                            else datetime.datetime.strptime(str(valor_gate), "%Y-%m-%d").date()
                        )
                        if campo_gate.regla_validacion == "max_90_dias":
                            dias_gate = (datetime.date.today() - fecha_gate).days
                            vacio_gate = dias_gate > 90 or dias_gate < 0
                        elif campo_gate.regla_validacion == "vigente_futuro":
                            vacio_gate = fecha_gate < datetime.date.today()
                    except (TypeError, ValueError):
                        vacio_gate = True
                if vacio_gate:
                    campos_requeridos_pendientes.append(campo_gate.nombre_mostrar)

            if campos_requeridos_pendientes:
                st.info(
                    "El paquete para firma está bloqueado hasta guardar correctamente los campos obligatorios: "
                    + ", ".join(campos_requeridos_pendientes)
                    + ". Complete y guarde los datos en «Formulario de Captura»."
                )
                subtab_form, subtab_evid = st.tabs(["📝 Formulario de Captura", "📎 Documentos Adjuntos"])
                subtab_paquete = None
            else:
                subtab_form, subtab_evid, subtab_paquete = st.tabs([
                    "📝 Formulario de Captura", "📎 Documentos Adjuntos", "📦 Paquete para firma"
                ])
            
            # ==========================================
            # TAB 1: FORMULARIO DINÁMICO
            # ==========================================
            with subtab_form:
                if es_solo_lectura:
                    st.info("ℹ️ Modo Consulta: Los formularios están bloqueados.")
                    
                datos_actuales = part.persona.datos_json or {}
                todos_campos = db.query(ConfiguracionCampos).all()
                campos_aplicables = [c for c in todos_campos if scope_applies(c.tipo_persona, part.persona.tipo) and (not c.roles_aplica or part.rol in c.roles_aplica)]
                
                if campos_aplicables:
                    # Configuration is metadata-driven. Conditional fields need reruns, so widgets
                    # are intentionally outside st.form and use stable keys.
                    def _field_config(field):
                        return field_config(getattr(field, "configuracion_json", None))

                    def _field_order(field):
                        try:
                            return int(_field_config(field).get("order", 100) or 100)
                        except (TypeError, ValueError):
                            return 100

                    campos_ordenados = sorted(
                        campos_aplicables,
                        key=lambda field: (
                            str(_field_config(field).get("section") or "General"),
                            _field_order(field),
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

                        valores_para_reglas = dict(datos_actuales)
                        valores_para_reglas.update(nuevos_datos)
                        for llave_regla, campo_regla in campo_por_llave.items():
                            clave_regla = f"field_{part.id}_{campo_regla.id}"
                            if clave_regla in st.session_state:
                                valores_para_reglas[llave_regla] = st.session_state[clave_regla]
                        try:
                            visible = field_is_visible(config, valores_para_reglas)
                        except ValueError as exc:
                            st.warning(f"Configuración condicional inválida para '{c.nombre_mostrar}': {exc}")
                            visible = True
                        if not visible:
                            continue

                        # Render a section heading only when its first visible field is reached.
                        if seccion != seccion_actual:
                            st.markdown(f"#### {seccion}")
                            seccion_actual = seccion
                            columnas = st.columns(2)
                            indice_columna = 0

                        col = columnas[indice_columna % 2]
                        indice_columna += 1
                        widget_key = f"field_{part.id}_{c.id}"
                        val_previo = st.session_state.get(widget_key, datos_actuales.get(c.llave_jinja, config.get("default")))
                        ayuda = str(config.get("help") or "") or None

                        with col:
                            tipo = c.tipo_input
                            opciones = c.opciones_json or []
                            valores_para_reglas = dict(datos_actuales)
                            valores_para_reglas.update(nuevos_datos)
                            for llave_regla, campo_regla in campo_por_llave.items():
                                clave_regla = f"field_{part.id}_{campo_regla.id}"
                                if clave_regla in st.session_state:
                                    valores_para_reglas[llave_regla] = st.session_state[clave_regla]
                            try:
                                opciones = dependent_options(config, valores_para_reglas, opciones)
                            except ValueError as exc:
                                st.warning(f"Configuración de opciones inválida para '{c.nombre_mostrar}': {exc}")
                                opciones = []

                            if tipo == "Texto":
                                try:
                                    text_options = text_widget_options(config)
                                except ValueError as exc:
                                    st.warning(f"Configuración inválida para '{c.nombre_mostrar}': {exc}")
                                    text_options = {}
                                nuevos_datos[c.llave_jinja] = st.text_input(
                                    c.nombre_mostrar,
                                    value=str(val_previo or ""),
                                    help=ayuda,
                                    disabled=es_solo_lectura,
                                    key=widget_key,
                                    **text_options,
                                )
                            elif tipo == "Número":
                                try:
                                    val_num = float(val_previo) if val_previo not in (None, "") else 0.0
                                except (TypeError, ValueError):
                                    val_num = 0.0
                                try:
                                    number_options = number_widget_options(config)
                                except ValueError as exc:
                                    st.warning(f"Configuración inválida para '{c.nombre_mostrar}': {exc}")
                                    number_options = {}
                                if "min_value" in number_options:
                                    val_num = max(val_num, number_options["min_value"])
                                if "max_value" in number_options:
                                    val_num = min(val_num, number_options["max_value"])
                                nuevos_datos[c.llave_jinja] = st.number_input(
                                    c.nombre_mostrar,
                                    value=val_num,
                                    help=ayuda,
                                    disabled=es_solo_lectura,
                                    key=widget_key,
                                    **number_options,
                                )
                            elif tipo in ("Opciones", "Selección única"):
                                if not opciones:
                                    st.warning(f"'{c.nombre_mostrar}' no tiene opciones disponibles para la selección actual.")
                                    nuevos_datos[c.llave_jinja] = val_previo
                                else:
                                    if widget_key in st.session_state and st.session_state[widget_key] not in opciones:
                                        del st.session_state[widget_key]
                                    idx = opciones.index(val_previo) if val_previo in opciones else 0
                                    nuevos_datos[c.llave_jinja] = st.selectbox(c.nombre_mostrar, options=opciones, index=idx, help=ayuda, disabled=es_solo_lectura, key=widget_key)
                            elif tipo == "Selección múltiple":
                                previo = val_previo if isinstance(val_previo, list) else []
                                seleccion_previa = [v for v in previo if v in opciones]
                                if not opciones:
                                    st.warning(f"'{c.nombre_mostrar}' no tiene opciones disponibles para la selección actual.")
                                    nuevos_datos[c.llave_jinja] = previo
                                else:
                                    if widget_key in st.session_state and any(v not in opciones for v in st.session_state[widget_key]):
                                        del st.session_state[widget_key]
                                    nuevos_datos[c.llave_jinja] = st.multiselect(c.nombre_mostrar, options=opciones, default=seleccion_previa, help=ayuda, disabled=es_solo_lectura, key=widget_key)
                            elif tipo == "Casilla":
                                if widget_key in st.session_state and not isinstance(st.session_state[widget_key], bool):
                                    st.session_state[widget_key] = checkbox_value(st.session_state[widget_key])
                                nuevos_datos[c.llave_jinja] = st.checkbox(
                                    c.nombre_mostrar,
                                    value=checkbox_value(val_previo),
                                    help=ayuda,
                                    disabled=es_solo_lectura,
                                    key=widget_key,
                                )
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
                            if "options_map" in config:
                                valores_validacion = dict(datos_actuales)
                                valores_validacion.update(nuevos_datos)
                                for llave_regla, campo_regla in campo_por_llave.items():
                                    clave_regla = f"field_{part.id}_{campo_regla.id}"
                                    if clave_regla in st.session_state:
                                        valores_validacion[llave_regla] = st.session_state[clave_regla]
                                try:
                                    if not validate_submitted_value(config, val, valores_validacion, c.opciones_json or []):
                                        errores.append(f"❌ '{c.nombre_mostrar}' contiene una opción no permitida para la selección actual.")
                                except ValueError as exc:
                                    errores.append(f"❌ Configuración inválida para '{c.nombre_mostrar}': {exc}")
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
                            valores_a_guardar = {
                                k: (v.strftime("%Y-%m-%d") if isinstance(v, datetime.date) else v)
                                for k, v in nuevos_datos.items()
                            }
                            datos_guardados = merge_capture_values(datos_actuales, valores_a_guardar)
                            part.persona.datos_json = datos_guardados
                            flag_modified(part.persona, "datos_json")
                            db.commit()
                            st.success("✅ Datos guardados.")
                            st.rerun()

            # ==========================================
            # TAB 2: DOCUMENTOS ADJUNTOS
            # ==========================================
            with subtab_evid:
                st.write("📎 **Documentos Adjuntos Requeridos**")
                todas_evidencias = db.query(ConfiguracionEvidencia).all()
                evidencias_aplicables = [e for e in todas_evidencias if scope_applies(e.tipo_persona, part.persona.tipo) and (not e.roles_aplica or part.rol in e.roles_aplica)]
                
                if not evidencias_aplicables:
                    st.info("No se requieren documentos probatorios adicionales para este perfil.")
                else:
                    for ev in evidencias_aplicables:
                        doc_ev = db.query(DocumentoExpediente).filter_by(participacion_id=part.id, categoria_documento="Evidencia_Adjunta", tipo_documento=ev.nombre_evidencia).first()
                        col_ev1, col_ev2 = st.columns([1, 1])
                        with col_ev1:
                            st.markdown(f"**{ev.nombre_evidencia}**")
                            config_evidencia = ev.configuracion_json or {}
                            vigencia = config_evidencia.get("vigencia")
                            if vigencia not in (None, ""):
                                vigencia_texto = (
                                    f"{vigencia} días"
                                    if isinstance(vigencia, (int, float)) and not isinstance(vigencia, bool)
                                    else str(vigencia)
                                )
                                st.caption(f"Vigencia: {vigencia_texto}")
                            if doc_ev and doc_ev.estatus == "Cargado":
                                fecha_carga = (
                                    doc_ev.fecha_actualizacion.strftime("%Y-%m-%d")
                                    if doc_ev.fecha_actualizacion else "Fecha no disponible"
                                )
                                st.success(f"Archivo en la nube ({fecha_carga})")
                                if doc_ev.ruta_archivo:
                                    if st.button("Preparar descarga", key=f"prep_ev_dl_{part.id}_{ev.id}"):
                                        try:
                                            if supabase_client is None:
                                                raise RuntimeError("Supabase Storage no está configurado.")
                                            st.session_state[f"evidencia_bytes_{part.id}_{ev.id}"] = (
                                                supabase_client.storage.from_("expedientes").download(doc_ev.ruta_archivo)
                                            )
                                        except Exception as exc:
                                            st.error(f"No se pudo recuperar la evidencia: {exc}")
                                    evidencia_bytes = st.session_state.get(f"evidencia_bytes_{part.id}_{ev.id}")
                                    if evidencia_bytes is not None:
                                        st.download_button(
                                            "Descargar evidencia",
                                            data=evidencia_bytes,
                                            file_name=os.path.basename(doc_ev.ruta_archivo),
                                            mime="application/octet-stream",
                                            key=f"dl_ev_{part.id}_{ev.id}",
                                        )
                            else:
                                st.warning("Pendiente de carga")
                        with col_ev2:
                            upload_form_key = f"form_ev_{part.id}_{ev.id}"
                            with st.form(upload_form_key, clear_on_submit=True):
                                archivo_ev = st.file_uploader(
                                    "Subir o reemplazar archivo (.pdf, .jpg, .png)",
                                    type=["pdf", "jpg", "jpeg", "png"],
                                    key=f"up_ev_{part.id}_{ev.id}",
                                    label_visibility="collapsed",
                                    disabled=es_solo_lectura,
                                )
                                guardar_evidencia = st.form_submit_button(
                                    "Cargar/Actualizar evidencia",
                                    disabled=es_solo_lectura,
                                )
                            if guardar_evidencia:
                                if not archivo_ev:
                                    st.warning("Selecciona un archivo antes de continuar.")
                                else:
                                    ts = int(datetime.datetime.now().timestamp() * 1000)
                                    proy_limpio = limpiar_nombre_archivo(part.proyecto.nombre)
                                    nombre_limpio = limpiar_nombre_archivo(ev.nombre_evidencia)
                                    pers_limpio = limpiar_nombre_archivo(part.persona.razon_social_nombre)
                                    ext = os.path.splitext(archivo_ev.name)[1].lower()
                                    ruta_ev = f"evidencias/{proy_limpio}-{pers_limpio}-{nombre_limpio}-{ts}{ext}"
                                    try:
                                        if supabase_client is None:
                                            raise RuntimeError("Supabase Storage no está configurado.")

                                        def _upload_evidencia():
                                            supabase_client.storage.from_("expedientes").upload(
                                                file=archivo_ev.getvalue(),
                                                path=ruta_ev,
                                                file_options={"content-type": archivo_ev.type, "x-upsert": "true"},
                                            )

                                        def _persist_evidencia():
                                            if not doc_ev:
                                                db.add(DocumentoExpediente(
                                                    participacion_id=part.id,
                                                    categoria_documento="Evidencia_Adjunta",
                                                    tipo_documento=ev.nombre_evidencia,
                                                    estatus="Cargado",
                                                    ruta_archivo=ruta_ev,
                                                    metadata_json={"nombre_original": archivo_ev.name},
                                                ))
                                            else:
                                                doc_ev.estatus = "Cargado"
                                                doc_ev.ruta_archivo = ruta_ev
                                                metadata_ev = dict(doc_ev.metadata_json or {})
                                                metadata_ev["nombre_original"] = archivo_ev.name
                                                doc_ev.metadata_json = metadata_ev
                                                flag_modified(doc_ev, "metadata_json")
                                            db.commit()

                                        upload_then_persist(
                                            _upload_evidencia,
                                            _persist_evidencia,
                                            db.rollback,
                                            lambda: supabase_client.storage.from_("expedientes").remove([ruta_ev]),
                                        )
                                        st.success("Evidencia cargada y registrada.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"No se pudo guardar la evidencia: {e}")

            # ==========================================
            # TAB 3: PAQUETE PARA FIRMA Y TRAZABILIDAD
            # ==========================================
            if subtab_paquete is not None:
                with subtab_paquete:
                    st.write("📄 **Gestión del Paquete para firma**")
                    
                    doc_exp = db.query(DocumentoExpediente).filter_by(
                        participacion_id=part.id,
                        categoria_documento="Paquete",
                        tipo_documento="Paquete Unificado",
                    ).first()
                    plantillas_aplicables = [tpl for tpl in db.query(PlantillaFormato).all() if tpl.roles_aplica and part.rol in tpl.roles_aplica]

                    if doc_exp: st.info(f"Estatus: **{doc_exp.estatus}**")
                    else: st.warning("Estatus: **No generado**")
                        
                    if not plantillas_aplicables:
                        st.error("No hay formatos configurados para este rol.")
                    else:
                        if doc_exp:
                            st.warning(
                                "Volver a generar el paquete reemplazará el PDF generado y reiniciará la referencia "
                                "al firmado actual y los datos de entrega/recepción. Los archivos firmados históricos se conservan."
                            )
                            confirmar_regeneracion = st.checkbox(
                                "Confirmo que quiero reemplazar el paquete y borrar su evidencia de entrega.",
                                key=f"confirm_regen_{part.id}",
                                disabled=es_solo_lectura,
                            )
                        else:
                            confirmar_regeneracion = True

                        if st.button(
                            "Volver a generar paquete..." if doc_exp else "Generar Paquete PDF Unificado",
                            key=f"btn_gen_{part.id}",
                            disabled=es_solo_lectura or not confirmar_regeneracion,
                        ):
                            if supabase_client is None:
                                st.error("Supabase Storage no está configurado; no se puede generar el paquete.")
                            else:
                                context = {"nombre": part.persona.razon_social_nombre, "rfc": part.persona.rfc or "", **datos_actuales}
                                with st.spinner("Compilando documentos y convirtiendo a PDF... Esto puede tomar unos segundos."):
                                    lista_pdfs, errores_procesamiento = procesar_plantillas_a_pdf(
                                        plantillas_aplicables,
                                        context,
                                        lambda ruta: supabase_client.storage.from_("expedientes").download(ruta),
                                    )
                                for error in errores_procesamiento:
                                    st.error(f"Error procesando plantilla: {error}")
                                if lista_pdfs:
                                    pdf_final_bytes = fusionar_pdfs(lista_pdfs)
                                    ts_paquete = int(datetime.datetime.now().timestamp() * 1000)
                                    ruta_paquete = f"paquetes/{part.id}/{ts_paquete}-paquete-unificado.pdf"
                                    ruta_paquete_anterior = None
                                    paquete_subido = False
                                    paquete_persistido = False
                                    try:
                                        if supabase_client is None:
                                            raise RuntimeError("Supabase Storage no está configurado.")
                                        supabase_client.storage.from_("expedientes").upload(
                                            file=pdf_final_bytes,
                                            path=ruta_paquete,
                                            file_options={"content-type": "application/pdf", "x-upsert": "false"},
                                        )
                                        paquete_subido = True
                                        if not doc_exp:
                                            doc_exp = DocumentoExpediente(
                                                participacion_id=part.id,
                                                categoria_documento="Paquete",
                                                tipo_documento="Paquete Unificado",
                                                estatus="Generado",
                                                ruta_archivo=ruta_paquete,
                                                metadata_json={"ruta_paquete_generado": ruta_paquete},
                                            )
                                            db.add(doc_exp)
                                        else:
                                            metadata = dict(doc_exp.metadata_json or {})
                                            ruta_paquete_anterior = obtener_ruta_paquete_generado(
                                                metadata, doc_exp.ruta_archivo, doc_exp.estatus
                                            )
                                            # Keep historical signed PDFs in Storage; only clear the active reference.
                                            metadata["ruta_paquete_generado"] = ruta_paquete
                                            for clave_entrega in (
                                                "ruta_paquete_firmado", "nombre_paquete_firmado",
                                                "fecha_carga_paquete_firmado", "metodo", "fecha_envio",
                                                "empresa", "guia", "responsables_proyecto",
                                            ):
                                                metadata.pop(clave_entrega, None)
                                            doc_exp.metadata_json = metadata
                                            doc_exp.ruta_archivo = ruta_paquete
                                            doc_exp.estatus = "Actualizado"
                                            flag_modified(doc_exp, "metadata_json")
                                        db.commit()
                                        paquete_persistido = True
                                        for ruta_obsoleta in (ruta_paquete_anterior,):
                                            if ruta_obsoleta and ruta_obsoleta != ruta_paquete:
                                                try:
                                                    supabase_client.storage.from_("expedientes").remove([ruta_obsoleta])
                                                except Exception as exc:
                                                    st.warning(
                                                        "El paquete nuevo se guardó, pero no se pudo eliminar "
                                                        f"el archivo anterior '{ruta_obsoleta}': {exc}"
                                                    )
                                        st.session_state[f"pdf_bytes_{part.id}"] = pdf_final_bytes
                                        st.success("Paquete generado y guardado en almacenamiento.")
                                        st.rerun()
                                    except Exception as e:
                                        db.rollback()
                                        if paquete_subido and not paquete_persistido:
                                            try:
                                                supabase_client.storage.from_("expedientes").remove([ruta_paquete])
                                            except Exception as cleanup_error:
                                                st.warning(
                                                    "Falló el guardado y no se pudo limpiar el paquete temporal: "
                                                    f"{cleanup_error}"
                                                )
                                        st.error(f"No se pudo guardar el paquete generado: {e}")
                                else:
                                    st.error("No se pudo generar ningún documento. Verifique las plantillas.")

                        ruta_paquete_guardado = (
                            obtener_ruta_paquete_generado(
                                doc_exp.metadata_json, doc_exp.ruta_archivo, doc_exp.estatus
                            )
                            if doc_exp else None
                        )
                        if doc_exp and ruta_paquete_guardado:
                            clave_pdf = f"pdf_bytes_{part.id}"
                            if clave_pdf not in st.session_state:
                                try:
                                    if supabase_client is None:
                                        raise RuntimeError("Supabase Storage no está configurado.")
                                    st.session_state[clave_pdf] = supabase_client.storage.from_("expedientes").download(ruta_paquete_guardado)
                                except Exception as e:
                                    st.warning(f"No se pudo recuperar el paquete guardado: {e}")
                            if clave_pdf in st.session_state:
                                st.download_button(
                                    "⬇️ 1. Descargar Paquete (.pdf)",
                                    data=st.session_state[clave_pdf],
                                    file_name=f"Paquete_{limpiar_nombre_archivo(part.persona.razon_social_nombre)}.pdf",
                                    mime="application/pdf",
                                    key=f"dl_{part.id}",
                                )
                        elif doc_exp:
                            st.info("El paquete está registrado, pero no tiene una ruta de descarga. Genérelo nuevamente.")
                                

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
                    

                    if not doc_exp:
                        st.info("Genere primero el paquete para firma para habilitar la carga del documento firmado.")
                    revision_carga_firmado = st.session_state.get(f"revision_carga_firmado_{part.id}", 0)
                    archivo_subido = st.file_uploader(
                        "⬆️ 3. Adjuntar Paquete Firmado (.pdf)",
                        type=["pdf"],
                        key=f"up_{part.id}_{revision_carga_firmado}",
                        disabled=es_solo_lectura or not doc_exp,
                    )
                    if archivo_subido is not None and doc_exp:
                        if st.button("Cargar/Adjuntar paquete firmado", key=f"btn_up_{part.id}", disabled=es_solo_lectura):
                            ts = int(datetime.datetime.now().timestamp())
                            proy_limpio = limpiar_nombre_archivo(part.proyecto.nombre)
                            pers_limpio = limpiar_nombre_archivo(part.persona.razon_social_nombre)
                            ts = int(datetime.datetime.now().timestamp() * 1000)
                            ruta_pdf = f"firmados/{part.id}/{ts}-paquete-firmado.pdf"
                            ruta_firmado_anterior = (doc_exp.metadata_json or {}).get("ruta_paquete_firmado")
                            firmado_subido = False
                            firmado_persistido = False
                            try:
                                if supabase_client is None:
                                    raise RuntimeError("Supabase Storage no está configurado.")
                                supabase_client.storage.from_("expedientes").upload(
                                    file=archivo_subido.getvalue(),
                                    path=ruta_pdf,
                                    file_options={"content-type": "application/pdf", "x-upsert": "false"},
                                )
                                firmado_subido = True
                                metadata = dict(doc_exp.metadata_json or {})
                                if not metadata.get("ruta_paquete_generado"):
                                    ruta_generada_previa = obtener_ruta_paquete_generado(
                                        metadata, doc_exp.ruta_archivo, doc_exp.estatus
                                    )
                                    if ruta_generada_previa:
                                        metadata["ruta_paquete_generado"] = ruta_generada_previa
                                metadata["ruta_paquete_firmado"] = ruta_pdf
                                metadata["nombre_paquete_firmado"] = archivo_subido.name
                                metadata["fecha_carga_paquete_firmado"] = datetime.datetime.now().isoformat(timespec="seconds")
                                doc_exp.metadata_json = metadata
                                doc_exp.estatus = "Firmado y Cargado"
                                doc_exp.ruta_archivo = ruta_pdf
                                flag_modified(doc_exp, "metadata_json")
                                db.commit()
                                firmado_persistido = True
                                # Do not expose bytes cached from a previously uploaded signed package.
                                st.session_state.pop(f"pdf_firmado_bytes_{part.id}", None)
                                # Preserve the previous signed PDF in Storage as upload history.
                                st.session_state[f"revision_carga_firmado_{part.id}"] = revision_carga_firmado + 1
                                st.success("Documento firmado cargado y registrado.")
                                st.rerun()
                            except Exception as e:
                                db.rollback()
                                if firmado_subido and not firmado_persistido:
                                    try:
                                        supabase_client.storage.from_("expedientes").remove([ruta_pdf])
                                    except Exception as cleanup_error:
                                        st.warning(
                                            "Falló el registro y no se pudo limpiar el archivo firmado temporal: "
                                            f"{cleanup_error}"
                                        )
                                st.error(f"No se pudo guardar el documento firmado: {e}")
     
                    if doc_exp:
                        meta_firmado_actual = doc_exp.metadata_json or {}
                        ruta_firmado_actual = meta_firmado_actual.get("ruta_paquete_firmado")
                        if ruta_firmado_actual:
                            nombre_firmado_actual = meta_firmado_actual.get("nombre_paquete_firmado") or os.path.basename(ruta_firmado_actual)
                            fecha_firmado_actual = meta_firmado_actual.get("fecha_carga_paquete_firmado")
                            if not fecha_firmado_actual and doc_exp.fecha_actualizacion:
                                fecha_firmado_actual = doc_exp.fecha_actualizacion.strftime("%Y-%m-%d")
                            col_firmado_label, col_firmado_link = st.columns([3, 1])
                            col_firmado_label.info(
                                f"Documento firmado cargado: **{nombre_firmado_actual}** · "
                                f"Fecha: {fecha_firmado_actual or 'No disponible'}"
                            )
                            if col_firmado_link.button("Generar link de descarga", key=f"prep_signed_dl_{part.id}"):
                                try:
                                    if supabase_client is None:
                                        raise RuntimeError("Supabase Storage no está configurado.")
                                    st.session_state[f"pdf_firmado_bytes_{part.id}"] = (
                                        supabase_client.storage.from_("expedientes").download(ruta_firmado_actual)
                                    )
                                except Exception as exc:
                                    st.error(f"No se pudo recuperar el paquete firmado: {exc}")
                            pdf_firmado_bytes = st.session_state.get(f"pdf_firmado_bytes_{part.id}")
                            if pdf_firmado_bytes is not None:
                                st.download_button(
                                    "Descargar paquete firmado",
                                    data=pdf_firmado_bytes,
                                    file_name=nombre_firmado_actual,
                                    mime="application/pdf",
                                    key=f"dl_signed_{part.id}",
                                )

                    if doc_exp and doc_exp.estatus in ["Firmado y Cargado", "Enviado Físicamente", "Recibido", "Validado Original"]:
                        st.divider()
                        st.markdown("### 📦 Trazabilidad del Documento Original")
                        meta = doc_exp.metadata_json or {}
                        ruta_firmado = meta.get("ruta_paquete_firmado")
                        if doc_exp.estatus in ["Enviado Físicamente", "Recibido", "Validado Original"]:
                            st.success(f"✅ Estatus físico actual: **{doc_exp.estatus}**")
                            st.write(f"**Método:** {meta.get('metodo', 'N/A')} | **Fecha de envío/entrega:** {meta.get('fecha_envio', 'N/A')}")
                            if meta.get("metodo") in ("Entregado a responsable del proyecto", "Entregado a responsable"):
                                responsables_guardados = meta.get("responsables_proyecto") or []
                                if responsables_guardados:
                                    st.write("**Entregado a responsable del proyecto:**")
                                    for responsable in responsables_guardados:
                                        st.write(
                                            f"- {responsable.get('nombre') or 'Nombre no registrado'} | "
                                            f"{responsable.get('email') or 'Correo no registrado'} | "
                                            f"Tel. {responsable.get('telefono') or 'No registrado'}"
                                        )
                            if meta.get('metodo') == "Enviado por paquetería":
                                st.write(f"**Paquetería:** {meta.get('empresa', 'N/A')} | **Guía:** {meta.get('guia', 'N/A')}")
                            if doc_exp.estatus == "Enviado Físicamente":
                                st.info("El responsable del proyecto debe registrar la recepción desde el Tablero de Avance Documental.")
                            elif doc_exp.estatus == "Recibido":
                                if st.button("Validar documento original", key=f"btn_validate_original_{part.id}", disabled=es_solo_lectura):
                                    doc_exp.estatus = "Validado Original"
                                    db.commit()
                                    st.rerun()
                            st.warning("Si cometió un error o la documentación fue rechazada, puede reiniciar el flujo.")
                            if st.button("Reiniciar Flujo", key=f"btn_restart_{part.id}", disabled=es_solo_lectura):
                                metadata_reiniciada, _ruta_firmado_anterior = limpiar_metadatos_reinicio_paquete(meta)
                                doc_exp.estatus = "Actualizado"
                                doc_exp.metadata_json = metadata_reiniciada
                                flag_modified(doc_exp, "metadata_json")
                                db.commit()
                                st.session_state.pop(f"pdf_firmado_bytes_{part.id}", None)
                                # Keep historical signed PDFs in Storage when the active workflow is reset.
                                st.rerun()
                        elif doc_exp.estatus == "Firmado y Cargado":
                            metodo = st.radio("Método de entrega", ["Entregado a responsable del proyecto", "Enviado por paquetería"], key=f"metodo_{part.id}", disabled=es_solo_lectura)
                            admins_proyecto = [
                                f"{admin.nombre or 'Nombre no registrado'} | {admin.email} | Tel. {admin.telefono or 'No registrado'}"
                                for admin in part.proyecto.admins
                            ]
                            admin_texto = "; ".join(admins_proyecto) if admins_proyecto else "Responsable de proyecto pendiente de asignación"
                            empresa, guia = "", ""
                            if metodo == "Entregado a responsable del proyecto":
                                st.info(
                                    f"👤 Entregar al responsable del proyecto **{part.proyecto.nombre}**: "
                                    f"{admin_texto}"
                                )
                            else:
                                col_a, col_b = st.columns(2)
                                empresa = col_a.text_input("Empresa de paquetería", key=f"emp_{part.id}", disabled=es_solo_lectura)
                                guia = col_b.text_input("Número de guía", key=f"guia_{part.id}", disabled=es_solo_lectura)
                            fecha_envio = st.date_input("Fecha de entrega/envío", value=datetime.date.today(), key=f"fecha_{part.id}", disabled=es_solo_lectura)
                            if st.button("Registrar Envío/Entrega", key=f"btn_track_{part.id}", disabled=es_solo_lectura):
                                nuevos_meta = meta.copy()
                                nuevos_meta["metodo"] = metodo
                                nuevos_meta["fecha_envio"] = fecha_envio.strftime("%Y-%m-%d")
                                if metodo == "Entregado a responsable del proyecto":
                                    nuevos_meta["responsables_proyecto"] = [
                                        {
                                            "nombre": admin.nombre or "",
                                            "email": admin.email,
                                            "telefono": admin.telefono or "",
                                        }
                                        for admin in part.proyecto.admins
                                    ]
                                    nuevos_meta.pop("empresa", None)
                                    nuevos_meta.pop("guia", None)
                                else:
                                    nuevos_meta.pop("responsables_proyecto", None)
                                    nuevos_meta["empresa"] = empresa
                                    nuevos_meta["guia"] = guia
                                doc_exp.metadata_json = nuevos_meta
                                doc_exp.estatus = "Enviado Físicamente"
                                flag_modified(doc_exp, "metadata_json")
                                db.commit()
                                st.rerun()