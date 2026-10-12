"""Independent Argon2id entry credentials and hashed random invite tokens."""
import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from argon2.profiles import RFC_9106_LOW_MEMORY


hasher = PasswordHasher.from_parameters(RFC_9106_LOW_MEMORY)


def hash_code(code):
    # Case-sensitive passphrases: do not trim or normalize human secrets.
    if not isinstance(code, str) or not 8 <= len(code) <= 128:
        raise ValueError('Access code must contain 8 to 128 characters.')
    return hasher.hash(code)


def verify_code(encoded, code):
    if not encoded or not isinstance(code, str) or len(code) > 128:
        return False
    try:
        return hasher.verify(encoded, code)
    except (VerificationError, InvalidHashError, TypeError):
        return False


def invitation_token():
    return secrets.token_urlsafe(32)


def token_hash(token):
    # Tokens have 256 bits of entropy; unlike human codes, a password KDF is unnecessary.
    return hashlib.sha256(token.encode('utf8')).hexdigest()
