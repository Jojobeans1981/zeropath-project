import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.sqlite import CHAR
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.user import utcnow


class Scan(Base):
    __tablename__ = "scans"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repo_id = Column(CHAR(36), ForeignKey("repositories.id"), index=True, nullable=False)
    status = Column(String, default="queued", nullable=False)
    commit_sha = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    files_scanned = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    repo = relationship("Repository", backref="scans")
    findings = relationship("Finding", backref="scan", cascade="all, delete-orphan")
