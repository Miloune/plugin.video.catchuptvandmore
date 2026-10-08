#!/usr/bin/env python3
"""Audit a code tree for Python 3-only constructs that break CPython 2.7.

Two layers:

1. Python 3 AST: syntax that does not parse (or parses but cannot run) on 2.7:
   f-strings, ``yield from``, annotations, walrus, async, nonlocal,
   ``return <value>`` inside a generator, matmul, keyword-only and
   positional-only arguments, starred assignment, ``raise ... from ...``,
   dict unpacking ``{**d}``, multiple ``*``/``**`` unpacking in calls,
   ``from __future__ import annotations``, numeric separators, ``except*``.

2. Masked-source regexes (comments and string literals blanked out, so a
   mention in a comment never fires): runtime-only API differences invisible
   to the AST, e.g. ``bytes(x, encoding=...)``, ``open(..., encoding=...)``,
   ``str.removeprefix``, py3-only builtin exceptions, plus unguarded
   ``urllib.parse/request/error`` and ``http.cookiejar`` imports (Kodi 18
   needs a ``try/except ImportError`` fallback).

Dev directories (``tools/``, ``tests/``, ``.not_to_push/``) are skipped: they
run on the developer machine with Python 3, not on the Kodi 18 device.

Findings are printed as ``path:line: description`` and the tool exits non-zero
when at least one finding exists, so it can gate a pre-commit hook or CI job.
"""
import ast
import io
import os
import re
import sys
import tokenize
import warnings


PY3_ONLY_NODES = {
    "JoinedStr": "f-string (f'...')",
    "FormattedValue": "f-string interpolation",
    "YieldFrom": "yield from",
    "AsyncFunctionDef": "async def",
    "Await": "await",
    "AsyncFor": "async for",
    "AsyncWith": "async with",
    "Nonlocal": "nonlocal",
    "AnnAssign": "variable annotation (x: T = ...)",
    "NamedExpr": "walrus operator (:=)",
}

# Runtime-only Python 3 APIs, invisible to a Python 3 AST parse. Applied to
# source lines with comments and string literals blanked out.
RUNTIME_PATTERNS = [
    (re.compile(r"(?<![\w.])bytes\s*\([^;\n]*encoding\s*="),
     "bytes(..., encoding=) is Python 3 only (type error on py2)"),
    (re.compile(r"(?<![\w.])str\s*\([^;\n]*encoding\s*="),
     "str(..., encoding=) is Python 3 only (type error on py2)"),
    (re.compile(r"(?<![\w.])open\s*\([^;\n]*encoding\s*="),
     "open(..., encoding=) is Python 3 only (use io.open on py2)"),
    (re.compile(r"\.\s*removeprefix\s*\("), "str.removeprefix (Python 3.9+)"),
    (re.compile(r"\.\s*removesuffix\s*\("), "str.removesuffix (Python 3.9+)"),
    (re.compile(r"\.\s*fromisoformat\s*\("), "datetime.fromisoformat (Python 3.7+)"),
    (re.compile(r"\.\s*casefold\s*\("), "str.casefold (Python 3.3+)"),
    (re.compile(r"\.\s*format_map\s*\("), "str.format_map (Python 3.2+)"),
    (re.compile(r"\bsubprocess\s*\.\s*run\s*\("), "subprocess.run (Python 3.5+)"),
    (re.compile(r"\bexist_ok\s*="), "exist_ok= (Python 3.2+)"),
    (re.compile(r"\bfunctools\s*\.\s*lru_cache\b"), "functools.lru_cache (Python 3)"),
    (re.compile(r"(?<![\w.])super\s*\(\s*\)"), "zero-argument super() (Python 3 only)"),
    (re.compile(r"\btime\s*\.\s*monotonic\s*\("), "time.monotonic (Python 3.3+)"),
    (re.compile(r"\bdatetime\s*\.\s*timezone\b|\btimezone\s*\.\s*utc\b"),
     "datetime.timezone / timezone.utc (Python 3 only; use pytz)"),
    (re.compile(r"\.\s*timestamp\s*\(\s*\)"), "datetime.timestamp (Python 3.3+)"),
    (re.compile(r"\bxbmcvfs\s*\.\s*translatePath\b"),
     "xbmcvfs.translatePath is Kodi 19+ (use xbmc.translatePath)"),
    (re.compile(r"\bxbmcvfs\s*\.\s*makeLegalFilename\b"),
     "xbmcvfs.makeLegalFilename is Kodi 19+ (use xbmc.makeLegalFilename)"),
    (re.compile(r"\bmaxsplit\s*="), "split/rsplit maxsplit= keyword (Python 3 only)"),
    (re.compile(r"^\s*import\s+queue\b|^\s*from\s+queue\s+import\b"),
     "module 'queue' is Python 3 (use Queue on py2)"),
    (re.compile(r"^\s*import\s+configparser\b|^\s*from\s+configparser\s+import\b"),
     "module 'configparser' is Python 3 (use ConfigParser on py2)"),
    (re.compile(r"^\s*import\s+pathlib\b|^\s*from\s+pathlib\s+import\b"),
     "module 'pathlib' does not exist on Python 2.7"),
    (re.compile(r"^\s*import\s+typing\b|^\s*from\s+typing\s+import\b"),
     "module 'typing' does not exist on Python 2.7"),
    (re.compile(r"^\s*import\s+dataclasses\b|^\s*from\s+dataclasses\s+import\b"),
     "module 'dataclasses' (Python 3.7+, not available on Kodi 18)"),
    (re.compile(r"^\s*import\s+enum\b|^\s*from\s+enum\s+import\b"),
     "module 'enum' (Python 3.4+, no enum34 on Kodi 18)"),
    (re.compile(r"^\s*import\s+secrets\b|^\s*from\s+secrets\s+import\b"),
     "module 'secrets' (Python 3.6+)"),
    (re.compile(r"^\s*import\s+concurrent\.futures\b|^\s*from\s+concurrent\.futures\s+import\b"),
     "concurrent.futures (Python 3.2+)"),
    (re.compile(r"\bmath\s*\.\s*isqrt\s*\("), "math.isqrt (Python 3.8+)"),
    (re.compile(r"\bmath\s*\.\s*inf\b|\bmath\s*\.\s*nan\b"), "math.inf/math.nan (Python 3.5+)"),
    (re.compile(r"\bos\s*\.\s*scandir\s*\("), "os.scandir (Python 3.5+)"),
    (re.compile(r"\bos\s*\.\s*replace\s*\("), "os.replace (Python 3.3+)"),
    (re.compile(r"\bshutil\s*\.\s*which\s*\("), "shutil.which (Python 3.3+)"),
    (re.compile(r"\b(FileNotFoundError|PermissionError|ModuleNotFoundError|"
                r"NotADirectoryError|IsADirectoryError|RecursionError|"
                r"ConnectionResetError|ConnectionRefusedError|BrokenPipeError|"
                r"BlockingIOError|ChildProcessError|InterruptedError|"
                r"ProcessLookupError|TimeoutError)\b"),
     "Python 3-only builtin exception name"),
]

