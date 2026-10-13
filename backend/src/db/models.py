"""Shared SQLite schema and ownership invariants for implemented features."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (JSON, Boolean, CheckConstraint, DateTime, ForeignKey,
                        ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow():
    # SQLite has no timezone type. Store UTC, add Z only at the API boundary.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    __table_args__ = (CheckConstraint("role IN ('TALENT', 'RESEARCH_TEAM')"),)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User | None] = relationship()


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    ip_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class RegistrationCode(Base):
    __tablename__ = "registration_codes"
    email: Mapped[str] = mapped_column(String, primary_key=True)
    challenge_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    session_hash: Mapped[str] = mapped_column(String, nullable=False)
    code_hash: Mapped[str] = mapped_column(String, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (CheckConstraint("attempts >= 0"),)


class RegistrationAttempt(Base):
    __tablename__ = "registration_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    ip_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class PasswordResetCode(Base):
    __tablename__ = "password_reset_codes"
    email: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    challenge_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    session_hash: Mapped[str] = mapped_column(String, nullable=False)
    code_hash: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (CheckConstraint("attempts >= 0"),)


class PasswordResetAttempt(Base):
    __tablename__ = "password_reset_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    ip_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class TalentProfile(Base):
    __tablename__ = "talent_profiles"
    talent_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    discipline_group: Mapped[str | None] = mapped_column(String, nullable=True)
    education: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    courses: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    research_experience: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    research_outputs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confirmation_status: Mapped[str] = mapped_column(String, nullable=False, default="UNCONFIRMED")
    confirmed_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

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
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    profile: Mapped[TalentProfile] = relationship()
    __table_args__ = (CheckConstraint("revision >= 0"),)


class PrivacyVisibleField(Base):
    __tablename__ = "privacy_visible_fields"
    talent_id: Mapped[str] = mapped_column(ForeignKey("privacy_settings.talent_id"), primary_key=True)
    field: Mapped[str] = mapped_column(String, primary_key=True)

    privacy: Mapped[PrivacySettings] = relationship()
    __table_args__ = (CheckConstraint("field IN ('displayName', 'disciplineGroup', 'education', "
                                    "'courses', 'researchExperience', 'skills', "
                                    "'researchInterests', 'researchOutputs')"),)


class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (CheckConstraint("kind IN ('SKILL', 'INTEREST')"),)


class TagDisciplineGroup(Base):
    __tablename__ = "tag_discipline_groups"
    tag_id: Mapped[str] = mapped_column(ForeignKey("tags.id"), primary_key=True)
    discipline_group: Mapped[str] = mapped_column(String, primary_key=True)

    tag: Mapped[Tag] = relationship()
    __table_args__ = (CheckConstraint("discipline_group IN ('STEM', 'BUSINESS')"),)


class ProfileSkill(Base):
    __tablename__ = "profile_skills"
    talent_id: Mapped[str] = mapped_column(ForeignKey("talent_profiles.talent_id"), primary_key=True)
    tag_id: Mapped[str] = mapped_column(ForeignKey("tags.id"), primary_key=True)
    claim: Mapped[str] = mapped_column(String, nullable=False)
    evidence_text: Mapped[str] = mapped_column(String, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    profile: Mapped[TalentProfile] = relationship()
    tag: Mapped[Tag] = relationship()
    __table_args__ = (CheckConstraint("claim IN ('HAS', 'DOES_NOT_HAVE')"),
                      CheckConstraint("position >= 0"), UniqueConstraint("talent_id", "position"))


class ProfileInterest(Base):
    __tablename__ = "profile_interests"
    talent_id: Mapped[str] = mapped_column(ForeignKey("talent_profiles.talent_id"), primary_key=True)
    tag_id: Mapped[str] = mapped_column(ForeignKey("tags.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    profile: Mapped[TalentProfile] = relationship()
    tag: Mapped[Tag] = relationship()
    __table_args__ = (CheckConstraint("position >= 0"), UniqueConstraint("talent_id", "position"))


class Document(Base):
    """Metadata target for provenance FKs; upload/extraction routes belong to US-09."""
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    talent_id: Mapped[str] = mapped_column(ForeignKey("talent_profiles.talent_id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    media_type: Mapped[str] = mapped_column(String, nullable=False)
    storage_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    profile: Mapped[TalentProfile] = relationship()
    __table_args__ = (
        CheckConstraint("kind IN ('CV', 'TRANSCRIPT')"),
        CheckConstraint("status IN ('QUEUED', 'PROCESSING', 'READY', 'FAILED')"),
        CheckConstraint("size_bytes BETWEEN 1 AND 10485760"),
        CheckConstraint("(status = 'FAILED' AND error IS NOT NULL) OR "
                        "(status != 'FAILED' AND error IS NULL)"),
    )

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
        DateTime,
        nullable=False,
        default=utcnow,
    )

    document: Mapped[Document] = relationship()

class ProfileOrigin(Base):
    __tablename__ = "profile_origins"
    talent_id: Mapped[str] = mapped_column(ForeignKey("talent_profiles.talent_id"), primary_key=True)
    field: Mapped[str] = mapped_column(String, primary_key=True)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
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
    status: Mapped[str] = mapped_column(String, nullable=False, default="DRAFT")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    university: Mapped[str] = mapped_column(String(200), nullable=False)
    discipline_group: Mapped[str] = mapped_column(String, nullable=False)
    discipline: Mapped[str] = mapped_column(String(200), nullable=False)
    research_area: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

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
    kind: Mapped[str] = mapped_column(String, nullable=False)
    importance: Mapped[str] = mapped_column(String, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    opportunity: Mapped[Opportunity] = relationship()
    __table_args__ = (
        CheckConstraint("kind IN ('SKILL', 'INTEREST')"),
        CheckConstraint("importance IN ('REQUIRED', 'PREFERRED')"),
        CheckConstraint("position >= 0"),
        UniqueConstraint("opportunity_id", "position"),
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
