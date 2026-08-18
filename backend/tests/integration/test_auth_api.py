"""Интеграционные тесты аутентификации (/auth/login, /auth/me)."""

import uuid

import jwt
import pytest

from app.core.config import get_settings

pytestmark = pytest.mark.integration


class TestLogin:
    async def test_login_creates_new_user_and_returns_token(self, client):
        # Arrange
        username = f"login_qa_{uuid.uuid4().hex[:8]}"

        # Act
        response = await client.post("/auth/login", json={"username": username})

        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["user"]["username"] == username
        assert body["user"]["role"] == "customer"
        payload = jwt.decode(body["access_token"], get_settings().jwt_secret, algorithms=[get_settings().jwt_alg])
        assert payload["username"] == username

    async def test_login_existing_user_returns_same_id(self, client):
        # Arrange
        username = f"repeat_qa_{uuid.uuid4().hex[:8]}"
        first = (await client.post("/auth/login", json={"username": username})).json()

        # Act
        second = await client.post("/auth/login", json={"username": username})

        # Assert
        assert second.status_code == 200
        assert second.json()["user"]["id"] == first["user"]["id"]

    async def test_login_requires_username(self, client):
        # Arrange / Act
        response = await client.post("/auth/login", json={})

        # Assert
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION"


class TestMe:
    async def test_me_with_valid_token(self, client, auth_headers, test_user):
        # Arrange — auth_headers содержит валидный JWT для test_user

        # Act
        response = await client.get("/auth/me", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        assert response.json()["user"]["id"] == str(test_user.id)

    async def test_me_without_token_is_401(self, client):
        # Arrange / Act
        response = await client.get("/auth/me")

        # Assert
        assert response.status_code == 401

    async def test_me_with_garbage_token_is_401(self, client):
        # Arrange
        headers = {"Authorization": "Bearer not-a-jwt"}

        # Act
        response = await client.get("/auth/me", headers=headers)

        # Assert
        assert response.status_code == 401

    async def test_me_with_token_of_missing_user_is_401(self, client):
        # Arrange
        from app.core.security import create_access_token

        ghost_token = create_access_token(uuid.uuid4(), "ghost", "customer")

        # Act
        response = await client.get("/auth/me", headers={"Authorization": f"Bearer {ghost_token}"})

        # Assert
        assert response.status_code == 401
