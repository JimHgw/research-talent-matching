from backend.src.shared.validation import validator


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