import json
import logging
import re
import time
from typing import List, Dict

import anthropic

from app.config import settings
from app.scanner.chunker import Chunk
from app.scanner.prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

VALID_SEVERITIES = {"critical", "high", "medium", "low", "informational"}
REQUIRED_KEYS = {"severity", "vulnerability_type", "file_path", "line_number", "code_snippet", "description", "explanation"}


def parse_llm_response(text: str) -> List[dict]:
    """Parse JSON array from LLM response, handling markdown wrapping."""
    # Try direct parse first
    try:
        result = json.loads(text.strip())
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Fallback: extract JSON array from markdown or surrounding text
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    logger.warning("[Scanner] Failed to parse LLM output: %.100s...", text)
    return []


def validate_finding(finding: dict) -> bool:
    """Validate a finding dict has all required fields with correct types."""
    if not isinstance(finding, dict):
        return False
    if not REQUIRED_KEYS.issubset(finding.keys()):
        logger.warning("[Scanner] Finding missing keys: %s", REQUIRED_KEYS - finding.keys())
        return False
    if finding.get("severity", "").lower() not in VALID_SEVERITIES:
        logger.warning("[Scanner] Invalid severity: %s", finding.get("severity"))
        return False
    if not isinstance(finding.get("line_number"), int) or finding["line_number"] < 1:
        logger.warning("[Scanner] Invalid line_number: %s", finding.get("line_number"))
        return False
    return True


def analyze_chunk(chunk: Chunk, max_retries: int = 1, system_prompt: str = None) -> List[dict]:
    """Send a chunk to Claude for security analysis. Returns validated findings."""
    if system_prompt is None:
        system_prompt = SYSTEM_PROMPT
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    user_prompt = build_user_prompt(chunk)

    file_names = [f.path for f in chunk.files]
    logger.info("[Scanner] Analyzing chunk with %d files: %s", len(file_names), file_names)

    for attempt in range(max_retries + 1):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            text = response.content[0].text
            logger.info("[Scanner] Received response (%d chars)", len(text))

            raw_findings = parse_llm_response(text)
            valid = []
            for f in raw_findings:
                if validate_finding(f):
                    f["severity"] = f["severity"].lower()
                    valid.append(f)
                else:
                    logger.warning("[Scanner] Discarding invalid finding: %.100s", str(f))

            logger.info("[Scanner] Found %d valid findings in chunk", len(valid))
            return valid

        except anthropic.RateLimitError:
            if attempt < max_retries:
                logger.warning("[Scanner] Rate limited, retrying in 5s (attempt %d)", attempt + 1)
                time.sleep(5)
            else:
                raise
        except anthropic.APIError as e:
            if attempt < max_retries:
                logger.warning("[Scanner] API error: %s, retrying in 5s", str(e))
                time.sleep(5)
            else:
                raise

    return []  # Should not reach here
