from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.utils.jwt_utils import decode_access_token


security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials

    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    return payload


def require_roles(*allowed_roles):

    """Deprecated: User.role never grants tenant or platform management authority."""
    def denied(current_user=Depends(get_current_user)):
        raise HTTPException(403, "Legacy account roles do not grant management authority.")
    return denied
