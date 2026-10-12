"""Read text from original uploaded documents."""

from pypdf import PdfReader
from docx import Document as DocxDocument
from docx.table import Table
from docx.text.paragraph import Paragraph


def extract_pdf_text(path):
    parts = []

    with path.open("rb") as stream:
        reader = PdfReader(stream, strict=True)

        for page in reader.pages:
            text = page.extract_text() or ""
            parts.append(text)

    return "\n".join(parts).strip()

def extract_docx_text(path):
    parts = []

    with path.open("rb") as stream:
        document = DocxDocument(stream)

        for block in document.iter_inner_content():
            if isinstance(block, Paragraph):
                parts.append(block.text)

            elif isinstance(block, Table):
                for row in block.rows:
                    cells = []

                    for cell in row.cells:
                        cells.append(cell.text.strip())

                    parts.append("\t".join(cells))

    return "\n".join(parts).strip()

def extract_document_text(path, media_type):
    if media_type == "application/pdf":
        return extract_pdf_text(path)

    if media_type == (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ):
        return extract_docx_text(path)

    raise ValueError("Unsupported document media type.")