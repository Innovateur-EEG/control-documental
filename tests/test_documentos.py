"""Regression tests for Word template rendering."""
from io import BytesIO

from docx import Document

from app.utils.documentos import procesar_word


def test_procesar_word_renders_docx_with_custom_jinja_filters():
    source = Document()
    source.add_paragraph("Hola {{ nombre }} {{ estado | mark('Activo') }}")
    input_bytes = BytesIO()
    source.save(input_bytes)

    rendered_bytes = procesar_word(
        input_bytes.getvalue(),
        {"nombre": "Natalia", "estado": "Activo"},
    )
    rendered = Document(BytesIO(rendered_bytes))
    text = "\n".join(paragraph.text for paragraph in rendered.paragraphs)

    assert "Hola Natalia X" in text

def test_procesar_excel_renders_saved_capture_values_and_preserves_workbook_structure():
    from openpyxl import Workbook, load_workbook

    source = Workbook()
    sheet = source.active
    sheet.title = "Captura"
    sheet["A1"] = "Nombre: {{ nombre }}"
    sheet["B2"] = "{{ estado }}"
    sheet["C3"] = 42
    sheet["D4"] = "=1+1"
    sheet["A1"].number_format = "@"
    extra = source.create_sheet("Anexo")
    extra["A1"] = "Valor: {{ importe }}"

    input_bytes = BytesIO()
    source.save(input_bytes)

    rendered_bytes = procesar_excel(
        input_bytes.getvalue(),
        {"nombre": "Persona de prueba", "estado": "Activo", "importe": "125.50"},
    )
    rendered = load_workbook(BytesIO(rendered_bytes), data_only=False)

    assert rendered.sheetnames == ["Captura", "Anexo"]
    assert rendered["Captura"]["A1"].value == "Nombre: Persona de prueba"
    assert rendered["Captura"]["B2"].value == "Activo"
    assert rendered["Captura"]["C3"].value == 42
    assert rendered["Captura"]["D4"].value == "=1+1"
    assert rendered["Captura"]["A1"].number_format == "@"
    assert rendered["Anexo"]["A1"].value == "Valor: 125.50"