# Bare Python 3 imports that must stay behind a try/except ImportError on the
# Kodi 18 target (py2 modules: urllib/urllib2/urlparse/cookielib).
PY3_IMPORT_MODULES = frozenset((
    "urllib.parse", "urllib.request", "urllib.error", "http.cookiejar"))


def _handles_import_error(handler):
    if handler.type is None:
        return True
    node = handler.type
    if isinstance(node, ast.Name):
        return node.id == "ImportError"
    if isinstance(node, ast.Tuple):
        return any(isinstance(elt, ast.Name) and elt.id == "ImportError"
                   for elt in node.elts)
    return False


def _check_py3_imports(tree):
    """Flag urllib/http.cookiejar imports not guarded by try/except ImportError."""
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            candidates = [module] if module in PY3_IMPORT_MODULES else []
        elif isinstance(node, ast.Import):
            candidates = [alias.name for alias in node.names
                          if alias.name in PY3_IMPORT_MODULES]
        else:
            continue
        if not candidates:
            continue
        guarded = False
        parent = parents.get(node)
        while parent is not None:
            if isinstance(parent, ast.Try):
                if any(_handles_import_error(h) for h in parent.handlers):
                    guarded = True
                    break
            parent = parents.get(parent)
        if not guarded:
            for module in candidates:
                findings.append((node.lineno,
                                 "unguarded Python 3 import '%s' "
                                 "(wrap in try/except ImportError)" % module))
    return findings


def _decode(raw):
    """Decode source bytes using the declared PEP 263 encoding, if any."""
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
    except SyntaxError:
        encoding = "utf-8"
    try:
        return raw.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        return raw.decode("utf-8", "replace")


def _blank(chars, start, end):
    """Blank a token's span in a list-of-mutable-char-lines."""
    start_row, start_col = start
    end_row, end_col = end
    if start_row == end_row:
        row = chars[start_row - 1]
        for i in range(start_col, min(end_col, len(row))):
            row[i] = " "
        return
    for i in range(start_col, len(chars[start_row - 1])):
        chars[start_row - 1][i] = " "
    for r in range(start_row, end_row - 1):
        chars[r] = [" "] * len(chars[r])
    row = chars[end_row - 1]
    for i in range(0, min(end_col, len(row))):
        row[i] = " "


def _mask(src):
    """Blank comments/strings, returning (masked lines, underscore numbers).

    Masking keeps line/column positions so findings point at the right line,
    and prevents a pattern mentioned in a comment or a literal from firing.
    """
    lines = src.splitlines()
    chars = [list(line) for line in lines]
    underscores = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.NUMBER and "_" in tok.string:
                underscores.append((tok.start[0], tok.string))
            elif tok.type in (tokenize.COMMENT, tokenize.STRING):
                _blank(chars, tok.start, tok.end)
    except (tokenize.TokenError, IndentationError):
        pass
    return ["".join(row) for row in chars], underscores


