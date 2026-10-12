"""Safely reset one existing LuminaR administrator password locally."""

import getpass
import sys

from backend.database.mongodb import users_collection
from backend.services.auth_service import hash_password


ADMIN_ROLE = "ADMIN"
SAFE_ADMIN_FIELDS = {"_id": 0, "name": 1, "email": 1, "user_id": 1, "role": 1}


def list_administrators():
    """Return only the safe fields needed to select an existing Admin."""
    administrators = list(users_collection.find({"role": ADMIN_ROLE}, SAFE_ADMIN_FIELDS))
    return sorted(administrators, key=lambda user: str(user.get("user_id", "")))


def display_administrator(administrator):
    print(f"name: {administrator.get('name', '')}")
    print(f"email: {administrator.get('email', '')}")
    print(f"user_id: {administrator.get('user_id', '')}")
    print(f"role: {administrator.get('role', '')}")


def select_administrator(administrators, selector):
    """Select by exact user ID or case-insensitive email from Admin results only."""
    selector = selector.strip()
    email_selector = selector.casefold()
    matches = [
        administrator
        for administrator in administrators
        if str(administrator.get("user_id", "")) == selector
        or str(administrator.get("email", "")).casefold() == email_selector
    ]
    return matches[0] if len(matches) == 1 else None


def validate_password(password):
    """Apply the password rules used by LuminaR registration and staff setup."""
    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters.")
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must not exceed 72 UTF-8 bytes.")


def update_admin_password(user_id, password):
    """Update only password_hash, provided the target is still an Admin."""
    validate_password(password)
    password_hash = hash_password(password)
    result = users_collection.update_one(
        {"user_id": user_id, "role": ADMIN_ROLE},
        {"$set": {"password_hash": password_hash}},
    )
    if result.matched_count != 1:
        raise ValueError("The selected administrator no longer exists or is not an Admin.")


def main():
    try:
        administrators = list_administrators()
    except Exception:
        print("Administrator password reset failed. Check database availability.", file=sys.stderr)
        return 1

    if not administrators:
        print("No administrator account exists.")
        return 0

    if len(administrators) == 1:
        administrator = administrators[0]
        display_administrator(administrator)
    else:
        print("Multiple administrator accounts exist:")
        for administrator in administrators:
            display_administrator(administrator)
            print()
        selector = input("Admin email or user_id: ")
        administrator = select_administrator(administrators, selector)
        if administrator is None:
            print("Administrator selection did not match exactly one Admin account.")
            return 1

    print("Reset password for:")
    print(f"email: {administrator['email']}")
    print(f"role: {administrator['role']}")
    if input("Continue? [y/N] ").strip().casefold() != "y":
        print("Password reset cancelled.")
        return 0

    password = getpass.getpass("New password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        print("Passwords do not match.", file=sys.stderr)
        return 1

    try:
        update_admin_password(administrator["user_id"], password)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print("Administrator password reset failed. No secrets were printed.", file=sys.stderr)
        return 1

    print("Administrator password updated successfully.")
    print(f"email: {administrator['email']}")
    print(f"role: {ADMIN_ROLE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
