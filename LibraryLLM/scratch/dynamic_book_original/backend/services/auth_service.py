import bcrypt

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

    last_user = users_collection.find_one(
        sort=[("user_id", -1)]
    )

    if last_user is None:
        return 1

    return last_user["user_id"] + 1


def register_user(name, email, password):

    existing_user = users_collection.find_one(
        {"email": email}
    )

    if existing_user is not None:
        return None

    password_hash = hash_password(password)

    user_id = get_next_user_id()

    user_document = {
        "user_id": user_id,
        "name": name,
        "email": email,
        "password_hash": password_hash,
        "role": "GENERAL_USER",
        "is_email_verified": False,
        "created_at": datetime.now(timezone.utc)
    }

    users_collection.insert_one(user_document)

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


def verify_email_otp(email, otp):

    user = users_collection.find_one(
        {"email": email}
    )

    if user is None:
        return None

    user_id = user["user_id"]

    if user["is_email_verified"]:
        return {
            "user_id": user_id,
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "is_email_verified": True
        }

    verification = email_verifications_collection.find_one(
        {"user_id": user_id},
        sort=[("created_at", -1)]
    )

    if verification is None:
        return None

    attempts = verification.get("attempts", 0)

    if attempts >= 5:
        raise ValueError(
            "Maximum OTP attempts exceeded"
        )

    expires_at = verification["expires_at"]

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    if datetime.now(timezone.utc) > expires_at:
        raise ValueError(
            "Verification code has expired"
        )

    valid_otp = bcrypt.checkpw(
        otp.encode("utf-8"),
        verification["otp_hash"].encode("utf-8")
    )

    if not valid_otp:

        email_verifications_collection.update_one(
            {"_id": verification["_id"]},
            {"$inc": {"attempts": 1}}
        )

        return None

    users_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "is_email_verified": True
            }
        }
    )

    email_verifications_collection.delete_one(
        {"_id": verification["_id"]}
    )

    return {
        "user_id": user_id,
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "is_email_verified": True
    }


def resend_verification_otp(email):

    user = users_collection.find_one(
        {"email": email}
    )

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

    user = users_collection.find_one(
        {"email": email}
    )

    if user is None:
        return None

    password_hash = user["password_hash"]

    valid_password = bcrypt.checkpw(
        password.encode("utf-8"),
        password_hash.encode("utf-8")
    )

    if not valid_password:
        return None

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