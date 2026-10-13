"""Read and validate document upload requests."""

from flask import request
from werkzeug.exceptions import RequestEntityTooLarge
from io import BytesIO
from pathlib import PurePath

from pypdf import PdfReader
from pypdf.errors import PyPdfError
from zipfile import BadZipFile, ZipFile
from zlib import error as ZlibError

from docx import Document as DocxDocument
from lxml.etree import XMLSyntaxError

from ...shared.validation import ApiError, invalid


MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_REQUEST_BYTES = MAX_FILE_BYTES + 1024 * 1024
MAX_DOCX_EXPANDED_BYTES = 50 * 1024 * 1024


def read_upload():
    # Uploads contain binary files, so they use multipart/form-data.
    if request.mimetype != "multipart/form-data":
        raise ApiError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "Use multipart/form-data.",
        )

    # Allow space for the file and multipart form overhead.
    request.max_content_length = MAX_REQUEST_BYTES

    try:
        files = request.files
        form = request.form
    except RequestEntityTooLarge:
        raise ApiError(
            413,
            "UPLOAD_TOO_LARGE",
            "The upload request is too large.",
        ) from None

    # Exactly one file field is allowed.
    if set(files) != {"file"} or len(files.getlist("file")) != 1:
        invalid("file", "Upload exactly one file.")

    # Exactly one kind field is allowed.
    if set(form) != {"kind"} or len(form.getlist("kind")) != 1:
        invalid("kind", "Submit exactly one kind field.")

    kind = form["kind"]

    if kind not in ("CV", "TRANSCRIPT"):
        invalid("kind", "Choose CV or TRANSCRIPT.")

    upload = files["file"]

    # Keep only the file name, without any directory information.
    file_name = (
        (upload.filename or "")
        .replace("\\", "/")
        .rsplit("/", 1)[-1]
        .strip()
    )

    if not file_name:
        invalid("file", "Provide a file name.")

    # Read one extra byte so oversized files can be detected.
    content = upload.stream.read(MAX_FILE_BYTES + 1)

    if not content:
        invalid("file", "Upload a non-empty file.")

    if len(content) > MAX_FILE_BYTES:
        raise ApiError(
            413,
            "UPLOAD_TOO_LARGE",
            "The file must not exceed 10 MiB.",
        )

    return file_name, kind, content

def validate_pdf(content):
    if not content.startswith(b"%PDF-"):
        raise ApiError(
            415,
            "UNSUPPORTED_FILE_TYPE",
            "Upload a valid PDF file.",
        )
    try:
        reader = PdfReader(BytesIO(content), strict=True)
        encrypted = reader.is_encrypted
        if not encrypted:
            len(reader.pages)
    except (
        PyPdfError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        RecursionError,
    ):
        raise ApiError(
            415,
            "UNSUPPORTED_FILE_TYPE",
            "The PDF could not be read. Upload a valid PDF file.",
        ) from None
    
    if encrypted:
        invalid(
            "file",
            "Upload a PDF without password protection.",
        )

    return "application/pdf"

def validate_docx(content):
    try:
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            names = {entry.filename for entry in entries}

            required = {
                "[Content_Types].xml",
                "_rels/.rels",
                "word/document.xml",
            }
            if not required.issubset(names):
                raise ValueError("Missing document parts")
            if len(names) != len(entries):
                raise ValueError("Duplicate document parts")

            expanded_size = sum(entry.file_size for entry in entries)
            if expanded_size > MAX_DOCX_EXPANDED_BYTES:
                invalid(
                    "file",
                    "The expanded DOCX content is too large.",
                )
            if archive.testzip() is not None:
                raise BadZipFile("Corrupted document part")
            document = DocxDocument(BytesIO(content))
        len(document.paragraphs)
        len(document.tables)
    except (
        BadZipFile,
        XMLSyntaxError,
        ZlibError,
        KeyError,
        ValueError,
        TypeError,
        AttributeError,
        RuntimeError,
        NotImplementedError,
        OSError,
    ):
        raise ApiError(
            415,
            "UNSUPPORTED_FILE_TYPE",
            "The DOCX could not be read. Upload a valid DOCX file.",
        ) from None

    return (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    )

def validate_file(file_name, content):
    extension = PurePath(file_name).suffix.lower()

    if extension == ".pdf":
        return validate_pdf(content)

    if extension == ".docx":
        return validate_docx(content)

    raise ApiError(
        415,
        "UNSUPPORTED_FILE_TYPE",
        "Upload a PDF or DOCX file.",
    )