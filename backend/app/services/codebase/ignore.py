"""Ignore rules for codebase walks."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Set

from app.services.codebase import BINARY_EXTENSIONS, DEFAULT_IGNORE_DIRS


def load_gitignore_patterns(root: Path) -> List[str]:
    patterns: List[str] = []
    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        return patterns
    try:
        for line in gitignore.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            patterns.append(line.rstrip("/"))
    except OSError:
        return patterns
    return patterns


def _matches_gitignore(rel_posix: str, name: str, patterns: Iterable[str]) -> bool:
    for pat in patterns:
        if pat.startswith("!"):
            continue
        clean = pat[1:] if pat.startswith("/") else pat
        if clean.endswith("/"):
            clean = clean[:-1]
        if name == clean or rel_posix == clean or rel_posix.startswith(clean + "/"):
            return True
        if clean.startswith("*") and name.endswith(clean[1:]):
            return True
        if clean.endswith("*") and name.startswith(clean[:-1]):
            return True
    return False


def should_skip_dir(name: str, rel_posix: str, gitignore: Iterable[str]) -> bool:
    if name in DEFAULT_IGNORE_DIRS or name.startswith("."):
        if name in {".github", ".gitlab"}:
            return False
        if name.startswith(".") and name not in {".github", ".gitlab"}:
            # keep walking into non-default hidden only if not ignored
            if name in DEFAULT_IGNORE_DIRS:
                return True
            if name not in {".github", ".gitlab"} and name.startswith("."):
                return name in DEFAULT_IGNORE_DIRS or name in {
                    ".git", ".svn", ".hg", ".venv", ".tox", ".mypy_cache", ".pytest_cache", ".idea", ".vscode", ".next"
                }
    if name in DEFAULT_IGNORE_DIRS:
        return True
    return _matches_gitignore(rel_posix, name, gitignore)


def should_skip_file(path: Path, rel_posix: str, gitignore: Iterable[str], extra_exclude: Set[str] | None = None) -> bool:
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    if path.name.startswith(".") and path.name not in {".env.example", ".gitignore", ".dockerignore"}:
        # allow common config dots selectively
        if path.name not in {".eslintrc", ".prettierrc", ".editorconfig", ".npmrc"}:
            if path.suffix not in {".yml", ".yaml", ".json", ".toml", ".md"}:
                pass
    if extra_exclude:
        for ex in extra_exclude:
            if rel_posix == ex or rel_posix.startswith(ex.rstrip("/") + "/") or path.name == ex:
                return True
    return _matches_gitignore(rel_posix, path.name, gitignore)


def iter_source_files(
    root: Path,
    *,
    max_files: int = 8000,
    extra_exclude: Iterable[str] | None = None,
) -> List[Path]:
    gitignore = load_gitignore_patterns(root)
    exclude = {e.strip().replace("\\", "/") for e in (extra_exclude or []) if e and e.strip()}
    files: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        rel_dir = current.relative_to(root).as_posix()
        if rel_dir == ".":
            rel_dir = ""
        kept: List[str] = []
        for d in list(dirnames):
            child_rel = f"{rel_dir}/{d}" if rel_dir else d
            if should_skip_dir(d, child_rel, gitignore) or (exclude and any(
                child_rel == e or child_rel.startswith(e.rstrip("/") + "/") for e in exclude
            )):
                continue
            kept.append(d)
        dirnames[:] = kept
        for name in filenames:
            path = current / name
            rel = path.relative_to(root).as_posix()
            if should_skip_file(path, rel, gitignore, exclude):
                continue
            try:
                if path.stat().st_size > 1_500_000:
                    continue
            except OSError:
                continue
            files.append(path)
            if len(files) >= max_files:
                return files
    return files
