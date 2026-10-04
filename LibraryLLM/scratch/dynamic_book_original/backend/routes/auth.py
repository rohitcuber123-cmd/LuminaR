from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from backend.utils.jwt_utils import create_access_token
from backend.services.auth_service import (
    register_user,
    verify_email_otp,
    resend_verification_otp,
    login_user
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    otp: str

class ResendVerificationRequest(BaseModel):
    email: EmailStr

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


@router.post("/verify-email")
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
        "user": result
    }
@router.post("/resend-verification")
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
        "user": user
    }
@router.post("/login")
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