"""Safe zip extract and git clone (public / PAT / SSH)."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlparse, urlunparse

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_UNCOMPRESSED_BYTES = 400 * 1024 * 1024  # 400 MB
MAX_ZIP_ENTRIES = 25_000


def codebase_root_for(fabric_id: str) -> Path:
    root = Path(settings.UPLOAD_DIR) / "codebase" / fabric_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def workspace_dir(fabric_id: str) -> Path:
    return codebase_root_for(fabric_id) / "workspace"


def _is_within_directory(directory: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def extract_zip_safely(zip_path: Path, dest: Path) -> Path:
    """Extract zip with zip-slip and size guards. Returns workspace root."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    total = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        infos = zf.infolist()
        if len(infos) > MAX_ZIP_ENTRIES:
            raise ValueError(f"Zip has too many entries ({len(infos)} > {MAX_ZIP_ENTRIES}).")
        for info in infos:
            total += info.file_size
            if total > MAX_UNCOMPRESSED_BYTES:
                raise ValueError("Uncompressed zip exceeds size limit.")
            member_path = dest / info.filename
            if not _is_within_directory(dest, member_path):
                raise ValueError(f"Illegal zip path: {info.filename}")
        zf.extractall(dest)

    return _normalize_workspace_root(dest)


def _normalize_workspace_root(dest: Path) -> Path:
    """If zip has a single top-level folder, use that as workspace."""
    children = [p for p in dest.iterdir() if p.name != "__MACOSX"]
    if len(children) == 1 and children[0].is_dir():
        nested = children[0]
        # Move contents up into dest/workspace style: return nested as root
        return nested
    return dest


def save_upload_bytes(fabric_id: str, filename: str, data: bytes) -> Path:
    root = codebase_root_for(fabric_id)
    safe_name = Path(filename).name or "upload.zip"
    target = root / safe_name
    target.write_bytes(data)
    return target


def clone_git_repo(
    *,
    fabric_id: str,
    git_url: str,
    git_ref: Optional[str] = None,
    auth_mode: str = "none",
    pat: Optional[str] = None,
    ssh_private_key: Optional[str] = None,
) -> Path:
    dest = workspace_dir(fabric_id)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    auth_mode = (auth_mode or "none").strip().lower()
    url = (git_url or "").strip()
    if not url:
        raise ValueError("git_url is required.")

    env = os.environ.copy()
    ssh_key_path: Optional[Path] = None
    clone_url = url

    try:
        if auth_mode == "pat":
            if not pat:
                raise ValueError("PAT is required for auth_mode=pat.")
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                raise ValueError("PAT auth requires an https:// git URL.")
            user = "git"
            token = quote(pat, safe="")
            netloc = f"{user}:{token}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            clone_url = urlunparse((parsed.scheme, netloc, parsed.path, "", "", ""))
        elif auth_mode == "ssh":
            if not ssh_private_key:
                raise ValueError("SSH private key is required for auth_mode=ssh.")
            key_dir = Path(tempfile.mkdtemp(prefix="weave_ssh_"))
            ssh_key_path = key_dir / "id_key"
            key_text = ssh_private_key.strip() + "\n"
            ssh_key_path.write_text(key_text, encoding="utf-8")
            os.chmod(ssh_key_path, 0o600)
            known_hosts = key_dir / "known_hosts"
            known_hosts.write_text("", encoding="utf-8")
            env["GIT_SSH_COMMAND"] = (
                f"ssh -i {ssh_key_path} -o StrictHostKeyChecking=accept-new "
                f"-o UserKnownHostsFile={known_hosts}"
            )
        elif auth_mode not in ("none", ""):
            raise ValueError(f"Unsupported auth_mode: {auth_mode}")

        cmd = ["git", "clone", "--depth", "1"]
        if git_ref:
            cmd.extend(["--branch", git_ref])
        cmd.extend([clone_url, str(dest)])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=600,
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "git clone failed").strip()
            # Scrub token from error if present
            if pat:
                err = err.replace(pat, "***")
            raise RuntimeError(f"Git clone failed: {err[:800]}")
        return dest
    finally:
        if ssh_key_path and ssh_key_path.parent.exists():
            shutil.rmtree(ssh_key_path.parent, ignore_errors=True)


def prepare_workspace_from_zip(fabric_id: str, zip_path: Path) -> Path:
    extract_to = codebase_root_for(fabric_id) / "extracted"
    root = extract_zip_safely(zip_path, extract_to)
    workspace = workspace_dir(fabric_id)
    if workspace.exists():
        shutil.rmtree(workspace)
    # If root is already under extract_to, move/copy to workspace
    if root.resolve() == extract_to.resolve():
        shutil.move(str(extract_to), str(workspace))
    else:
        shutil.copytree(root, workspace)
        shutil.rmtree(extract_to, ignore_errors=True)
    return workspace
