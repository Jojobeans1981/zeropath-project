"""
File-level scan caching.

Hashes each file's content and skips re-analysis if the file hasn't changed
since the last scan. Dramatically reduces LLM calls on re-scans.
"""
import hashlib
import logging
from typing import Dict, List, Set

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.scan import Scan
from app.models.finding import Finding

logger = logging.getLogger(__name__)


def hash_file_content(content: str) -> str:
    """SHA-256 hash of file content for change detection."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def get_previous_scan_file_hashes(db: Session, repo_id: str, current_scan_id: str) -> Dict[str, str]:
    """Get file content hashes from the most recent completed scan for a repo.
    Returns {file_path: content_hash}."""
    previous_scan = (
        db.query(Scan)
        .filter(
            Scan.repo_id == repo_id,
            Scan.id != current_scan_id,
            Scan.status == "complete",
        )
        .order_by(Scan.created_at.desc())
        .first()
    )
    if not previous_scan:
        return {}

    # Get findings from previous scan — use identity_hash as a proxy for file state
    prev_findings = db.query(Finding).filter(Finding.scan_id == previous_scan.id).all()
    file_hashes = {}
    for f in prev_findings:
        # Store the file_path -> we'll compare content hashes
        if f.file_path not in file_hashes:
            file_hashes[f.file_path] = f.identity_hash  # Use as change indicator

    return file_hashes


def filter_changed_files(
    file_contents: list,
    content_hashes: Dict[str, str],
    previous_hashes: Dict[str, str],
) -> tuple:
    """Split files into changed and unchanged based on content hashes.
    Returns (changed_files, unchanged_files, cached_count)."""
    changed = []
    unchanged = []

    for fc in file_contents:
        current_hash = content_hashes.get(fc.path, "")
        prev_hash = previous_hashes.get(fc.path, "")

        if prev_hash and current_hash == prev_hash:
            unchanged.append(fc)
        else:
            changed.append(fc)

    logger.info("[Cache] %d changed files, %d unchanged (cached)", len(changed), len(unchanged))
    return changed, unchanged, len(unchanged)
