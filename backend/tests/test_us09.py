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

    # Download the original PDF through the API.
    document_id = data["id"]

    with client.get(
        f"/api/v1/me/documents/{document_id}/file"
    ) as download:
        assert download.status_code == 200, download.get_json()

        # The downloaded bytes must match the uploaded file.
        assert download.data == content
        assert download.mimetype == "application/pdf"

        disposition = download.headers["Content-Disposition"]
        assert disposition.startswith("attachment;")
        assert "test-cv.pdf" in disposition

        assert download.headers["Cache-Control"] == "no-store"
        assert download.headers["X-Content-Type-Options"] == "nosniff"

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

    # Download the original Word document through the API.
    document_id = data["id"]

    with client.get(
        f"/api/v1/me/documents/{document_id}/file"
    ) as download:
        assert download.status_code == 200, download.get_json()

        assert download.data == content
        assert download.mimetype == (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        )

        disposition = download.headers["Content-Disposition"]
        assert disposition.startswith("attachment;")
        assert "test-transcript.docx" in disposition

        assert download.headers["Cache-Control"] == "no-store"
        assert download.headers["X-Content-Type-Options"] == "nosniff"

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

@pytest.mark.parametrize(
    "document_status",
    ["QUEUED", "PROCESSING", "READY", "FAILED"],
)
def test_document_status_returns_current_state(
    app, signed, document_status
):
    client, _ = signed

    response = client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    before = response.get_json()

    # Only a failed document has error information.
    error = None

    if document_status == "FAILED":
        error = {
            "code": "EXTRACTION_FAILED",
            "message": "The document could not be processed.",
            "fieldErrors": [],
        }

    # Prepare a document in the state being tested.
    with app.extensions["database"].transaction(write=True) as db:
        db.add(
            Document(
                id="doc_status",
                talent_id=before["talentId"],
                kind="CV",
                file_name="status-test.pdf",
                media_type="application/pdf",
                storage_key="test/status-test.pdf",
                size_bytes=128,
                status=document_status,
                error=error,
            )
        )

    response = client.get("/api/v1/me/documents/doc_status")

    assert response.status_code == 200, response.get_json()

    data = response.get_json()
    validator("Document").validate(data)

    assert data["id"] == "doc_status"
    assert data["fileName"] == "status-test.pdf"
    assert data["status"] == document_status
    assert data["error"] == error

    # Reading document status must not change the profile.
    response = client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == before

@pytest.mark.parametrize("suffix", ["", "/extraction"])
@pytest.mark.parametrize(
    "email, status, code",
    [
        (None, 401, "UNAUTHENTICATED"),
        ("team@example.test", 403, "FORBIDDEN"),
        ("other@example.test", 404, "NOT_FOUND"),
    ],
)
def test_document_read_endpoints_reject_unauthorized_access(
    app, signed, email, status, code, suffix
):
    owner_client, _ = signed

    response = owner_client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    profile = response.get_json()

    # Prepare a document owned by the first talent.
    with app.extensions["database"].transaction(write=True) as db:
        db.add(
            Document(
                id="doc_private",
                talent_id=profile["talentId"],
                kind="CV",
                file_name="private-cv.pdf",
                media_type="application/pdf",
                storage_key="test/private-cv.pdf",
                size_bytes=128,
                status="QUEUED",
            )
        )

    # Use a separate client for the person requesting access.
    requester = app.test_client()

    if email is not None:
        sign_in(requester, email)

    response = requester.get(
        f"/api/v1/me/documents/doc_private{suffix}"
    )

    assert response.status_code == status, response.get_json()

    data = response.get_json()
    validator("Error").validate(data)
    assert data["error"]["code"] == code

    # The owner should still be able to read the document.
    response = owner_client.get("/api/v1/me/documents/doc_private")
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["status"] == "QUEUED"

@pytest.mark.parametrize(
    "suffix", ["", "/file", "/extraction"]
)
@pytest.mark.parametrize(
    "document_id, status, code",
    [
        ("doc_missing", 404, "NOT_FOUND"),
        ("bad.id", 422, "VALIDATION_ERROR"),
        ("x" * 65, 422, "VALIDATION_ERROR"),
    ],
)
def test_document_endpoints_reject_missing_or_invalid_id(
    signed, document_id, status, code, suffix
):
    client, _ = signed

    response = client.get(
        f"/api/v1/me/documents/{document_id}{suffix}"
    )

    assert response.status_code == status, response.get_json()

    data = response.get_json()
    validator("Error").validate(data)
    assert data["error"]["code"] == code

    if status == 422:
        assert data["error"]["fieldErrors"][0]["field"] == "documentId"


