"""Language parsers for structural analysis."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class ParsedSymbol:
    name: str
    kind: str  # class | function | method | interface
    line: int = 0


@dataclass
class ParsedFile:
    path: str
    language: str
    imports: List[str] = field(default_factory=list)
    symbols: List[ParsedSymbol] = field(default_factory=list)
    api_hints: List[str] = field(default_factory=list)
    data_hints: List[str] = field(default_factory=list)


def parse_file(path: Path, rel: str, language: str, text: str) -> ParsedFile:
    if language == "python":
        return _parse_python(rel, text)
    if language in ("javascript", "typescript"):
        return _parse_js_ts(rel, language, text)
    if language == "java":
        return _parse_java(rel, text)
    return _parse_heuristic(rel, language, text)


def _parse_python(rel: str, text: str) -> ParsedFile:
    result = ParsedFile(path=rel, language="python")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return _parse_heuristic(rel, "python", text)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result.imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                result.imports.append(node.module.split(".")[0])
        elif isinstance(node, ast.ClassDef):
            result.symbols.append(ParsedSymbol(node.name, "class", getattr(node, "lineno", 0)))
            lower = node.name.lower()
            if any(x in lower for x in ("model", "entity", "schema", "dto", "record")):
                result.data_hints.append(node.name)
        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            result.symbols.append(ParsedSymbol(node.name, "function", getattr(node, "lineno", 0)))
            for dec in node.decorator_list:
                dec_s = ast.unparse(dec) if hasattr(ast, "unparse") else ""
                if any(k in dec_s for k in ("route", "get", "post", "put", "delete", "api", "router")):
                    result.api_hints.append(node.name)

    # FastAPI / Flask style
    for m in re.finditer(r"@(?:app|router)\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)", text):
        result.api_hints.append(f"{m.group(1).upper()} {m.group(2)}")
    return result


def _parse_js_ts(rel: str, language: str, text: str) -> ParsedFile:
    result = ParsedFile(path=rel, language=language)
    for m in re.finditer(
        r"""(?:import\s+(?:[\s\S]*?\s+from\s+)?['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\))""",
        text,
    ):
        mod = m.group(1) or m.group(2)
        if mod:
            result.imports.append(mod.split("/")[0].lstrip("."))
    for m in re.finditer(r"(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)", text):
        result.symbols.append(ParsedSymbol(m.group(1), "function"))
    for m in re.finditer(r"(?:export\s+)?(?:default\s+)?class\s+([A-Za-z0-9_]+)", text):
        result.symbols.append(ParsedSymbol(m.group(1), "class"))
    for m in re.finditer(r"(?:export\s+)?(?:default\s+)?(?:interface|type)\s+([A-Za-z0-9_]+)", text):
        result.symbols.append(ParsedSymbol(m.group(1), "interface"))
        if any(x in m.group(1).lower() for x in ("model", "entity", "dto", "schema")):
            result.data_hints.append(m.group(1))
    for m in re.finditer(
        r"""(?:app|router|Router)\.(get|post|put|patch|delete)\(\s*['`]([^'"`]+)""",
        text,
        re.I,
    ):
        result.api_hints.append(f"{m.group(1).upper()} {m.group(2)}")
    for m in re.finditer(r"""@(Get|Post|Put|Patch|Delete)\(\s*['"]([^'"]+)""", text):
        result.api_hints.append(f"{m.group(1).upper()} {m.group(2)}")
    return result


def _parse_java(rel: str, text: str) -> ParsedFile:
    result = ParsedFile(path=rel, language="java")
    for m in re.finditer(r"import\s+([a-zA-Z0-9_.]+)\s*;", text):
        parts = m.group(1).split(".")
        result.imports.append(parts[0] if len(parts) < 3 else ".".join(parts[:2]))
    for m in re.finditer(r"(?:public\s+|private\s+|protected\s+)?(?:abstract\s+)?class\s+([A-Za-z0-9_]+)", text):
        result.symbols.append(ParsedSymbol(m.group(1), "class"))
        if any(x in m.group(1).lower() for x in ("entity", "model", "dto", "repository")):
            result.data_hints.append(m.group(1))
    for m in re.finditer(r"(?:public\s+|private\s+|protected\s+)?interface\s+([A-Za-z0-9_]+)", text):
        result.symbols.append(ParsedSymbol(m.group(1), "interface"))
    for m in re.finditer(
        r"@(?:Get|Post|Put|Patch|Delete|Request)Mapping\(\s*(?:value\s*=\s*)?['\"]([^'\"]+)",
        text,
    ):
        result.api_hints.append(m.group(1))
    return result


def _parse_heuristic(rel: str, language: str, text: str) -> ParsedFile:
    result = ParsedFile(path=rel, language=language)
    for m in re.finditer(r"(?:import|require|include|use)\s+[\"']?([A-Za-z0-9_./\\-]+)", text):
        result.imports.append(m.group(1).split("/")[0].split("\\")[0])
    for m in re.finditer(r"(?:class|interface|struct|fn|func|def)\s+([A-Za-z0-9_]+)", text):
        result.symbols.append(ParsedSymbol(m.group(1), "symbol"))
    return result
