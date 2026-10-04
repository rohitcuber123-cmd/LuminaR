from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator
from backend.services.identity_service import STAFF_ROLES
from backend.utils.auth_rate_limit import limit_auth_attempts
from backend.utils.security_audit import security_event
from backend.utils.jwt_utils import create_access_token
from backend.services.auth_service import (
    register_user,
    verify_email_otp,
    resend_verification_otp,
    login_user
)
from backend.services.auth_service import complete_staff_setup

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

class CredentialRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    @field_validator('email', mode='before', check_fields=False)
    @classmethod
    def trim_email(cls, value):
        return value.strip() if isinstance(value, str) else value

class LoginRequest(CredentialRequest):
    email: EmailStr
    password: str

class RegisterRequest(CredentialRequest):
    name: str
    email: EmailStr
    password: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    otp: str

class ResendVerificationRequest(BaseModel):
    email: EmailStr

class StaffSetupRequest(CredentialRequest):
    email: EmailStr
    otp: str
    password: str

@router.post('/staff-setup', dependencies=[Depends(limit_auth_attempts)])
def staff_setup(request: StaffSetupRequest):
    if len(request.otp) != 6 or not request.otp.isascii() or not request.otp.isdigit():
        raise HTTPException(400, 'Invalid or expired setup code.')
    try:
        return complete_staff_setup(request.email, request.otp, request.password)
    except ValueError as error:
        raise HTTPException(400, str(error))

@router.post("/register")
def register(request: RegisterRequest):

    if len(request.password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=400,
            detail="Password is too long"
        )

    if len(request.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least 8 characters"
        )

    try:

        user = register_user(
            request.name,
            request.email,
            request.password
        )

    except RuntimeError as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )

    if user is None:

        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )

    return {
        "message": "User registered successfully",
        "user": user
    }


@router.post("/verify-email", dependencies=[Depends(limit_auth_attempts)])
def verify_email(request: VerifyEmailRequest):

    if not request.otp.isdigit() or len(request.otp) != 6:

        raise HTTPException(
            status_code=400,
            detail="OTP must be a 6-digit number"
        )

    try:

        result = verify_email_otp(
            request.email,
            request.otp
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    if result is None:

        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code"
        )

    return {
        "message": "Email verified successfully",
        "user": {"is_email_verified": True}
    }
@router.post("/resend-verification", dependencies=[Depends(limit_auth_attempts)])
def resend_verification(request: ResendVerificationRequest):

    try:

        user = resend_verification_otp(
            request.email
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except RuntimeError as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )

    if user is None:

        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return {
        "message": "A new verification code has been sent",
        "user": {"is_email_verified": False}
    }
@router.post("/login", dependencies=[Depends(limit_auth_attempts)])
def login(request: LoginRequest):

    try:

        user = login_user(
            request.email,
            request.password
        )

    except ValueError as error:

        raise HTTPException(
            status_code=403,
            detail=str(error)
        )

    if user is None:

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    access_token = create_access_token(
        user_id=user["user_id"],
        email=user["email"],
        role=user["role"]
    )

    return {
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.post('/staff-login', dependencies=[Depends(limit_auth_attempts)])
def staff_login(request: LoginRequest):
    try:
        user = login_user(request.email, request.password)
    except ValueError:
        security_event('staff_login_failure')
        raise HTTPException(403, 'This account is not authorized for staff access.')
    if user is None:
        security_event('staff_login_failure')
        raise HTTPException(401, 'Invalid email or password')
    if user['role'] not in STAFF_ROLES:
        security_event('staff_login_failure')
        raise HTTPException(403, 'This account is not authorized for staff access.')
    token = create_access_token(user['user_id'], user['email'], user['role'])
    security_event('staff_login_success', actor_id=user['user_id'])
    return {'message':'Login successful', 'access_token':token, 'token_type':'bearer', 'user':user}
