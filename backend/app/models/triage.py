import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.sqlite import CHAR
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.user import utcnow


class TriageStatus(Base):
    __tablename__ = "triage_statuses"
    __table_args__ = (
        UniqueConstraint("finding_id", "user_id", name="uq_finding_user_triage"),
    )

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    finding_id = Column(CHAR(36), ForeignKey("findings.id"), index=True, nullable=False)
    user_id = Column(CHAR(36), ForeignKey("users.id"), index=True, nullable=False)
    status = Column(String, nullable=False, default="open")
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    finding = relationship("Finding", backref="triage_records")
    user = relationship("User")
