from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)

SECURITY_PATTERNS = [
    "auth", "login", "api", "route", "view", "model", "admin",
    "settings", "config", "db", "sql", "query", "middleware",
    "password", "token", "session", "permission", "secret",
    "crypto", "hash", "sanitize", "validate", "upload",
]


@dataclass
class FileContent:
    path: str
    content: str
    line_count: int


@dataclass
class Chunk:
    files: List[FileContent] = field(default_factory=list)
    total_tokens: int = 0


def estimate_tokens(text: str) -> int:
    """Rough estimate: ~4 characters per token."""
    return len(text) // 4


def is_security_relevant(path: str) -> bool:
    path_lower = path.lower()
    return any(pattern in path_lower for pattern in SECURITY_PATTERNS)


def prioritize_files(files: List[FileContent]) -> List[FileContent]:
    """Sort files: security-relevant first, then alphabetical."""
    security = [f for f in files if is_security_relevant(f.path)]
    other = [f for f in files if not is_security_relevant(f.path)]
    security.sort(key=lambda f: f.path)
    other.sort(key=lambda f: f.path)
    return security + other


def chunk_files(files: List[FileContent], max_tokens: int = 80000) -> List[Chunk]:
    """Group files into chunks that fit within max_tokens."""
    prioritized = prioritize_files(files)
    chunks: List[Chunk] = []
    current = Chunk()

    for file in prioritized:
        file_tokens = estimate_tokens(file.content)

        # If single file exceeds max, truncate it
        if file_tokens > max_tokens:
            char_limit = max_tokens * 4
            truncated = FileContent(
                path=file.path,
                content=file.content[:char_limit] + "\n# [TRUNCATED — file too large for single analysis chunk]",
                line_count=file.line_count,
            )
            if current.files:
                chunks.append(current)
                current = Chunk()
            chunks.append(Chunk(files=[truncated], total_tokens=max_tokens))
            continue

        # If adding this file would exceed limit, start new chunk
        if current.total_tokens + file_tokens > max_tokens and current.files:
            chunks.append(current)
            current = Chunk()

        current.files.append(file)
        current.total_tokens += file_tokens

    if current.files:
        chunks.append(current)

    logger.info("[Scanner] Created %d chunks from %d files", len(chunks), len(files))
    return chunks
