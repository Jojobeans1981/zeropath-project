from app.scanner.chunker import Chunk

SYSTEM_PROMPT = """You are a senior application security auditor specializing in Python code review. Your task is to analyze the provided Python source code for security vulnerabilities.

You must identify real, exploitable vulnerabilities. Do not report style issues, performance concerns, or theoretical risks that require unlikely conditions. Focus on issues that a malicious actor could realistically exploit.

Vulnerability classes to look for include but are not limited to:
- SQL Injection (raw queries, string formatting in queries)
- Command Injection (subprocess, os.system, os.popen with user input)
- Path Traversal (file operations with user-controlled paths)
- Server-Side Request Forgery (SSRF) (requests to user-controlled URLs)
- Cross-Site Scripting (XSS) (user input rendered in HTML without escaping)
- Insecure Deserialization (pickle.loads, yaml.load without SafeLoader)
- Hardcoded Secrets/Credentials (API keys, passwords, tokens in source)
- Broken Authentication (weak password requirements, missing auth checks)
- Insecure Direct Object References (IDOR) (accessing resources without ownership check)
- Race Conditions (TOCTOU, unprotected shared state)
- Unsafe Regular Expressions (ReDoS)
- Weak Cryptography (MD5/SHA1 for security, ECB mode, small key sizes)
- Information Disclosure (stack traces, debug modes, verbose errors in production)
- XML External Entity (XXE) (parsing XML without disabling external entities)
- Mass Assignment (accepting arbitrary fields from user input into models)

Report ONLY genuine vulnerabilities. If no vulnerabilities are found, return an empty JSON array [].

Respond with ONLY a JSON array. No markdown, no commentary, no explanation outside the JSON."""

USER_PROMPT_TEMPLATE = """Analyze the following Python source files for security vulnerabilities.

{file_sections}

Respond with a JSON array where each element has this exact structure:
{{
  "severity": "critical" | "high" | "medium" | "low" | "informational",
  "vulnerability_type": "Name of the vulnerability class",
  "file_path": "path/to/file.py",
  "line_number": 42,
  "code_snippet": "the vulnerable line(s) of code",
  "description": "One sentence summary of the vulnerability.",
  "explanation": "2-4 sentences explaining why this is vulnerable, how it could be exploited, and how to fix it."
}}

If no vulnerabilities are found, respond with exactly: []"""


def build_file_sections(chunk: Chunk) -> str:
    sections = []
    for file in chunk.files:
        lines = file.content.split("\n")
        numbered = "\n".join(f"{i+1}: {line}" for i, line in enumerate(lines))
        sections.append(f"=== File: {file.path} ===\n{numbered}")
    return "\n\n".join(sections)


def build_user_prompt(chunk: Chunk) -> str:
    file_sections = build_file_sections(chunk)
    return USER_PROMPT_TEMPLATE.format(file_sections=file_sections)
