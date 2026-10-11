from backend.src.shared.validation import validator
from backend.src.db.models import Document
from backend.tests.conftest import headers, sign_in
from datetime import datetime
from io import BytesIO
from docx import Document as DocxDocument

from sqlalchemy import select

from pypdf import PdfWriter
import pytest

def test_document_list_is_empty_for_new_talent(signed):
    client, _ = signed

    response = client.get("/api/v1/me/documents")

    assert response.status_code == 200, response.get_json()
    data = response.get_json()
    validator("DocumentPage").validate(data)

    assert data == {
        "items": [],
        "page": 1,
        "pageSize": 20,
        "total": 0,
    }

def test_document_list_only_returns_owned_documents(app, signed):
    client, _ = signed

    # Get the signed-in user's profile.
    response = client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    own_profile = response.get_json()

    # Sign in another user using a separate client.
    other_client = app.test_client()
    sign_in(other_client, "other@example.test")
    response = other_client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    other_profile = response.get_json()

    # Add one document for each user to the test database.
    with app.extensions["database"].transaction(write=True) as db:
        db.add(
            Document(
                id="doc_own",
                talent_id=own_profile["talentId"],
                kind="CV",
                file_name="my-cv.pdf",
                media_type="application/pdf",
                storage_key="test/own-cv.pdf",
                size_bytes=128,
                status="QUEUED",
            )
        )

        db.add(
            Document(
                id="doc_other",
                talent_id=other_profile["talentId"],
                kind="CV",
                file_name="other-cv.pdf",
                media_type="application/pdf",
                storage_key="test/other-cv.pdf",
                size_bytes=128,
                status="QUEUED",
            )
        )

    # Request the list as the first user.
    response = client.get("/api/v1/me/documents")
    assert response.status_code == 200, response.get_json()
    data = response.get_json()
    validator("DocumentPage").validate(data)

     # Only the first user's document should be returned.
    assert data["total"] == 1
    assert len(data["items"]) == 1

    document = data["items"][0]
    assert document["id"] == "doc_own"
    assert document["fileName"] == "my-cv.pdf"
    assert document["mediaType"] == "application/pdf"
    assert document["status"] == "QUEUED"

