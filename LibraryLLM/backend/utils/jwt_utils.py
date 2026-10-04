import os
from uuid import uuid4

from datetime import datetime, timedelta, timezone

from jose import jwt
from dotenv import load_dotenv


load_dotenv()


JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

JWT_ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 60


def create_access_token(user_id, email, role):

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=30 if role in ('ADMIN', 'LIBRARIAN') else ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "sid": uuid4().hex,
        "iat": datetime.now(timezone.utc),
        "exp": expire
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM
    )


def decode_access_token(token):

    try:

        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={'require_exp': True, 'require_sub': True},
        )

        from backend.services.identity_service import current_identity
        from backend.services.login_sessions import is_revoked
        if is_revoked(payload.get('sid')):
            return None
        return current_identity(payload)

    except Exception:

        return None
