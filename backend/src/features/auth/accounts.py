"""Create accounts and their private defaults in the caller's transaction."""

import secrets

from ...db.models import PrivacySettings, TalentProfile, User


def create_account(db, email, password_hash, display_name, role):
    user = User(id="user_" + secrets.token_hex(16), email=email,
                display_name=display_name, role=role, password_hash=password_hash)
    db.add(user)
    db.flush()
    if role == "TALENT":
        profile = TalentProfile(talent_id="talent_" + secrets.token_hex(16), user_id=user.id)
        db.add(profile)
        db.flush()
        db.add(PrivacySettings(talent_id=profile.talent_id))
    return user
