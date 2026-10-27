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
    document = DocxDocument(path)
    word = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    markup = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"

    def read(node):
        if node.tag == markup + "AlternateContent":
            choices = [
                child for child in node
                if child.tag == markup + "Choice"
            ]
            fallbacks = [
                child for child in node
                if child.tag == markup + "Fallback"
            ]
            selected = choices or fallbacks
            return read(selected[0]) if selected else ""

        if node.tag == word + "t":
            return node.text or ""

        if node.tag == word + "noBreakHyphen":
            return "-"

        if node.tag == word + "tab":
            return "\t"

        if node.tag in (word + "br", word + "cr"):
            return "\n"

        if node.tag == word + "tr":
            return "\t".join(
                read(cell).strip()
                for cell in node
                if cell.tag == word + "tc"
            ) + "\n"

        content = "".join(read(child) for child in node)

        if node.tag == word + "txbxContent":
            return "\n" + content + "\n"

        if node.tag == word + "p":
            return content + "\n"

        return content

    return read(document.element.body).strip()

def extract_document_text(path, media_type):
    if media_type == "application/pdf":
        return extract_pdf_text(path)

    if media_type == (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ):
        return extract_docx_text(path)

    raise ValueError("Unsupported document media type.")
