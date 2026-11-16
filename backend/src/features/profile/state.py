"""Profile change transition shared by manual saves and reviewed imports."""

from ...db.models import utcnow


def mark_profile_changed(profile):
    """Record one change and require a separate review/confirmation.

    Manual saves call this only when canonical content changes. A reviewed
    import calls it on every successful import, including identical content.
    The caller owns the write transaction and persistence.
    """
    profile.revision += 1
    profile.confirmation_status = "UNCONFIRMED"
    profile.confirmed_revision = None
    profile.confirmed_at = None
    profile.updated_at = utcnow()