@pytest.mark.parametrize(
    "email, status, code",
    [
        (None, 401, "UNAUTHENTICATED"),
        ("team@example.test", 403, "FORBIDDEN"),
        ("other@example.test", 404, "NOT_FOUND"),
    ],
)
def test_document_download_rejects_unauthorized_access(
    app, signed, tmp_path, email, status, code
):
    owner_client, csrf = signed
    app.config["DOCUMENT_STORAGE_DIR"] = str(
        tmp_path / "documents"
    )

    # Prepare a real PDF.
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(buffer)
    content = buffer.getvalue()

    # Upload as the document owner.
    response = owner_client.post(
        "/api/v1/me/documents",
        data={
            "kind": "CV",
            "file": (BytesIO(content), "private-cv.pdf"),
        },
        content_type="multipart/form-data",
        headers=headers(csrf),
    )
    assert response.status_code == 202, response.get_json()
    document_id = response.get_json()["id"]

    # A separate client has its own login session.
    requester = app.test_client()

    if email is not None:
        sign_in(requester, email)

    with requester.get(
        f"/api/v1/me/documents/{document_id}/file"
    ) as response:
        assert response.status_code == status, response.get_json()

        data = response.get_json()
        validator("Error").validate(data)
        assert data["error"]["code"] == code

    # The owner can still download the original file.
    with owner_client.get(
        f"/api/v1/me/documents/{document_id}/file"
    ) as response:
        assert response.status_code == 200, response.get_json()
        assert response.data == content

def test_document_download_returns_404_when_file_is_missing(
    app, signed, tmp_path
):
    client, _ = signed
    app.config["DOCUMENT_STORAGE_DIR"] = str(
        tmp_path / "documents"
    )

    response = client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    profile = response.get_json()

    # Create metadata without creating the actual file.
    with app.extensions["database"].transaction(write=True) as db:
        db.add(
            Document(
                id="doc_missing_file",
                talent_id=profile["talentId"],
                kind="CV",
                file_name="missing-cv.pdf",
                media_type="application/pdf",
                storage_key="missing-file-key",
                size_bytes=128,
                status="QUEUED",
            )
        )

    # The document record exists.
    response = client.get(
        "/api/v1/me/documents/doc_missing_file"
    )
    assert response.status_code == 200, response.get_json()

    # The original file does not exist.
    with client.get(
        "/api/v1/me/documents/doc_missing_file/file"
    ) as response:
        assert response.status_code == 404, response.get_json()

        data = response.get_json()
        validator("Error").validate(data)
        assert data["error"]["code"] == "NOT_FOUND"

def test_extraction_is_ready_after_worker_processes_docx(
    app, signed, tmp_path
):
    client, csrf = signed
    app.config["DOCUMENT_STORAGE_DIR"] = str(
        tmp_path / "documents"
    )

    response = client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    before = response.get_json()

    # Create a Word document containing supported text.
    buffer = BytesIO()
    document = DocxDocument()
    document.add_paragraph("Skills: Python, SQL")
    document.add_paragraph(
        "Research interests: Machine learning"
    )
    document.save(buffer)

    response = client.post(
        "/api/v1/me/documents",
        data={
            "kind": "CV",
            "file": (BytesIO(buffer.getvalue()), "test-cv.docx"),
        },
        content_type="multipart/form-data",
        headers=headers(csrf),
    )
    assert response.status_code == 202, response.get_json()
    document_id = response.get_json()["id"]
    url = f"/api/v1/me/documents/{document_id}/extraction"

    # The queued document has no extraction result yet.
    response = client.get(url)
    assert response.status_code == 409, response.get_json()
    error = response.get_json()
    validator("Error").validate(error)
    assert error["error"]["code"] == "EXTRACTION_NOT_READY"

    # Run the real worker command against the test database.
    command = app.test_cli_runner().invoke(
        args=["process-documents", "--once"]
    )
    assert command.exit_code == 0, command.output

    # The extraction result should now be available.
    response = client.get(url)
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    validator("Extraction").validate(result)

    assert result["documentId"] == document_id
    assert result["status"] == "READY"
    assert result["reviewRequired"] is True

    skills = result["suggestedSections"]["skills"]
    assert {skill["tagId"] for skill in skills} == {
        "skill_python",
        "skill_sql",
    }
    assert all(skill["claim"] == "HAS" for skill in skills)
    assert all(
        skill["evidenceText"] == "Skills: Python, SQL"
        for skill in skills
    )

    assert result["suggestedSections"]["researchInterests"] == [
        "interest_ml"
    ]

    # Extraction must not modify the profile.
    response = client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == before

@pytest.mark.parametrize(
    "document_status, http_status, code",
    [
        ("QUEUED", 409, "EXTRACTION_NOT_READY"),
        ("PROCESSING", 409, "EXTRACTION_NOT_READY"),
        ("FAILED", 422, "EXTRACTION_FAILED"),
    ],
)
def test_extraction_rejects_unavailable_results(
    app, signed, document_status, http_status, code
):
    client, _ = signed

    response = client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    before = response.get_json()

    error = None

    if document_status == "FAILED":
        error = {
            "code": "EXTRACTION_FAILED",
            "message": "The document could not be processed.",
            "fieldErrors": [],
        }

    with app.extensions["database"].transaction(write=True) as db:
        db.add(
            Document(
                id="doc_extraction_state",
                talent_id=before["talentId"],
                kind="CV",
                file_name="state-test.pdf",
                media_type="application/pdf",
                storage_key="state-test-key",
                size_bytes=128,
                status=document_status,
                error=error,
            )
        )

    response = client.get(
        "/api/v1/me/documents/doc_extraction_state/extraction"
    )
    assert response.status_code == http_status, response.get_json()

    data = response.get_json()
    validator("Error").validate(data)
    assert data["error"]["code"] == code

    # A rejected request must leave the profile unchanged.
    response = client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == before