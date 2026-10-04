import bcrypt
from pymongo.errors import DuplicateKeyError
from backend.services.identity_service import (
    READER_ROLE, ROLES, find_user_by_email, email_exists, normalize_email,
    next_user_id, public_user,
)

from datetime import datetime, timedelta, timezone

from backend.database.mongodb import (
    users_collection,
    email_verifications_collection
)

from backend.services.email_service import (
    generate_otp,
    send_otp_email
)


def hash_password(password):

    password_bytes = password.encode("utf-8")

    if len(password_bytes) > 72:
        raise ValueError(
            "Password must not exceed 72 bytes"
        )

    return bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt()
    ).decode("utf-8")


def hash_otp(otp):

    return bcrypt.hashpw(
        otp.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")


def get_next_user_id():
    return next_user_id()


def register_user(name, email, password):
    email = normalize_email(email)
    if email_exists(email):
        return None

    password_hash = hash_password(password)

    user_id = get_next_user_id()

    user_document = {
        "user_id": user_id,
        "name": name,
        "email": email,
        "password_hash": password_hash,
        "role": READER_ROLE,
        "is_email_verified": False,
        "created_at": datetime.now(timezone.utc)
    }

    try:
        users_collection.insert_one(user_document)
    except DuplicateKeyError:
        return None

    otp = generate_otp()
    otp_hash = hash_otp(otp)

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(minutes=10)
    )

    email_verifications_collection.insert_one({
        "user_id": user_id,
        "otp_hash": otp_hash,
        "expires_at": expires_at,
        "attempts": 0,
        "created_at": datetime.now(timezone.utc)
    })

    email_sent = send_otp_email(
        email,
        name,
        otp
    )

    if not email_sent:

        email_verifications_collection.delete_many(
            {"user_id": user_id}
        )

        users_collection.delete_one(
            {"user_id": user_id}
        )

        raise RuntimeError(
            "Unable to send verification email"
        )

    return {
        "user_id": user_id,
        "name": name,
        "email": email,
        "role": "GENERAL_USER",
        "is_email_verified": False
    }


def consume_verification_otp(user_id, otp):
    """Count attempts and consume a code once across concurrent requests."""
    from pymongo import ReturnDocument
    now = datetime.now(timezone.utc)
    verification = email_verifications_collection.find_one_and_update(
        {"user_id": user_id, "expires_at": {"$gt": now}, "attempts": {"$lt": 5}},
        {"$inc": {"attempts": 1}}, sort=[("created_at", -1)],
        return_document=ReturnDocument.AFTER,
    )
    if not verification:
        return False
    try:
        valid = bcrypt.checkpw(otp.encode("utf-8"), verification["otp_hash"].encode("utf-8"))
    except (ValueError, TypeError):
        return False
    if not valid:
        return False
    consumed = email_verifications_collection.delete_one({"_id": verification["_id"], "otp_hash": verification["otp_hash"]})
    return consumed.deleted_count == 1


def verify_email_otp(email, otp):
    user = find_user_by_email(email)
    if user is None:
        return None
    if user.get("password_setup_required"):
        raise ValueError("Account setup must be completed with a new password.")
    if user["is_email_verified"]:
        return public_user(user)
    if not consume_verification_otp(user["user_id"], otp):
        return None
    users_collection.update_one({"user_id": user["user_id"]}, {"$set": {"is_email_verified": True}})
    return {**public_user(user), "is_email_verified": True}


def complete_staff_setup(email, otp, password):
    if len(password) < 8 or len(password.encode("utf-8")) > 72:
        raise ValueError("Password must contain at least 8 characters and at most 72 UTF-8 bytes.")
    user = find_user_by_email(email)
    if (not user or user.get("role") != "LIBRARIAN" or not user.get("password_setup_required")
            or user.get("is_email_verified") or user.get("is_active", True) is not True):
        raise ValueError("Invalid or expired setup code.")
    password_hash = hash_password(password)
    if not consume_verification_otp(user["user_id"], otp):
        raise ValueError("Invalid or expired setup code.")
    changed = users_collection.update_one(
        {"user_id": user["user_id"], "role": "LIBRARIAN", "password_setup_required": True,
         "is_email_verified": False, "is_active": {"$ne": False}},
        {"$set": {"password_hash": password_hash, "is_email_verified": True, "password_setup_required": False}},
    )
    if changed.modified_count != 1:
        raise ValueError("Unable to complete account setup.")
    from backend.utils.security_audit import security_event
    security_event("librarian_setup_completed", target_id=user["user_id"])
    return {"message": "Account setup completed. Sign in with your new password."}


def resend_verification_otp(email):
    user = find_user_by_email(email)

    if user is None:
        return None

    user_id = user["user_id"]

    if user["is_email_verified"]:
        raise ValueError(
            "Email is already verified"
        )

    last_verification = email_verifications_collection.find_one(
        {"user_id": user_id},
        sort=[("created_at", -1)]
    )

    if last_verification is not None:

        last_created = last_verification["created_at"]

        if last_created.tzinfo is None:
            last_created = last_created.replace(
                tzinfo=timezone.utc
            )

        seconds_elapsed = (
            datetime.now(timezone.utc)
            - last_created
        ).total_seconds()

        if seconds_elapsed < 60:

            remaining = int(
                60 - seconds_elapsed
            )

            raise ValueError(
                f"Please wait {remaining} seconds before requesting another code"
            )

    email_verifications_collection.delete_many(
        {"user_id": user_id}
    )

    otp = generate_otp()
    otp_hash = hash_otp(otp)

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(minutes=10)
    )

    email_verifications_collection.insert_one({
        "user_id": user_id,
        "otp_hash": otp_hash,
        "expires_at": expires_at,
        "attempts": 0,
        "created_at": datetime.now(timezone.utc)
    })

    email_sent = send_otp_email(
        user["email"],
        user["name"],
        otp
    )

    if not email_sent:

        email_verifications_collection.delete_many(
            {"user_id": user_id}
        )

        raise RuntimeError(
            "Unable to send verification email"
        )

    return {
        "user_id": user["user_id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "is_email_verified": False
    }


def login_user(email, password):
    user = find_user_by_email(email)
    if user is None or len(password.encode('utf-8')) > 72:
        return None

    password_hash = user["password_hash"]

    try:
        valid_password = bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except (ValueError, TypeError):
        return None

    if not valid_password:
        return None

    if user.get('is_active', True) is not True or user.get('role') not in ROLES or user.get('password_setup_required'):
        raise ValueError('This account is not authorized to sign in.')

    if not user["is_email_verified"]:
        raise ValueError(
            "Please verify your email before logging in"
        )

    return {
        "user_id": user["user_id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "is_email_verified": True
    }
