"""
AST-based taint analysis for Python source code.

Traces data flow from known sources (user input) to known sinks (dangerous functions).
Returns only the suspicious code paths for LLM confirmation — dramatically reducing
tokens, cost, and false positives.

Architecture:
  1. Parse Python file into AST
  2. Identify SOURCES (user input entry points)
  3. Identify SINKS (dangerous function calls)
  4. Trace taint propagation through assignments and function args
  5. Return only paths where tainted data reaches a sink
"""

import ast
import logging
from dataclasses import dataclass, field
from typing import List, Set, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# --- Known Sources (user-controlled input) ---
SOURCES = {
    # Flask
    "request.args": "Flask query parameters",
    "request.form": "Flask form data",
    "request.data": "Flask raw request body",
    "request.json": "Flask JSON body",
    "request.values": "Flask combined args+form",
    "request.files": "Flask file uploads",
    "request.headers": "Flask request headers",
    "request.cookies": "Flask cookies",
    "request.get_json": "Flask JSON body",
    # Django
    "request.GET": "Django query parameters",
    "request.POST": "Django form data",
    "request.body": "Django raw body",
    "request.META": "Django request metadata",
    # FastAPI
    "Query": "FastAPI query parameter",
    "Body": "FastAPI request body",
    "Form": "FastAPI form data",
    "Header": "FastAPI header",
    "Cookie": "FastAPI cookie",
    # Starlette/FastAPI
    "request.query_params": "FastAPI/Starlette query parameters",
    "request.path_params": "FastAPI/Starlette path parameters",
    # General
    "input": "Python input()",
    "sys.argv": "Command line arguments",
    "os.environ": "Environment variables",
    "sys.stdin": "Standard input",
}

# --- Known Sinks (dangerous operations) ---
SINKS = {
    # SQL Injection
    "cursor.execute": {"cwe": "CWE-89", "vuln_type": "SQL Injection", "severity": "critical"},
    "db.execute": {"cwe": "CWE-89", "vuln_type": "SQL Injection", "severity": "critical"},
    "session.execute": {"cwe": "CWE-89", "vuln_type": "SQL Injection", "severity": "critical"},
    "engine.execute": {"cwe": "CWE-89", "vuln_type": "SQL Injection", "severity": "critical"},
    "connection.execute": {"cwe": "CWE-89", "vuln_type": "SQL Injection", "severity": "critical"},
    # Command Injection
    "os.system": {"cwe": "CWE-78", "vuln_type": "Command Injection", "severity": "critical"},
    "os.popen": {"cwe": "CWE-78", "vuln_type": "Command Injection", "severity": "critical"},
    "subprocess.call": {"cwe": "CWE-78", "vuln_type": "Command Injection", "severity": "critical"},
    "subprocess.run": {"cwe": "CWE-78", "vuln_type": "Command Injection", "severity": "critical"},
    "subprocess.Popen": {"cwe": "CWE-78", "vuln_type": "Command Injection", "severity": "critical"},
    "subprocess.check_output": {"cwe": "CWE-78", "vuln_type": "Command Injection", "severity": "critical"},
    # Path Traversal
    "open": {"cwe": "CWE-22", "vuln_type": "Path Traversal", "severity": "high"},
    "os.path.join": {"cwe": "CWE-22", "vuln_type": "Path Traversal", "severity": "high"},
    "shutil.copy": {"cwe": "CWE-22", "vuln_type": "Path Traversal", "severity": "high"},
    "shutil.move": {"cwe": "CWE-22", "vuln_type": "Path Traversal", "severity": "high"},
    # XSS / Template Injection
    "render_template_string": {"cwe": "CWE-79", "vuln_type": "Server-Side Template Injection", "severity": "high"},
    "Markup": {"cwe": "CWE-79", "vuln_type": "Cross-Site Scripting (XSS)", "severity": "high"},
    "jinja2.from_string": {"cwe": "CWE-79", "vuln_type": "Server-Side Template Injection", "severity": "high"},
    "Template": {"cwe": "CWE-79", "vuln_type": "Server-Side Template Injection", "severity": "high"},
    # SSRF
    "requests.get": {"cwe": "CWE-918", "vuln_type": "Server-Side Request Forgery (SSRF)", "severity": "high"},
    "requests.post": {"cwe": "CWE-918", "vuln_type": "Server-Side Request Forgery (SSRF)", "severity": "high"},
    "requests.put": {"cwe": "CWE-918", "vuln_type": "Server-Side Request Forgery (SSRF)", "severity": "high"},
    "requests.delete": {"cwe": "CWE-918", "vuln_type": "Server-Side Request Forgery (SSRF)", "severity": "high"},
    "urllib.request.urlopen": {"cwe": "CWE-918", "vuln_type": "Server-Side Request Forgery (SSRF)", "severity": "high"},
    "httpx.get": {"cwe": "CWE-918", "vuln_type": "Server-Side Request Forgery (SSRF)", "severity": "high"},
    "httpx.post": {"cwe": "CWE-918", "vuln_type": "Server-Side Request Forgery (SSRF)", "severity": "high"},
    # Deserialization
    "pickle.loads": {"cwe": "CWE-502", "vuln_type": "Insecure Deserialization", "severity": "critical"},
    "pickle.load": {"cwe": "CWE-502", "vuln_type": "Insecure Deserialization", "severity": "critical"},
    "yaml.load": {"cwe": "CWE-502", "vuln_type": "Insecure Deserialization", "severity": "high"},
    "yaml.unsafe_load": {"cwe": "CWE-502", "vuln_type": "Insecure Deserialization", "severity": "critical"},
    "marshal.loads": {"cwe": "CWE-502", "vuln_type": "Insecure Deserialization", "severity": "critical"},
    # Code Execution
    "eval": {"cwe": "CWE-95", "vuln_type": "Code Injection", "severity": "critical"},
    "exec": {"cwe": "CWE-95", "vuln_type": "Code Injection", "severity": "critical"},
    "compile": {"cwe": "CWE-95", "vuln_type": "Code Injection", "severity": "high"},
    # XXE
    "xml.etree.ElementTree.parse": {"cwe": "CWE-611", "vuln_type": "XML External Entity (XXE)", "severity": "high"},
    "lxml.etree.parse": {"cwe": "CWE-611", "vuln_type": "XML External Entity (XXE)", "severity": "high"},
}

