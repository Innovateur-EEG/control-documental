import os
import io
import platform
import tempfile
import subprocess
import openpyxl
from jinja2 import Environment
from pypdf import PdfReader, PdfWriter
from docxtpl import DocxTemplate
from app.utils.template_filters import mark_filter, mark_not_filter, prefix_filter

def procesar_excel(file_bytes: bytes, context: dict) -> bytes:
    """Render Jinja expressions inside Excel string cells and preserve workbook layout."""
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes))
    env = Environment()
    env.filters["mark"] = mark_filter
    env.filters["mark_not"] = mark_not_filter
    env.filters["prefix"] = prefix_filter

    for sheet in wb.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and "{{" in cell.value and "}}" in cell.value:
                    cell.value = env.from_string(cell.value).render(context)

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()

def procesar_word(file_bytes: bytes, context: dict) -> bytes:
    """Renderiza la plantilla Word usando Jinja2"""
    doc = DocxTemplate(io.BytesIO(file_bytes))
    env = Environment()
    env.filters["mark"] = mark_filter
    env.filters["mark_not"] = mark_not_filter
    env.filters["prefix"] = prefix_filter
    doc.render(context, jinja_env=env)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()

def convertir_a_pdf(file_bytes: bytes, extension: str) -> bytes:
    """
    Usa LibreOffice en modo invisible para convertir Word o Excel a PDF.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{extension}")
        
        with open(input_path, "wb") as f:
            f.write(file_bytes)
            
        cmd = None
        # Búsqueda de rutas para Windows Local
        if platform.system() == "Windows":
            rutas = []
            # Buscar en los discos más comunes
            for disco in ["C", "D", "E"]:
                rutas.extend([
                    rf"{disco}:\Program Files\LibreOffice\program\soffice.exe",
                    rf"{disco}:\Program Files (x86)\LibreOffice\program\soffice.exe"
                ])
            for ruta in rutas:
                if os.path.exists(ruta):
                    cmd = [ruta, "--headless", "--convert-to", "pdf", input_path, "--outdir", tmpdir]
                    break
            # Fallback si está instalado pero en otra ruta (requiere estar en el PATH)
            if not cmd:
                cmd = ["soffice", "--headless", "--convert-to", "pdf", input_path, "--outdir", tmpdir]
        else:
            # Comando nativo para Linux (Streamlit Cloud)
            cmd = ["libreoffice", "--headless", "--convert-to", "pdf", input_path, "--outdir", tmpdir]
        
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except FileNotFoundError:
            # Fallback en Linux por si el comando se llama distinto
            if platform.system() != "Windows":
                try:
                    cmd[0] = "soffice"
                    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                except Exception as inner_e:
                    raise RuntimeError(f"Error Linux: 'libreoffice' no está instalado. Streamlit no leyó packages.txt. Detalle: {inner_e}")
            else:
                raise RuntimeError("Error Windows: LibreOffice no está en C:\\Program Files\\ ni en el PATH. Instálalo para probar en local.")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"El motor de LibreOffice falló al convertir. Error: {e.stderr.decode()}")
            
        pdf_path = os.path.join(tmpdir, "input.pdf")
        if not os.path.exists(pdf_path):
            raise RuntimeError("LibreOffice se ejecutó pero el archivo PDF no se generó correctamente.")
            
        with open(pdf_path, "rb") as f:
            return f.read()

def fusionar_pdfs(lista_pdfs_bytes: list) -> bytes:
    """Une múltiples archivos PDF en memoria en uno solo"""
    if not lista_pdfs_bytes:
        return b""
        
    writer = PdfWriter()
    for pdf_bytes in lista_pdfs_bytes:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)
            
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


ESTADOS_CON_RUTA_FIRMADA = {
    "Firmado y Cargado",
    "Enviado Físicamente",
    "Recibido",
    "Validado Original",
}


def obtener_ruta_paquete_generado(metadata: dict | None, ruta_archivo: str | None, estatus: str | None) -> str | None:
    """Return the generated PDF path without mistaking a signed PDF for the generated one."""
    metadata = metadata or {}
    ruta_generada = metadata.get("ruta_paquete_generado")
    if ruta_generada:
        return ruta_generada
    if estatus not in ESTADOS_CON_RUTA_FIRMADA:
        return ruta_archivo
    return None



def limpiar_metadatos_reinicio_paquete(metadata: dict | None) -> tuple[dict, str | None]:
    """Clear signed-package and delivery state while preserving the generated original."""
    cleaned = dict(metadata or {})
    ruta_firmado = cleaned.pop("ruta_paquete_firmado", None)
    for key in (
        "nombre_paquete_firmado", "fecha_carga_paquete_firmado",
        "metodo", "fecha_envio", "empresa", "guia", "responsables_proyecto",
    ):
        cleaned.pop(key, None)
    return cleaned, ruta_firmado


def procesar_plantillas_a_pdf(plantillas, context: dict, descargar):
    """Render and convert every configured template, rejecting partial packages.

    Returns (pdfs, errors). If any template fails, pdfs is empty so callers
    cannot accidentally publish an incomplete package.
    """
    pdfs = []
    errors = []
    for plantilla in plantillas:
        nombre = getattr(plantilla, "nombre", "Plantilla sin nombre")
        ruta = getattr(plantilla, "ruta_plantilla_word", None)
        if not ruta:
            errors.append(f"'{nombre}': no tiene una plantilla configurada.")
            continue
        extension = os.path.splitext(ruta)[1].lower()
        try:
            if extension not in (".docx", ".xlsx"):
                raise ValueError(f"formato de plantilla no soportado: {extension or 'sin extensión'}")
            file_bytes = descargar(ruta)
            rendered = procesar_word(file_bytes, context) if extension == ".docx" else procesar_excel(file_bytes, context)
            if not rendered:
                raise ValueError("el renderizador no produjo un documento.")
            pdf = convertir_a_pdf(rendered, extension)
            if not pdf:
                raise ValueError("la conversión a PDF no produjo contenido.")
            pdfs.append(pdf)
        except Exception as exc:
            errors.append(f"'{nombre}': {exc}")
    return ([], errors) if errors else (pdfs, [])
