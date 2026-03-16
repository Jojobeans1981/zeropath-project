from app.scanner.chunker import FileContent, chunk_files, prioritize_files
from app.scanner.dedup import compute_identity_hash
from app.scanner.analyzer import parse_llm_response, validate_finding


def test_chunker_single_file():
    files = [FileContent(path="app.py", content="x = 1\n" * 100, line_count=100)]
    chunks = chunk_files(files, max_tokens=80000)
    assert len(chunks) == 1
    assert len(chunks[0].files) == 1


def test_chunker_multiple_chunks():
    # Create files that exceed one chunk
    big_content = "x = 1\n" * 100000  # ~600K chars = ~150K tokens
    files = [FileContent(path=f"file{i}.py", content=big_content, line_count=100000) for i in range(3)]
    chunks = chunk_files(files, max_tokens=80000)
    assert len(chunks) >= 3


def test_chunker_oversized_file():
    huge = "x = 1\n" * 500000  # Way over 80K tokens
    files = [FileContent(path="huge.py", content=huge, line_count=500000)]
    chunks = chunk_files(files, max_tokens=80000)
    assert len(chunks) == 1
    assert "[TRUNCATED" in chunks[0].files[0].content


def test_chunker_priority_ordering():
    files = [
        FileContent(path="utils.py", content="x=1", line_count=1),
        FileContent(path="auth.py", content="x=1", line_count=1),
        FileContent(path="helpers.py", content="x=1", line_count=1),
    ]
    prioritized = prioritize_files(files)
    assert prioritized[0].path == "auth.py"


def test_dedup_stable_hash():
    h1 = compute_identity_hash("SQL Injection", "app.py", "line1\nline2\nline3\nline4\nline5", 3)
    h2 = compute_identity_hash("SQL Injection", "app.py", "line1\nline2\nline3\nline4\nline5", 3)
    assert h1 == h2


def test_dedup_different_vuln_type():
    h1 = compute_identity_hash("SQL Injection", "app.py", "code", 1)
    h2 = compute_identity_hash("XSS", "app.py", "code", 1)
    assert h1 != h2


def test_dedup_tolerates_whitespace():
    h1 = compute_identity_hash("SQLi", "a.py", "  x = 1  \n  y = 2  ", 1)
    h2 = compute_identity_hash("SQLi", "a.py", "x = 1\ny = 2", 1)
    assert h1 == h2


def test_parser_valid_json():
    result = parse_llm_response('[{"severity": "high", "vulnerability_type": "XSS"}]')
    assert len(result) == 1


def test_parser_json_in_markdown():
    result = parse_llm_response('```json\n[{"severity": "high"}]\n```')
    assert len(result) == 1


def test_parser_empty_array():
    result = parse_llm_response("[]")
    assert result == []


def test_parser_malformed():
    result = parse_llm_response("this is not json at all")
    assert result == []


def test_validate_finding_valid():
    f = {
        "severity": "high",
        "vulnerability_type": "SQLi",
        "file_path": "app.py",
        "line_number": 10,
        "code_snippet": "code",
        "description": "desc",
        "explanation": "expl",
    }
    assert validate_finding(f) is True


def test_validate_finding_missing_keys():
    assert validate_finding({"severity": "high"}) is False


def test_validate_finding_bad_severity():
    f = {
        "severity": "super_critical",
        "vulnerability_type": "SQLi",
        "file_path": "a.py",
        "line_number": 1,
        "code_snippet": "c",
        "description": "d",
        "explanation": "e",
    }
    assert validate_finding(f) is False
