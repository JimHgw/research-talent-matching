"""Shared MySQL/SQLite schema and ownership invariants for implemented features."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (JSON, Boolean, CheckConstraint, DateTime, ForeignKey,
                        ForeignKeyConstraint, Index, Integer, String, Table, Text, UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.mysql import DATETIME, MEDIUMTEXT


# Both engines store naive UTC. MySQL must retain microseconds for ordering/leases.
UTCDateTime = DateTime().with_variant(DATETIME(fsp=6), "mysql")


def utcnow():
    # Store UTC, add Z only at the API boundary.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    @classmethod
    def __table_cls__(cls, *args, **kwargs):
        kwargs.setdefault("mysql_engine", "InnoDB")
        kwargs.setdefault("mysql_charset", "utf8mb4")
        kwargs.setdefault("mysql_collate", "utf8mb4_0900_bin")
        return Table(*args, **kwargs)


class DatabaseWriteLock(Base):
    __tablename__ = "database_write_lock"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    __table_args__ = (CheckConstraint("id = 1"),)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    __table_args__ = (CheckConstraint("role IN ('TALENT', 'RESEARCH_TEAM')"),)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    user: Mapped[User | None] = relationship()


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    attempted_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)


class RegistrationCode(Base):
    __tablename__ = "registration_codes"
    email: Mapped[str] = mapped_column(String(254), primary_key=True)
    challenge_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    session_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    __table_args__ = (CheckConstraint("attempts >= 0"),)


class RegistrationAttempt(Base):
    __tablename__ = "registration_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    attempted_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)


class PasswordResetCode(Base):
    __tablename__ = "password_reset_codes"
    email: Mapped[str] = mapped_column(String(254), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    challenge_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    session_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    __table_args__ = (CheckConstraint("attempts >= 0"),)


class PasswordResetAttempt(Base):
    __tablename__ = "password_reset_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    attempted_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)


class TalentProfile(Base):
    __tablename__ = "talent_profiles"
    talent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    discipline_group: Mapped[str | None] = mapped_column(String(16), nullable=True)
    education: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    courses: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    research_experience: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    research_outputs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confirmation_status: Mapped[str] = mapped_column(String(16), nullable=False, default="UNCONFIRMED")
    confirmed_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)

    user: Mapped[User] = relationship()
    __table_args__ = (
        CheckConstraint("revision >= 0"),
        CheckConstraint("discipline_group IS NULL OR discipline_group IN ('STEM', 'BUSINESS')"),
        CheckConstraint("(confirmation_status = 'UNCONFIRMED' AND confirmed_revision IS NULL "
                        "AND confirmed_at IS NULL) OR (confirmation_status = 'CONFIRMED' "
                        "AND confirmed_revision IS NOT NULL AND confirmed_at IS NOT NULL "
                        "AND confirmed_revision = revision)"),
    )


class PrivacySettings(Base):
    __tablename__ = "privacy_settings"
    talent_id: Mapped[str] = mapped_column(ForeignKey("talent_profiles.talent_id"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discoverable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)

    profile: Mapped[TalentProfile] = relationship()
    __table_args__ = (CheckConstraint("revision >= 0"),)


class PrivacyVisibleField(Base):
    __tablename__ = "privacy_visible_fields"
    talent_id: Mapped[str] = mapped_column(ForeignKey("privacy_settings.talent_id"), primary_key=True)
    field: Mapped[str] = mapped_column(String(32), primary_key=True)

    privacy: Mapped[PrivacySettings] = relationship()
    __table_args__ = (CheckConstraint("field IN ('displayName', 'disciplineGroup', 'education', "
                                    "'courses', 'researchExperience', 'skills', "
                                    "'researchInterests', 'researchOutputs')"),)


class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    __table_args__ = (CheckConstraint("kind IN ('SKILL', 'INTEREST')"),)


class TagDisciplineGroup(Base):
    __tablename__ = "tag_discipline_groups"
    tag_id: Mapped[str] = mapped_column(ForeignKey("tags.id"), primary_key=True)
    discipline_group: Mapped[str] = mapped_column(String(16), primary_key=True)

    tag: Mapped[Tag] = relationship()
    __table_args__ = (CheckConstraint("discipline_group IN ('STEM', 'BUSINESS')"),)


class ProfileSkill(Base):
    """Legacy tag-backed rows, retained for non-destructive upgrades."""
    __tablename__ = "profile_skills"
    talent_id: Mapped[str] = mapped_column(ForeignKey("talent_profiles.talent_id"), primary_key=True)
    tag_id: Mapped[str] = mapped_column(ForeignKey("tags.id"), primary_key=True)
    claim: Mapped[str] = mapped_column(String(16), nullable=False)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    profile: Mapped[TalentProfile] = relationship()
    tag: Mapped[Tag] = relationship()
    __table_args__ = (CheckConstraint("claim IN ('HAS', 'DOES_NOT_HAVE')"),
                      CheckConstraint("position >= 0"), UniqueConstraint("talent_id", "position"))


class ProfileSkillDetails(Base):
    """An explicit empty list also supersedes legacy skill rows."""
    __tablename__ = "profile_skill_details"
    talent_id: Mapped[str] = mapped_column(ForeignKey("talent_profiles.talent_id"), primary_key=True)
    skills: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    profile: Mapped[TalentProfile] = relationship()


class ProfileInterest(Base):
    __tablename__ = "profile_interests"
    talent_id: Mapped[str] = mapped_column(ForeignKey("talent_profiles.talent_id"), primary_key=True)
    tag_id: Mapped[str] = mapped_column(ForeignKey("tags.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    profile: Mapped[TalentProfile] = relationship()
    tag: Mapped[Tag] = relationship()
    __table_args__ = (CheckConstraint("position >= 0"), UniqueConstraint("talent_id", "position"))


class ProfileTextDetails(Base):
    """Private descriptions; the resume permits 20,000 four-byte characters."""

    __tablename__ = "profile_text_details"
    talent_id: Mapped[str] = mapped_column(ForeignKey("talent_profiles.talent_id"), primary_key=True)
    research_interest_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    resume_description: Mapped[str] = mapped_column(Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False, default="")
    profile: Mapped[TalentProfile] = relationship()


class PersonalInterestTag(Base):
    __tablename__ = "personal_interest_tags"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    talent_id: Mapped[str] = mapped_column(ForeignKey("talent_profiles.talent_id"), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    normalised_label: Mapped[str] = mapped_column(String(300), nullable=False)
    profile: Mapped[TalentProfile] = relationship()
    __table_args__ = (UniqueConstraint("talent_id", "normalised_label"),
                      UniqueConstraint("id", "talent_id"))


class ProfilePersonalInterest(Base):
    __tablename__ = "profile_personal_interests"
    talent_id: Mapped[str] = mapped_column(ForeignKey("talent_profiles.talent_id"), primary_key=True)
    tag_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    tag: Mapped[PersonalInterestTag] = relationship()
    __table_args__ = (ForeignKeyConstraint(["tag_id", "talent_id"],
                                          ["personal_interest_tags.id", "personal_interest_tags.talent_id"]),
                      CheckConstraint("position >= 0"), UniqueConstraint("talent_id", "position"))


class ProfileComponentOrigin(Base):
    """Component provenance without weakening the legacy profile-origin check."""

    __tablename__ = "profile_component_origins"
    talent_id: Mapped[str] = mapped_column(ForeignKey("talent_profiles.talent_id"), primary_key=True)
    field: Mapped[str] = mapped_column(String(32), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    __table_args__ = (CheckConstraint("field IN ('researchInterestText', 'customInterestTags', 'resumeDescription')"),
                      CheckConstraint("(source_type = 'MANUAL' AND document_id IS NULL) OR "
                                      "(source_type = 'USER_REVIEWED_DOCUMENT' AND document_id IS NOT NULL)"))


class Document(Base):
    """Metadata target for provenance FKs; upload/extraction routes belong to US-09."""
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    talent_id: Mapped[str] = mapped_column(ForeignKey("talent_profiles.talent_id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)

    profile: Mapped[TalentProfile] = relationship()
    __table_args__ = (
        CheckConstraint("kind IN ('CV', 'TRANSCRIPT')"),
        CheckConstraint("status IN ('QUEUED', 'PROCESSING', 'READY', 'FAILED')"),
        CheckConstraint("size_bytes BETWEEN 1 AND 10485760"),
        CheckConstraint("(status = 'FAILED' AND error IS NOT NULL) OR "
                        "(status != 'FAILED' AND error IS NULL)"),
    )

class DocumentProcessingLease(Base):
    """Persist claims separately so existing document tables need no ALTER."""
    __tablename__ = "document_processing_leases"
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    __table_args__ = (CheckConstraint("attempts >= 1"),)


class DocumentExtraction(Base):
    """Extraction suggestions awaiting user review."""

    __tablename__ = "document_extractions"

    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id"),
        primary_key=True,
    )

    result: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utcnow,
    )

    document: Mapped[Document] = relationship()

class ProfileOrigin(Base):
    __tablename__ = "profile_origins"
    talent_id: Mapped[str] = mapped_column(ForeignKey("talent_profiles.talent_id"), primary_key=True)
    field: Mapped[str] = mapped_column(String(32), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True)

    profile: Mapped[TalentProfile] = relationship()
    document: Mapped[Document | None] = relationship()
    __table_args__ = (
        CheckConstraint("field IN ('education', 'courses', 'researchExperience', "
                        "'skills', 'researchInterests', 'researchOutputs')"),
        CheckConstraint("(source_type = 'MANUAL' AND document_id IS NULL) OR "
                        "(source_type = 'USER_REVIEWED_DOCUMENT' AND document_id IS NOT NULL)"),
    )


class Opportunity(Base):
    __tablename__ = "opportunities"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    university: Mapped[str] = mapped_column(String(200), nullable=False)
    discipline_group: Mapped[str] = mapped_column(String(16), nullable=False)
    discipline: Mapped[str] = mapped_column(String(200), nullable=False)
    research_area: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    opportunity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)

    owner: Mapped[User] = relationship()
    __table_args__ = (
        CheckConstraint("revision >= 1"),
        CheckConstraint("status IN ('DRAFT', 'PUBLISHED')"),
        CheckConstraint("discipline_group IN ('STEM', 'BUSINESS')"),
        Index("ix_opportunities_owner_updated", "owner_user_id", "updated_at", "id"),
        Index("ix_opportunities_status_updated", "status", "updated_at", "id"),
    )


class OpportunityRequirement(Base):
    __tablename__ = "opportunity_requirements"
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"), primary_key=True)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    criteria: Mapped[dict[str, Any] | None] = mapped_column(
        JSON(none_as_null=True),
        nullable=True,
    )
    importance: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    opportunity: Mapped[Opportunity] = relationship()
    __table_args__ = (
        CheckConstraint(
            "kind IN ('SKILL', 'INTEREST', 'EDUCATION', "
            "'RESEARCH_EXPERIENCE', 'RESEARCH_OUTPUT')",
            name="ck_opportunity_requirement_kind",
        ),
        CheckConstraint("importance IN ('REQUIRED', 'PREFERRED')"),
        CheckConstraint("position >= 0"),
        UniqueConstraint("opportunity_id", "position"),
    )


class OpportunitySkillDetails(Base):
    __tablename__ = "opportunity_skill_details"
    opportunity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    requirement_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    titles: Mapped[list] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["opportunity_id", "requirement_id"],
                             ["opportunity_requirements.opportunity_id", "opportunity_requirements.id"]),
    )


class RequirementTag(Base):
    __tablename__ = "requirement_tags"
    opportunity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    requirement_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tag_id: Mapped[str] = mapped_column(ForeignKey("tags.id"), primary_key=True, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    requirement: Mapped[OpportunityRequirement] = relationship()
    tag: Mapped[Tag] = relationship()
    __table_args__ = (
        ForeignKeyConstraint(["opportunity_id", "requirement_id"],
                             ["opportunity_requirements.opportunity_id", "opportunity_requirements.id"]),
        CheckConstraint("position >= 0"),
        UniqueConstraint("opportunity_id", "requirement_id", "position"),
    )
