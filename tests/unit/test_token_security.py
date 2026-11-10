from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token


class TestTokenSecurity:
    def test_existing_hs256_wire_format_and_session_claims_remain_compatible(self):
        subject, session = str(uuid4()), str(uuid4())
        payload = {
            "sub": subject,
            "sid": session,
            "aud": "admin",
            "exp": datetime.now(UTC) + timedelta(minutes=1),
        }
        # A standards-compatible token signed independently of the application's issuer.
        token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
        claims = decode_access_token(token)
        assert claims["sub"] == subject
        assert claims["sid"] == session

    @pytest.mark.parametrize("missing", ["exp", "aud", "sub"])
    def test_required_claims_cannot_be_omitted(self, missing):
        payload = {
            "sub": str(uuid4()),
            "aud": "admin",
            "exp": datetime.now(UTC) + timedelta(minutes=1),
        }
        del payload[missing]
        token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
        with pytest.raises(jwt.MissingRequiredClaimError, match=missing):
            decode_access_token(token)

    def test_customer_audience_is_rejected_at_staff_boundary(self):
        token = create_access_token(str(uuid4()), audience="customer")
        with pytest.raises(jwt.InvalidAudienceError, match="Audience"):
            decode_access_token(token)
