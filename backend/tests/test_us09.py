from backend.src.shared.validation import validator
from backend.src.db.models import Document
from backend.tests.conftest import sign_in
from datetime import datetime
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