# --- Patterns that indicate string formatting with variables (potential injection) ---
DANGEROUS_STRING_OPS = {"format", "replace", "%", "f-string", "+"}


@dataclass
class TaintSource:
    """A location where user input enters the program."""
    variable: str
    source_type: str
    line: int
    col: int


@dataclass
class TaintSink:
    """A location where a dangerous operation occurs."""
    function: str
    sink_info: Dict
    line: int
    col: int
    args_code: str


@dataclass
class TaintPath:
    """A traced path from source to sink."""
    source: TaintSource
    sink: TaintSink
    intermediates: List[str]  # variable names in the chain
    code_lines: List[Tuple[int, str]]  # (line_number, code) along the path
    confidence: str  # "high", "medium", "low"


@dataclass
class TaintResult:
    """Complete taint analysis result for a file."""
    file_path: str
    paths: List[TaintPath] = field(default_factory=list)
    sources_found: int = 0
    sinks_found: int = 0
    parse_error: Optional[str] = None


def _get_attr_chain(node: ast.AST) -> str:
    """Convert an attribute access chain to string: request.args.get -> 'request.args.get'"""
    if isinstance(node, ast.Attribute):
        parent = _get_attr_chain(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    elif isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Call):
        return _get_attr_chain(node.func)
    return ""


def _get_call_name(node: ast.Call) -> str:
    """Get the full name of a function call."""
    return _get_attr_chain(node.func)


def _node_to_source(node: ast.AST, lines: List[str]) -> str:
    """Get the source code for a node from the original lines."""
    if hasattr(node, 'lineno') and node.lineno <= len(lines):
        line = lines[node.lineno - 1].strip()
        return line
    return ""


def _is_string_concat_or_format(node: ast.AST) -> bool:
    """Check if a node involves string concatenation or formatting."""
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, (ast.Add, ast.Mod)):
            return True
    if isinstance(node, ast.JoinedStr):  # f-string
        return True
    if isinstance(node, ast.Call):
        name = _get_call_name(node)
        if name.endswith(".format"):
            return True
    return False


