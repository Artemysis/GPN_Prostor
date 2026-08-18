"""Интеграционные тесты документов: загрузка вложений (MinIO замокан), метаданные, удаление."""

import io
import uuid

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
async def existing_request(client) -> dict:
    return (await client.post("/requests", json={"title": "Заявка с вложениями"})).json()


class TestUploadAttachment:
    async def test_upload_creates_document_and_stores_object(self, client, existing_request, mock_minio):
        # Arrange
        request_id = existing_request["id"]
        file_bytes = b"%PDF-1.4 fake report content"

        # Act
        response = await client.post(
            f"/requests/{request_id}/attachments",
            data={"kind": "attachment"},
            files={"file": ("отчёт.pdf", io.BytesIO(file_bytes), "application/pdf")},
        )

        # Assert
        assert response.status_code == 201
        doc = response.json()
        assert doc["kind"] == "attachment"
        assert doc["filename"] == "отчёт.pdf"
        assert doc["size_bytes"] == len(file_bytes)
        stored_keys = [k for k in mock_minio.uploaded if k.startswith(f"attachments/{request_id}/")]
        assert len(stored_keys) == 1
        assert mock_minio.uploaded[stored_keys[0]] == file_bytes

    async def test_upload_to_missing_request_is_404(self, client, mock_minio):
        # Arrange / Act
        response = await client.post(
            f"/requests/{uuid.uuid4()}/attachments",
            data={"kind": "attachment"},
            files={"file": ("x.txt", io.BytesIO(b"data"), "text/plain")},
        )

        # Assert
        assert response.status_code == 404
        assert mock_minio.uploaded == {}


class TestDocumentMetadata:
    async def test_list_attachments_excludes_export_kind(self, client, existing_request, mock_minio):
        # Arrange
        request_id = existing_request["id"]
        uploaded = (
            await client.post(
                f"/requests/{request_id}/attachments",
                data={"kind": "attachment"},
                files={"file": ("a.txt", io.BytesIO(b"a"), "text/plain")},
            )
        ).json()

        # Act
        response = await client.get(f"/requests/{request_id}/attachments")

        # Assert
        assert response.status_code == 200
        ids = [d["id"] for d in response.json()]
        assert uploaded["id"] in ids
        assert all(d["kind"] != "tz_final" for d in response.json())

    async def test_document_detail_contains_presigned_url(self, client, existing_request, mock_minio):
        # Arrange
        uploaded = (
            await client.post(
                f"/requests/{existing_request['id']}/attachments",
                data={"kind": "attachment"},
                files={"file": ("b.pdf", io.BytesIO(b"b"), "application/pdf")},
            )
        ).json()

        # Act
        response = await client.get(f"/documents/{uploaded['id']}")

        # Assert
        assert response.status_code == 200
        detail = response.json()
        assert detail["presigned_url"].startswith("http://minio.test/")
        assert detail["expires_in"] == 900

    async def test_download_redirects_to_presigned_url(self, client, existing_request, mock_minio):
        # Arrange
        uploaded = (
            await client.post(
                f"/requests/{existing_request['id']}/attachments",
                data={"kind": "attachment"},
                files={"file": ("c.pdf", io.BytesIO(b"c"), "application/pdf")},
            )
        ).json()

        # Act
        response = await client.get(f"/documents/{uploaded['id']}/download")

        # Assert
        assert response.status_code == 302
        assert response.headers["location"].startswith("http://minio.test/")


class TestDeleteAttachment:
    async def test_delete_removes_row_and_object(self, client, existing_request, mock_minio):
        # Arrange
        request_id = existing_request["id"]
        uploaded = (
            await client.post(
                f"/requests/{request_id}/attachments",
                data={"kind": "attachment"},
                files={"file": ("d.txt", io.BytesIO(b"d"), "text/plain")},
            )
        ).json()

        # Act
        deleted = await client.delete(f"/requests/{request_id}/attachments/{uploaded['id']}")
        fetched = await client.get(f"/documents/{uploaded['id']}")

        # Assert
        assert deleted.status_code == 204
        assert fetched.status_code == 404
        remaining = [k for k in mock_minio.deleted if k.startswith(f"attachments/{request_id}/")]
        assert remaining  # объект удалён из хранилища

    async def test_get_missing_document_is_404(self, client):
        # Arrange / Act
        response = await client.get(f"/documents/{uuid.uuid4()}")

        # Assert
        assert response.status_code == 404
