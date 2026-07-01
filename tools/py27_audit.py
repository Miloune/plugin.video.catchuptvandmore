#!/usr/bin/env python3
"""Audit a code tree for Python 3-only syntax that breaks CPython 2.7.

Walks every *.py file, parses it with the Python 3 AST, and reports any
construct that would raise SyntaxError or is unsupported on Python 2.7.
"""
import ast
import os
import sys


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


def check_file(path):
    findings = []
    with open(path, "rb") as f:
        src = f.read()
    try:
        tree = ast.parse(src, filename=path)
    except SyntaxError as e:
        findings.append((getattr(e, "lineno", 0), "SYNTAX ERROR: %s" % e.msg))
        return findings

    for node in ast.walk(tree):
        name = type(node).__name__
        if name in PY3_ONLY_NODES:
            findings.append((getattr(node, "lineno", 0), PY3_ONLY_NODES[name]))
        # from __future__ import annotations (PEP 563) - py3.7+ only
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            for alias in node.names:
                if alias.name == "annotations":
                    findings.append((node.lineno,
                                     "from __future__ import annotations"))
        # matrix multiplication operator '@' (py3.5+)
        if isinstance(node, ast.BinOp) and type(node.op).__name__ == "MatMult":
            findings.append((getattr(node, "lineno", 0), "matmul '@' operator"))
        # function-def annotations on args or returns, and
        # 'return <value>' inside a generator (SyntaxError on Python 2.7)
        if isinstance(node, (ast.FunctionDef,)):
            if node.returns is not None:
                findings.append((node.lineno, "function return annotation"))
            for arg in list(node.args.args) + list(node.args.kwonlyargs):
                if getattr(arg, "annotation", None) is not None:
                    findings.append((node.lineno,
                                     "argument annotation on '%s'" % arg.arg))
            findings.extend(_check_return_in_generator(node))
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



def main(root):
    total = 0
    files_with_issues = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # skip VCS and packaging dirs
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "__pycache__", ".pytest_cache",
                                    "tests", ".not_to_push")]
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
