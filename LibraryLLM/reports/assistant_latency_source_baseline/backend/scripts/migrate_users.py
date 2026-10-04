import sqlite3

from backend.database.mongodb import (
    users_collection,
    email_verifications_collection
)


SQLITE_PATH = r"D:\SDC\LibraryLLM\datasets\library.db"


def migrate_users():

    sqlite = sqlite3.connect(SQLITE_PATH)

    try:

        users = sqlite.execute(
            """
            SELECT
                user_id,
                name,
                email,
                password_hash,
                role,
                is_email_verified,
                created_at
            FROM users
            """
        ).fetchall()

        verifications = sqlite.execute(
            """
            SELECT
                user_id,
                otp_hash,
                expires_at,
                attempts,
                created_at
            FROM email_verifications
            """
        ).fetchall()

    finally:

        sqlite.close()

    # Clear only the collections we're migrating
    users_collection.delete_many({})
    email_verifications_collection.delete_many({})

    # Migrate users
    user_documents = []

    for user in users:

        (
            user_id,
            name,
            email,
            password_hash,
            role,
            is_email_verified,
            created_at
        ) = user

        user_documents.append({
            "legacy_user_id": user_id,
            "name": name,
            "email": email,
            "password_hash": password_hash,
            "role": role,
            "is_email_verified": bool(is_email_verified),
            "created_at": created_at
        })

    if user_documents:

        users_collection.insert_many(
            user_documents
        )

    # Migrate verification records
    verification_documents = []

    for verification in verifications:

        (
        
            user_id,
            otp_hash,
            expires_at,
            attempts,
            created_at
        ) = verification

        verification_documents.append({
            "user_id": user_id,
            "otp_hash": otp_hash,
            "expires_at": expires_at,
            "attempts": attempts,
            "created_at": created_at
        })

    if verification_documents:

        email_verifications_collection.insert_many(
            verification_documents
        )

    print(
        f"Users migrated: {len(user_documents)}"
    )

    print(
        f"Verification records migrated: "
        f"{len(verification_documents)}"
    )


if __name__ == "__main__":
    migrate_users()