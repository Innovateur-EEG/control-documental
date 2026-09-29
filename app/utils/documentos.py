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