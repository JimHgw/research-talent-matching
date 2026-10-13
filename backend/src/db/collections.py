"""Persistent relationships only: never snapshot private profile information."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, utcnow


class SavedOpportunity(Base):
    __tablename__ = "saved_opportunities"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class ShortlistedTalent(Base):
    __tablename__ = "shortlisted_talent"
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"), primary_key=True)
    talent_id: Mapped[str] = mapped_column(ForeignKey("talent_profiles.talent_id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
