import json
import logging
import re

import anthropic
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.finding import Finding
from app.models.remediation import Remediation
from app.models.scan import Scan
from app.models.repository import Repository
from app.scanner.prompts import REMEDIATION_SYSTEM_PROMPT, REMEDIATION_USER_TEMPLATE

logger = logging.getLogger(__name__)


async def get_or_generate_remediation(
    db: AsyncSession,
    finding_id: str,
    user_id: str,
) -> Remediation:
    # Verify ownership
    result = await db.execute(
        select(Finding)
        .options(selectinload(Finding.scan).selectinload(Scan.repo))
        .where(Finding.id == finding_id)
    )
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Finding not found."}})
    if finding.scan.repo.user_id != user_id:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Access denied."}})

    # Check cache
    existing = await db.execute(
        select(Remediation).where(Remediation.finding_id == finding_id)
    )
    cached = existing.scalar_one_or_none()
    if cached:
        return cached

    # Generate fix via LLM
    logger.info("[Remediation] Generating fix for finding %s", finding_id)
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    user_prompt = REMEDIATION_USER_TEMPLATE.format(
        vulnerability_type=finding.vulnerability_type,
        severity=finding.severity,
        file_path=finding.file_path,
        line_number=finding.line_number,
        description=finding.description,
        explanation=finding.explanation,
        code_snippet=finding.code_snippet,
    )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=REMEDIATION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text = response.content[0].text

    # Parse response
    try:
        data = json.loads(text.strip())
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            data = json.loads(match.group())
        else:
            data = {"fixed_code": text, "explanation": "Auto-generated fix", "confidence": "low"}

    # Validate confidence
    confidence = data.get("confidence", "medium")
    if confidence not in ("high", "medium", "low"):
        confidence = "medium"

    # Persist
    remediation = Remediation(
        finding_id=finding_id,
        fixed_code=data.get("fixed_code", ""),
        explanation=data.get("explanation", ""),
        confidence=confidence,
    )
    db.add(remediation)
    await db.commit()
    await db.refresh(remediation)

    logger.info("[Remediation] Generated fix with confidence: %s", confidence)
    return remediation
