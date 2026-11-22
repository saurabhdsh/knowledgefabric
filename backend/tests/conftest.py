"""Every test run gets its own empty stores.

This file is imported before any ``app`` module, so the settings object is
built from these values. Tests never read or write the developer's fabrics,
database, or vector index, and never call a real model.
"""
from __future__ import annotations

import atexit
import os
import shutil
import tempfile

_ROOT = tempfile.mkdtemp(prefix="weave-tests-")

for _var, _sub in (
    ("KF_DATA_DIR", "data"),
    ("KF_UPLOAD_DIR", "uploads"),
    ("KF_CHROMA_DIR", "chroma"),
    ("KF_ONTOLOGY_DATA_DIR", "ontology"),
    ("KF_ONTOLOGY_UPLOAD_DIR", os.path.join("ontology", "uploads")),
):
    _path = os.path.join(_ROOT, _sub)
    os.makedirs(_path, exist_ok=True)
    os.environ[_var] = _path

os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_ROOT, 'data', 'test.db')}"
os.environ["OPENAI_API_KEY"] = ""
os.environ["AZURE_OPENAI_API_KEY"] = ""
os.environ["AZURE_OPENAI_ENDPOINT"] = ""
os.environ["BEDROCK_ENABLED"] = "false"
os.environ["ENABLE_JOB_WORKER"] = "false"
os.environ["SECRET_KEY"] = "test-only-signing-key-0123456789abcdef0123456789"
os.environ["WEAVE_ENV"] = "test"

atexit.register(shutil.rmtree, _ROOT, True)
