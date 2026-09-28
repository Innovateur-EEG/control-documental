import os
import io
import platform
import tempfile
import subprocess
import openpyxl
from pypdf import PdfReader, PdfWriter
from docxtpl import DocxTemplate

def procesar_excel(file_bytes: bytes, context: dict) -> bytes:
    """Abre un Excel en memoria, busca las etiquetas {{llave}} y las reemplaza"""
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes))
    
    for sheet in wb.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if cell.value and isinstance(cell.value, str):
                    # Si detecta formato Jinja, intenta reemplazar con el contexto
                    for key, val in context.items():
                        tag = f"{{{{{key}}}}}" # Equivale a {{key}}
                        if tag in cell.value:
                            cell.value = cell.value.replace(tag, str(val))
                            
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()

def procesar_word(file_bytes: bytes, context: dict) -> bytes:
    """Renderiza la plantilla Word usando Jinja2"""
    doc = DocxTemplate(io.BytesIO(file_bytes))
    doc.render(context)
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
            
        # Determinar el comando según el sistema operativo
        if platform.system() == "Windows":
            # Rutas típicas de LibreOffice en Windows
            ruta_lo = r"C:\Program Files\LibreOffice\program\soffice.exe"
            if not os.path.exists(ruta_lo):
                ruta_lo = r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"
            cmd = [ruta_lo, "--headless", "--convert-to", "pdf", input_path, "--outdir", tmpdir]
        else:
            # Comando nativo para Linux (Streamlit Cloud / Render)
            cmd = ["libreoffice", "--headless", "--convert-to", "pdf", input_path, "--outdir", tmpdir]
        
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e:
            # Fallback a 'soffice' genérico en Linux/Mac
            if platform.system() != "Windows":
                try:
                    cmd[0] = "soffice"
                    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                except Exception as inner_e:
                    raise RuntimeError(f"Error de conversión: LibreOffice no encontrado. Detalle: {inner_e}")
            else:
                raise RuntimeError(f"LibreOffice no se encontró en 'Program Files'. Instálalo o revisa la ruta. Detalle: {e}")
                
        pdf_path = os.path.join(tmpdir, "input.pdf")
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