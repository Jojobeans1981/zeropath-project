import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.sqlite import CHAR
from app.database import Base
from app.models.user import utcnow


class Finding(Base):
    __tablename__ = "findings"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id = Column(CHAR(36), ForeignKey("scans.id"), index=True, nullable=False)
    identity_hash = Column(String, index=True, nullable=False)
    severity = Column(String, nullable=False)
    vulnerability_type = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    line_number = Column(Integer, nullable=False)
    code_snippet = Column(String, nullable=False)
    description = Column(String, nullable=False)
    explanation = Column(String, nullable=False)
    language = Column(String, default="python", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