class TaintTracer(ast.NodeVisitor):
    """AST visitor that traces taint from sources to sinks."""

    def __init__(self, source_code: str, file_path: str):
        self.source_code = source_code
        self.lines = source_code.split("\n")
        self.file_path = file_path

        # Tainted variables: variable_name -> TaintSource
        self.tainted: Dict[str, TaintSource] = {}

        # Found sources and sinks
        self.sources: List[TaintSource] = []
        self.sinks: List[TaintSink] = []

        # Traced paths
        self.paths: List[TaintPath] = []

        # Track function parameters that come from route handlers
        self.route_params: Set[str] = set()

    def analyze(self) -> TaintResult:
        """Run the full analysis."""
        try:
            tree = ast.parse(self.source_code)
        except SyntaxError as e:
            return TaintResult(
                file_path=self.file_path,
                parse_error=f"SyntaxError: {e}"
            )

        # First pass: find route handlers and mark their params as tainted
        self._find_route_handlers(tree)

        # Second pass: trace taint through the AST
        self.visit(tree)

        return TaintResult(
            file_path=self.file_path,
            paths=self.paths,
            sources_found=len(self.sources),
            sinks_found=len(self.sinks),
        )

    def _find_route_handlers(self, tree: ast.Module):
        """Find Flask/FastAPI route handler functions and mark params as tainted."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check for route decorators
                for decorator in node.decorator_list:
                    dec_name = _get_attr_chain(decorator) if not isinstance(decorator, ast.Call) else _get_call_name(decorator)
                    if any(route in dec_name for route in ["route", "get", "post", "put", "delete", "patch"]):
                        # All parameters except 'self' and 'cls' are potentially user-controlled
                        for arg in node.args.args:
                            if arg.arg not in ("self", "cls"):
                                self.route_params.add(arg.arg)
                                source = TaintSource(
                                    variable=arg.arg,
                                    source_type=f"Route parameter '{arg.arg}'",
                                    line=node.lineno,
                                    col=node.col_offset,
                                )
                                self.sources.append(source)
                                self.tainted[arg.arg] = source

    def visit_Assign(self, node: ast.Assign):
        """Track taint through variable assignments."""
        # Check if RHS contains a tainted value or a source
        rhs_taint = self._check_tainted(node.value)

        if rhs_taint:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.tainted[target.id] = rhs_taint
                elif isinstance(target, ast.Tuple):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name):
                            self.tainted[elt.id] = rhs_taint

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """Check function calls for sinks receiving tainted data."""
        call_name = _get_call_name(node)

        # Check if this is a source
        for source_pattern, source_desc in SOURCES.items():
            if source_pattern in call_name or call_name.endswith(source_pattern):
                # This call returns user input
                pass  # Handled in visit_Assign when result is assigned

        # Check if this is a sink
        sink_info = None
        for sink_pattern, info in SINKS.items():
            if call_name == sink_pattern or call_name.endswith(f".{sink_pattern}") or call_name.endswith(sink_pattern):
                sink_info = info
                break

        if sink_info:
            sink = TaintSink(
                function=call_name,
                sink_info=sink_info,
                line=node.lineno,
                col=node.col_offset,
                args_code=_node_to_source(node, self.lines),
            )
            self.sinks.append(sink)

            # Check if any argument is tainted
            for arg in node.args:
                taint_source = self._check_tainted(arg)
                if taint_source:
                    self._record_path(taint_source, sink, arg)

            for kw in node.keywords:
                if kw.value:
                    taint_source = self._check_tainted(kw.value)
                    if taint_source:
                        self._record_path(taint_source, sink, kw.value)

            # Check for string formatting in arguments (e.g., f"SELECT * FROM {user_input}")
            for arg in node.args:
                if _is_string_concat_or_format(arg):
                    inner_taint = self._check_tainted_in_format(arg)
                    if inner_taint:
                        self._record_path(inner_taint, sink, arg)

        self.generic_visit(node)

    def _check_tainted(self, node: ast.AST) -> Optional[TaintSource]:
        """Check if an AST node contains tainted data."""
        if isinstance(node, ast.Name):
            if node.id in self.tainted:
                return self.tainted[node.id]

        elif isinstance(node, ast.Attribute):
            chain = _get_attr_chain(node)
            # Check against known sources
            for source_pattern, source_desc in SOURCES.items():
                if source_pattern in chain:
                    source = TaintSource(
                        variable=chain,
                        source_type=source_desc,
                        line=node.lineno,
                        col=node.col_offset,
                    )
                    self.sources.append(source)
                    return source
            # Check if base is tainted
            if isinstance(node.value, ast.Name) and node.value.id in self.tainted:
                return self.tainted[node.value.id]

        elif isinstance(node, ast.Subscript):
            # request.args["key"] or request.args.get("key")
            chain = _get_attr_chain(node.value)
            for source_pattern, source_desc in SOURCES.items():
                if source_pattern in chain:
                    source = TaintSource(
                        variable=chain,
                        source_type=source_desc,
                        line=node.lineno,
                        col=node.col_offset,
                    )
                    self.sources.append(source)
                    return source

        elif isinstance(node, ast.Call):
            call_name = _get_call_name(node)
            # request.args.get("key")
            for source_pattern, source_desc in SOURCES.items():
                if source_pattern in call_name:
                    source = TaintSource(
                        variable=call_name,
                        source_type=source_desc,
                        line=node.lineno,
                        col=node.col_offset,
                    )
                    self.sources.append(source)
                    return source
            # Check if the function itself returns tainted data
            if call_name in self.tainted:
                return self.tainted[call_name]

        elif isinstance(node, ast.BinOp):
            # String concatenation: tainted + something
            left_taint = self._check_tainted(node.left)
            if left_taint:
                return left_taint
            right_taint = self._check_tainted(node.right)
            if right_taint:
                return right_taint

        elif isinstance(node, ast.JoinedStr):
            # f-string: check all values
            for value in node.values:
                if isinstance(value, ast.FormattedValue):
                    taint = self._check_tainted(value.value)
                    if taint:
                        return taint

        return None

    def _check_tainted_in_format(self, node: ast.AST) -> Optional[TaintSource]:
        """Check for tainted data inside string formatting operations."""
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            # "SELECT * FROM %s" % user_input
            return self._check_tainted(node.right)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = self._check_tainted(node.left)
            right = self._check_tainted(node.right)
            return left or right
        elif isinstance(node, ast.Call):
            call_name = _get_call_name(node)
            if call_name.endswith(".format"):
                for arg in node.args:
                    taint = self._check_tainted(arg)
                    if taint:
                        return taint
                for kw in node.keywords:
                    if kw.value:
                        taint = self._check_tainted(kw.value)
                        if taint:
                            return taint
        elif isinstance(node, ast.JoinedStr):
            return self._check_tainted(node)
        return None

    def _record_path(self, source: TaintSource, sink: TaintSink, tainted_node: ast.AST):
        """Record a taint path from source to sink (deduplicated)."""
        # Dedup: skip if we already have a path with same source line + sink line
        for existing in self.paths:
            if existing.source.line == source.line and existing.sink.line == sink.line:
                return
        # Gather code lines between source and sink
        start_line = min(source.line, sink.line)
        end_line = max(source.line, sink.line)
        code_lines = []
        for i in range(start_line, min(end_line + 1, len(self.lines) + 1)):
            code_lines.append((i, self.lines[i - 1] if i <= len(self.lines) else ""))

        # Determine confidence
        if source.line == sink.line:
            confidence = "high"  # Direct: source used in sink on same line
        elif end_line - start_line < 10:
            confidence = "high"  # Close proximity
        elif end_line - start_line < 30:
            confidence = "medium"
        else:
            confidence = "low"  # Far apart — may have sanitization we missed

        path = TaintPath(
            source=source,
            sink=sink,
            intermediates=[],
            code_lines=code_lines,
            confidence=confidence,
        )
        self.paths.append(path)
        logger.debug("[Taint] Path found: %s -> %s (line %d -> %d, confidence: %s)",
                     source.variable, sink.function, source.line, sink.line, confidence)


def analyze_file_taint(source_code: str, file_path: str) -> TaintResult:
    """Analyze a single Python file for taint paths from sources to sinks."""
    tracer = TaintTracer(source_code, file_path)
    result = tracer.analyze()
    logger.info("[Taint] %s: %d sources, %d sinks, %d paths",
                file_path, result.sources_found, result.sinks_found, len(result.paths))
    return result


def format_taint_paths_for_llm(result: TaintResult) -> Optional[str]:
    """Format taint analysis results into a focused prompt section for the LLM.
    Returns None if no suspicious paths were found."""
    if not result.paths:
        return None

    sections = []
    for i, path in enumerate(result.paths):
        code_block = "\n".join(f"{ln}: {code}" for ln, code in path.code_lines)
        sections.append(
            f"--- Suspicious Path {i+1} ({path.confidence} confidence) ---\n"
            f"Source: {path.source.variable} ({path.source.source_type}) at line {path.source.line}\n"
            f"Sink: {path.sink.function} ({path.sink.sink_info['vuln_type']}, {path.sink.sink_info['cwe']}) at line {path.sink.line}\n"
            f"Code:\n{code_block}\n"
        )

    return "\n".join(sections)


def get_pre_findings(result: TaintResult) -> List[Dict]:
    """Convert taint paths into preliminary findings that can be sent to LLM for confirmation
    or used directly as high-confidence findings."""
    findings = []
    for path in result.paths:
        sink_line_code = ""
        for ln, code in path.code_lines:
            if ln == path.sink.line:
                sink_line_code = code.strip()
                break

        findings.append({
            "severity": path.sink.sink_info["severity"],
            "vulnerability_type": path.sink.sink_info["vuln_type"],
            "cwe": path.sink.sink_info["cwe"],
            "file_path": result.file_path,
            "line_number": path.sink.line,
            "source": path.source.variable,
            "source_type": path.source.source_type,
            "sink": path.sink.function,
            "code_snippet": sink_line_code or path.sink.args_code,
            "confidence": path.confidence,
            "taint_trace": f"{path.source.variable} ({path.source.source_type}) -> {path.sink.function}",
        })

    return findings
