"""Workspace inventory / fingerprint."""
from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.codebase import LANGUAGE_BY_EXT
from app.services.codebase.ignore import iter_source_files

FRAMEWORK_MARKERS = {
    "package.json": "nodejs",
    "package-lock.json": "nodejs",
    "yarn.lock": "nodejs",
    "pnpm-lock.yaml": "nodejs",
    "requirements.txt": "python",
    "pyproject.toml": "python",
    "Pipfile": "python",
    "setup.py": "python",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "build.gradle.kts": "gradle",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "Gemfile": "ruby",
    "composer.json": "php",
    "Dockerfile": "docker",
    "docker-compose.yml": "docker",
    "docker-compose.yaml": "docker",
    "next.config.js": "nextjs",
    "next.config.mjs": "nextjs",
    "angular.json": "angular",
    "vue.config.js": "vue",
    "manage.py": "django",
    "app/main.py": "fastapi_or_flask",
}


def build_inventory(root: Path, *, max_files: int = 8000, extra_exclude: Optional[List[str]] = None) -> Dict[str, Any]:
    files = iter_source_files(root, max_files=max_files, extra_exclude=extra_exclude or [])
    lang_counts: Counter[str] = Counter()
    modules: Dict[str, int] = Counter()
    entrypoints: List[str] = []
    frameworks: set[str] = set()
    hasher = hashlib.sha256()

    for path in files:
        rel = path.relative_to(root).as_posix()
        hasher.update(rel.encode("utf-8"))
        try:
            hasher.update(str(path.stat().st_size).encode("utf-8"))
        except OSError:
            pass
        lang = LANGUAGE_BY_EXT.get(path.suffix.lower(), "other")
        lang_counts[lang] += 1
        top = rel.split("/", 1)[0] if "/" in rel else "(root)"
        modules[top] += 1
        name = path.name.lower()
        if name in {"main.py", "app.py", "index.js", "index.ts", "main.ts", "main.java", "program.cs", "main.go"}:
            entrypoints.append(rel)

    # Framework markers (walk limited set of known names at root and one level)
    for marker, label in FRAMEWORK_MARKERS.items():
        if (root / marker).exists():
            frameworks.add(label)
        else:
            # one-level search for common markers
            for child in root.iterdir() if root.is_dir() else []:
                if child.is_dir() and (child / Path(marker).name).exists() and "/" not in marker:
                    frameworks.add(label)
                    break

    # package.json name hint
    pkg = root / "package.json"
    if pkg.is_file():
        frameworks.add("nodejs")
    if (root / "pyproject.toml").is_file() or (root / "requirements.txt").is_file():
        frameworks.add("python")

    top_modules = [
        {"name": name, "file_count": count}
        for name, count in modules.most_common(40)
    ]

    return {
        "file_count": len(files),
        "languages": dict(lang_counts.most_common()),
        "frameworks": sorted(frameworks),
        "modules": top_modules,
        "module_count": len(modules),
        "entrypoints": entrypoints[:50],
        "workspace_fingerprint": hasher.hexdigest()[:32],
        "files_sample": [p.relative_to(root).as_posix() for p in files[:200]],
        "all_relative_files": [p.relative_to(root).as_posix() for p in files],
    }
