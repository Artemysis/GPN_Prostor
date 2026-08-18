"""Unit-тесты JWT-безопасности и генератора номеров заявок."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import create_access_token, decode_access_token
from app.utils.numbering import generate_request_number

pytestmark = pytest.mark.unit

settings = get_settings()


class TestAccessToken:
    def test_round_trip_preserves_claims(self):
        # Arrange
        user_id = uuid.uuid4()

        # Act
        token = create_access_token(user_id, "ivanov", "customer")
        payload = decode_access_token(token)

        # Assert
        assert payload["sub"] == str(user_id)
        assert payload["username"] == "ivanov"
        assert payload["role"] == "customer"

    def test_token_expiry_in_ttl_window(self):
        # Arrange
        user_id = uuid.uuid4()
        before = datetime.now(UTC)

        # Act
        token = create_access_token(user_id, "petrov", "customer")
        payload = decode_access_token(token)

        # Assert
        expected_exp = before + timedelta(hours=settings.jwt_ttl_hours)
        actual_exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
        assert abs((actual_exp - expected_exp).total_seconds()) < 60

    def test_expired_token_rejected(self):
        # Arrange
        user_id = uuid.uuid4()
        now = datetime.now(UTC)
        stale = jwt.encode(
            {"sub": str(user_id), "exp": now - timedelta(hours=1)},
            settings.jwt_secret,
            algorithm=settings.jwt_alg,
        )

        # Act / Assert
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_access_token(stale)

    def test_token_signed_with_wrong_secret_rejected(self):
        # Arrange
        user_id = uuid.uuid4()
        forged = jwt.encode({"sub": str(user_id)}, "another-secret", algorithm=settings.jwt_alg)

        # Act / Assert
        with pytest.raises(jwt.PyJWTError):
            decode_access_token(forged)


class TestRequestNumber:
    def test_format_contains_current_year(self):
        # Arrange
        year = datetime.now(UTC).year

        # Act
        number = generate_request_number()

        # Assert
        assert number == f"REQ-{year}-{int(number.split('-')[2]):06d}"
        suffix = int(number.split("-")[2])
        assert 0 <= suffix <= 999999

    def test_numbers_are_six_digit_padded(self):
        # Arrange / Act
        number = generate_request_number()

        # Assert
        assert len(number.split("-")[2]) == 6
