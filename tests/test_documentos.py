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
