import hashlib


def compute_identity_hash(
    vuln_type: str,
    file_path: str,
    file_content: str,
    line_number: int,
) -> str:
    """Compute a stable identity hash for a finding based on content context."""
    lines = file_content.split("\n")
    start = max(0, line_number - 4)  # 3 lines before (0-indexed: line_number - 1 - 3)
    end = min(len(lines), line_number + 1)  # 1 line after (0-indexed: line_number - 1 + 2)
    context_lines = lines[start:end]

    # Normalize: strip whitespace, remove comment-only and empty lines
    normalized = []
    for line in context_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            normalized.append(stripped.lower())

    context = "\n".join(normalized)
    raw = f"{vuln_type}::{file_path}::{context}"
    return hashlib.sha256(raw.encode()).hexdigest()
