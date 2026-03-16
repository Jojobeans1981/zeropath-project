import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.sqlite import CHAR
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.user import utcnow


class Remediation(Base):
    __tablename__ = "remediations"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    finding_id = Column(CHAR(36), ForeignKey("findings.id"), unique=True, nullable=False)
    fixed_code = Column(String, nullable=False)
    explanation = Column(String, nullable=False)
    confidence = Column(String, nullable=False, default="medium")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    finding = relationship("Finding", backref="remediation")