def _check_ast(tree):
    findings = []
    for node in ast.walk(tree):
        name = type(node).__name__
        if name in PY3_ONLY_NODES:
            findings.append((getattr(node, "lineno", 0), PY3_ONLY_NODES[name]))
        # from __future__ import annotations (PEP 563, py3.7+ only)
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            for alias in node.names:
                if alias.name == "annotations":
                    findings.append((node.lineno,
                                     "from __future__ import annotations"))
        # matrix multiplication operator '@' (py3.5+)
        if isinstance(node, ast.BinOp) and type(node.op).__name__ == "MatMult":
            findings.append((getattr(node, "lineno", 0), "matmul '@' operator"))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            findings.extend(_check_function(node))
        # raise ... from ... (py3 only)
        if isinstance(node, ast.Raise) and node.cause is not None:
            findings.append((node.lineno, "raise ... from ... (Python 3 only)"))
        # dict unpacking {**d} (py3.5+)
        if isinstance(node, ast.Dict) and any(k is None for k in node.keys):
            findings.append((getattr(node, "lineno", 0),
                             "dict unpacking {**d} (Python 3.5+)"))
        # multiple * / ** unpacking in a call (py3.5+)
        if isinstance(node, ast.Call):
            starred = sum(1 for arg in node.args if isinstance(arg, ast.Starred))
            kw_unpacks = sum(1 for kw in node.keywords if kw.arg is None)
            if starred > 1:
                findings.append((node.lineno,
                                 "multiple * unpacking in call (Python 3.5+)"))
            if kw_unpacks > 1:
                findings.append((node.lineno,
                                 "multiple ** unpacking in call (Python 3.5+)"))
        # except* (py3.11+)
        if hasattr(ast, "TryStar") and isinstance(node, ast.TryStar):
            findings.append((node.lineno, "except* (Python 3.11 only)"))
    # starred assignment targets: a, *b = ... (py3 only)
    for target in _assignment_targets(tree):
        findings.append((target.lineno, "starred assignment target (Python 3 only)"))
    return findings


def _assignment_targets(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.For):
            targets = [node.target]
        elif isinstance(node, ast.With):
            targets = [item.optional_vars for item in node.items
                       if item.optional_vars is not None]
        else:
            continue
        for target in targets:
            for sub in ast.walk(target):
                if isinstance(sub, ast.Starred):
                    yield sub


def _check_function(func):
    findings = []
    if func.returns is not None:
        findings.append((func.lineno, "function return annotation"))
    for arg in list(func.args.args) + list(func.args.kwonlyargs):
        if getattr(arg, "annotation", None) is not None:
            findings.append((func.lineno,
                             "argument annotation on '%s'" % arg.arg))
    if getattr(func.args, "kwonlyargs", None):
        findings.append((func.lineno,
                         "keyword-only argument(s) in '%s' (Python 3 only)"
                         % func.name))
    if getattr(func.args, "posonlyargs", None):
        findings.append((func.lineno,
                         "positional-only argument(s) in '%s' (Python 3.8+)"
                         % func.name))
    findings.extend(_check_return_in_generator(func))
    return findings


def _own_body_nodes(func):
    """Yield nodes belonging to func's own scope (not nested def/class)."""
    stack = list(func.body)
    while stack:
        n = stack.pop()
        # Do not descend into nested function or class scopes
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                          ast.Lambda)):
            continue
        yield n
        for child in ast.iter_child_nodes(n):
            stack.append(child)


def _check_return_in_generator(func):
    """'return <value>' inside a generator is a SyntaxError on Python 2.7."""
    body = list(_own_body_nodes(func))
    is_generator = any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in body)
    if not is_generator:
        return []
    out = []
    for n in body:
        if isinstance(n, ast.Return) and n.value is not None:
            out.append((n.lineno,
                        "'return <value>' inside generator '%s' (py2.7 SyntaxError)"
                        % func.name))
    return out


def check_file(path):
    findings = []
    with open(path, "rb") as f:
        raw = f.read()
    try:
        # Expected on py2 regex strings; see AGENTS.md (do not "fix" them).
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(raw, filename=path)
    except SyntaxError as e:
        findings.append((getattr(e, "lineno", 0), "SYNTAX ERROR: %s" % e.msg))
        return findings

    findings.extend(_check_ast(tree))
    findings.extend(_check_py3_imports(tree))

    masked, underscores = _mask(_decode(raw))
    for lineno, number in underscores:
        findings.append((lineno,
                         "numeric literal with underscores (Python 3.6+): %s"
                         % number))
    for lineno, line in enumerate(masked, 1):
        for pattern, message in RUNTIME_PATTERNS:
            if pattern.search(line):
                findings.append((lineno, message))
    return findings


def main(root):
    total = 0
    files_with_issues = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # skip VCS, packaging and dev-only directories (they run with py3)
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "__pycache__", ".pytest_cache",
                                    "tests", ".not_to_push", "tools")]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            findings = check_file(path)
            if findings:
                files_with_issues += 1
                rel = os.path.relpath(path, root)
                for lineno, desc in sorted(findings):
                    total += 1
                    print("%s:%s: %s" % (rel, lineno, desc))
    print("\n=== %d issue(s) across %d file(s) ===" % (total, files_with_issues))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
