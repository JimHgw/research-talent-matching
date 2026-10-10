"""Policy for newly chosen passwords; existing login credentials remain usable."""

from argon2.exceptions import InvalidHashError, VerificationError
from flask import current_app

from ...shared.validation import invalid, validator


def validate_new_password(password, field="password"):
    if not validator("NewPassword").is_valid(password):
        invalid(field, "Use 8–200 characters with an uppercase letter, a lowercase letter and a digit.")


def password_matches(encoded, password):
    try:
        return current_app.extensions["password_hasher"].verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False