def test_document_list_pagination_and_order(app, signed):
    client, _ = signed

    response = client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    profile = response.get_json()

    documents = [
        ("doc_a", datetime(2026, 1, 1)),
        ("doc_b", datetime(2026, 1, 2)),
        ("doc_c", datetime(2026, 1, 2)),
    ]

    with app.extensions["database"].transaction(write=True) as db:
        for document_id, created_at  in documents:
            db.add(
                Document(
                    id=document_id,
                    talent_id=profile["talentId"],
                    kind="CV",
                    file_name=f"{document_id}.pdf",
                    media_type="application/pdf",
                    storage_key=f"test/{document_id}.pdf",
                    size_bytes=128,
                    status="QUEUED",
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
    expected_pages = [
        (1, ["doc_b", "doc_c"]),
        (2, ["doc_a"]),
        (3, []),
        (10**30, []),
    ]

    for page, expected_ids in expected_pages:
        response = client.get(
            f"/api/v1/me/documents?page={page}&pageSize=2"
        )
        assert response.status_code == 200, response.get_json()
        data = response.get_json()

        validator("DocumentPage").validate(data)
        assert data["page"] == page
        assert data["pageSize"] == 2
        assert data["total"] == 3

        actual_ids = [
            document["id"]
            for document in data["items"]
        ]
        assert actual_ids == expected_ids

def test_document_list_requires_login(client):
    response = client.get("/api/v1/me/documents")

    assert response.status_code == 401, response.get_json()

    data = response.get_json()
    validator("Error").validate(data)
    assert data["error"]["code"] == "UNAUTHENTICATED"


def test_document_list_rejects_research_team(client):
    sign_in(client, "team@example.test")

    response = client.get("/api/v1/me/documents")

    assert response.status_code == 403, response.get_json()

    data = response.get_json()
    validator("Error").validate(data)
    assert data["error"]["code"] == "FORBIDDEN"

@pytest.mark.parametrize(
    "query, field",
    [
        ("page=0", "page"),
        ("page=abc", "page"),
        ("pageSize=101", "pageSize"),
        ("page=1&page=2", "page"),
    ],
)
def test_document_list_rejects_invalid_pagination(signed, query, field):
    client, _ = signed

    response = client.get(f"/api/v1/me/documents?{query}")

    assert response.status_code == 422, response.get_json()

    data = response.get_json()
    validator("Error").validate(data)

    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert data["error"]["fieldErrors"][0]["field"] == field

def test_upload_pdf_saves_file_without_changing_profile(
    app, signed, tmp_path
):
    client, csrf = signed
    storage_dir = tmp_path / "documents"
    app.config["DOCUMENT_STORAGE_DIR"] = str(storage_dir)

    # Save the profile before uploading.
    response = client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    before = response.get_json()

    # Create a real PDF containing one blank page.
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(buffer)
    content = buffer.getvalue()

    # Upload the PDF through the API.
    response = client.post(
        "/api/v1/me/documents",
        data={
            "kind": "CV",
            "file": (BytesIO(content), "test-cv.pdf"),
        },
        content_type="multipart/form-data",
        headers=headers(csrf),
    )
    assert response.status_code == 202, response.get_json()
    data = response.get_json()
    validator("Document").validate(data)

    assert data["fileName"] == "test-cv.pdf"
    assert data["kind"] == "CV"
    assert data["mediaType"] == "application/pdf"
    assert data["sizeBytes"] == len(content)
    assert data["status"] == "QUEUED"
    assert data["error"] is None

    # Check ownership and the original file saved on disk.
    with app.extensions["database"].transaction() as db:
        document = db.get(Document, data["id"])

        assert document is not None
        assert document.talent_id == before["talentId"]

        saved_path = storage_dir / document.storage_key
        assert saved_path.read_bytes() == content

    # Uploading must leave the entire profile unchanged.
    response = client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == before

def test_upload_docx_saves_file_without_changing_profile(
    app, signed, tmp_path
):
    client, csrf = signed

    storage_dir = tmp_path / "documents"
    app.config["DOCUMENT_STORAGE_DIR"] = str(storage_dir)

    response = client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    before = response.get_json()

    # Create a real Word document.
    buffer = BytesIO()
    word_document = DocxDocument()
    word_document.add_paragraph("Synthetic transcript")
    word_document.save(buffer)
    content = buffer.getvalue()

    response = client.post(
        "/api/v1/me/documents",
        data={
            "kind": "TRANSCRIPT",
            "file": (BytesIO(content), "test-transcript.docx"),
        },
        content_type="multipart/form-data",
        headers=headers(csrf),
    )

    assert response.status_code == 202, response.get_json()

    data = response.get_json()
    validator("Document").validate(data)

    assert data["fileName"] == "test-transcript.docx"
    assert data["kind"] == "TRANSCRIPT"
    assert data["mediaType"] == (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    )
    assert data["sizeBytes"] == len(content)
    assert data["status"] == "QUEUED"
    assert data["error"] is None

    with app.extensions["database"].transaction() as db:
        document = db.get(Document, data["id"])

        assert document is not None
        assert document.talent_id == before["talentId"]

        saved_path = storage_dir / document.storage_key
        assert saved_path.read_bytes() == content

    response = client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == before

@pytest.mark.parametrize(
    "email, valid_csrf, status, code",
    [
        (None, True, 401, "UNAUTHENTICATED"),
        ("team@example.test", True, 403, "FORBIDDEN"),
        ("talent@example.test", False, 403, "CSRF_INVALID"),
    ],
)
def test_upload_rejects_unauthorized_requests(
    app, client, tmp_path, email, valid_csrf, status, code
):
    storage_dir = tmp_path / "documents"
    app.config["DOCUMENT_STORAGE_DIR"] = str(storage_dir)

    # Prepare login and request headers for this case.
    request_headers = {}

    if email is not None:
        csrf = sign_in(client, email)
        request_headers = headers(csrf)

        if not valid_csrf:
            request_headers["X-CSRF-Token"] = "invalid-token"

    # Use a valid PDF so the test focuses on permissions.
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(buffer)

    response = client.post(
        "/api/v1/me/documents",
        data={
            "kind": "CV",
            "file": (BytesIO(buffer.getvalue()), "test-cv.pdf"),
        },
        content_type="multipart/form-data",
        headers=request_headers,
    )

    assert response.status_code == status, response.get_json()

    data = response.get_json()
    validator("Error").validate(data)
    assert data["error"]["code"] == code

    # Rejected uploads must not create files or database records.
    assert list(storage_dir.glob("*")) == []

    with app.extensions["database"].transaction() as db:
        assert db.scalars(select(Document)).all() == []

@pytest.mark.parametrize(
    "kind, file_name, content, status, code",
    [
        ("CV", None, None, 422, "VALIDATION_ERROR"),
        ("CV", "empty.pdf", b"", 422, "VALIDATION_ERROR"),
        ("OTHER", "cv.pdf", b"example", 422, "VALIDATION_ERROR"),
        ("CV", "fake.pdf", b"ordinary text", 415, "UNSUPPORTED_FILE_TYPE"),
        ("CV", "fake.docx", b"ordinary text", 415, "UNSUPPORTED_FILE_TYPE"),
        ("CV", "old.doc", b"example", 415, "UNSUPPORTED_FILE_TYPE"),
        (
            "CV",
            "large.pdf",
            b"x" * (10 * 1024 * 1024 + 1),
            413,
            "UPLOAD_TOO_LARGE",
        ),
    ],
    ids=[
        "missing-file",
        "empty-file",
        "invalid-kind",
        "fake-pdf",
        "fake-docx",
        "legacy-doc",
        "oversized-file",
    ],
)
def test_upload_rejects_invalid_content(
    app, signed, tmp_path, kind, file_name, content, status, code
):
    client, csrf = signed

    storage_dir = tmp_path / "documents"
    app.config["DOCUMENT_STORAGE_DIR"] = str(storage_dir)

    response = client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    before = response.get_json()

    upload_data = {"kind": kind}

    # Leave out the file field in the missing-file case.
    if file_name is not None:
        upload_data["file"] = (BytesIO(content), file_name)

    response = client.post(
        "/api/v1/me/documents",
        data=upload_data,
        content_type="multipart/form-data",
        headers=headers(csrf),
    )

    assert response.status_code == status, response.get_json()

    data = response.get_json()
    validator("Error").validate(data)
    assert data["error"]["code"] == code

    # A rejected upload must leave no stored documents.
    assert list(storage_dir.glob("*")) == []

    with app.extensions["database"].transaction() as db:
        assert db.scalars(select(Document)).all() == []

    response = client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == before