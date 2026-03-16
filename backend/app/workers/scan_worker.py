import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from celery import Celery

from app.config import settings
from app.database import SyncSessionLocal
from app.models.finding import Finding
from app.models.repository import Repository
from app.models.scan import Scan
from app.scanner.analyzer import analyze_chunk
from app.scanner.chunker import FileContent, chunk_files
from app.scanner.dedup import compute_identity_hash
from app.scanner.git_ops import clone_repo, discover_python_files
from app.services.finding_service import carry_forward_triage

logger = logging.getLogger(__name__)

celery_app = Celery("zeropath", broker=settings.redis_url)
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"


@celery_app.task(name="run_scan")
def run_scan(scan_id: str) -> None:
    """Full scan pipeline: clone -> discover -> chunk -> analyze -> dedup -> persist."""
    db = SyncSessionLocal()
    temp_dir = Path(settings.scan_workdir) / str(uuid.uuid4())

    try:
        # 1. Get scan and repo
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            logger.error("[Worker] Scan %s not found", scan_id)
            return
        repo = db.query(Repository).filter(Repository.id == scan.repo_id).first()
        if not repo:
            logger.error("[Worker] Repository %s not found", scan.repo_id)
            return

        # 2. Set status to running
        scan.status = "running"
        scan.started_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("[Worker] Starting scan %s for repo %s", scan_id, repo.name)

        # 3. Clone repo
        temp_dir.mkdir(parents=True, exist_ok=True)
        commit_sha = clone_repo(repo.url, temp_dir)
        scan.commit_sha = commit_sha
        db.commit()

        # 4. Discover Python files
        py_files = discover_python_files(temp_dir)
        if not py_files:
            logger.info("[Worker] No Python files found in %s", repo.name)
            scan.status = "complete"
            scan.files_scanned = 0
            scan.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        # 5. Read file contents
        file_contents: List[FileContent] = []
        for rel_path in py_files:
            full_path = temp_dir / rel_path
            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
                file_contents.append(FileContent(
                    path=str(rel_path),
                    content=content,
                    line_count=content.count("\n") + 1,
                ))
            except Exception as e:
                logger.warning("[Worker] Could not read %s: %s", rel_path, e)

        # 6. Chunk files
        chunks = chunk_files(file_contents)
        logger.info("[Worker] Processing %d chunks for %d files", len(chunks), len(file_contents))

        # 7. Analyze each chunk
        all_findings: List[dict] = []
        for i, chunk in enumerate(chunks):
            logger.info("[Worker] Analyzing chunk %d/%d", i + 1, len(chunks))
            findings = analyze_chunk(chunk)
            all_findings.extend(findings)

        # 8. Deduplicate and persist findings
        seen_hashes: set = set()
        persisted_count = 0

        # Build file content lookup for dedup context
        content_map = {fc.path: fc.content for fc in file_contents}

        for raw in all_findings:
            file_content = content_map.get(raw["file_path"], "")
            identity_hash = compute_identity_hash(
                raw["vulnerability_type"],
                raw["file_path"],
                file_content,
                raw["line_number"],
            )

            if identity_hash in seen_hashes:
                logger.info("[Worker] Dedup: skipping duplicate finding %s in %s", raw["vulnerability_type"], raw["file_path"])
                continue
            seen_hashes.add(identity_hash)

            finding = Finding(
                scan_id=scan_id,
                identity_hash=identity_hash,
                severity=raw["severity"],
                vulnerability_type=raw["vulnerability_type"],
                file_path=raw["file_path"],
                line_number=raw["line_number"],
                code_snippet=raw["code_snippet"],
                description=raw["description"],
                explanation=raw["explanation"],
            )
            db.add(finding)
            persisted_count += 1

        # 8.5. Carry forward triage from previous scan
        try:
            carried = carry_forward_triage(db, scan_id)
            logger.info("[Worker] Carried forward %d triage statuses", carried)
        except Exception as e:
            logger.warning("[Worker] Triage carry-forward failed (non-fatal): %s", str(e))

        # 9. Mark complete
        scan.status = "complete"
        scan.files_scanned = len(file_contents)
        scan.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("[Worker] Scan %s complete: %d files, %d findings", scan_id, len(file_contents), persisted_count)

    except Exception as e:
        logger.exception("[Worker] Scan %s failed: %s", scan_id, str(e))
        try:
            scan = db.query(Scan).filter(Scan.id == scan_id).first()
            if scan:
                scan.status = "failed"
                scan.error_message = str(e)[:500]
                scan.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            logger.exception("[Worker] Failed to update scan status")
    finally:
        db.close()
        if temp_dir.exists():
            shutil.rmtree(str(temp_dir), ignore_errors=True)
            logger.info("[Worker] Cleaned up temp directory %s", temp_dir)
