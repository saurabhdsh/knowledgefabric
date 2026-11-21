"""Embedding models for the vector index (Release 2.0, Phase 0).

Every vector in the index is produced by a named, versioned model, and each
model writes to its own Chroma collection, so vectors from different models are
never compared with each other.

Providers (``EMBEDDING_PROVIDER``):

* ``onnx-minilm`` (default) — all-MiniLM-L6-v2 run with onnxruntime. Semantic,
  384 dimensions, no Torch needed at query time.
* ``sentence-transformers`` — any SentenceTransformer model (``MODEL_NAME``).
* ``hash`` — stable lexical feature hashing. Not semantic. Only for tests and
  air-gapped installs, and it must be selected explicitly: the service never
  falls back to it silently.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import tarfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingUnavailableError(RuntimeError):
    """The configured embedding model could not be loaded or run."""


class EmbeddingModel:
    """Interface every embedding provider implements."""

    id: str = ""
    provider: str = ""
    model_name: str = ""
    revision: str = ""
    dim: int = 0
    semantic: bool = False

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        raise NotImplementedError

    def info(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "provider": self.provider,
            "model": self.model_name,
            "revision": self.revision,
            "dimension": self.dim,
            "semantic": self.semantic,
            "collection": collection_name_for(self.id),
        }


# ---------------------------------------------------------------------------
# ONNX all-MiniLM-L6-v2
# ---------------------------------------------------------------------------

_MINILM_NAME = "all-MiniLM-L6-v2"
_MINILM_ARCHIVE_URL = "https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz"
_MINILM_ARCHIVE_SHA256 = "913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3"
_MINILM_MODEL_SHA256 = "4f148ba8ae9c2c7fbee4af2b132db8d06c6a6545b47fc83bbb98c3d22b8393e6"
_MINILM_MAX_TOKENS = 256


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class OnnxMiniLMModel(EmbeddingModel):
    id = "onnx-all-MiniLM-L6-v2"
    provider = "onnx-minilm"
    model_name = f"sentence-transformers/{_MINILM_NAME}"
    revision = _MINILM_MODEL_SHA256[:12]
    dim = 384
    semantic = True

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._session = None
        self._tokenizer = None
        self._input_names: List[str] = []

    # -- model files -------------------------------------------------------

    def _candidate_dirs(self) -> List[Path]:
        return [
            Path(settings.EMBEDDING_MODEL_DIR) / _MINILM_NAME / "onnx",
            # Baked into the Docker image at build time.
            Path("/opt/weave/embeddings") / _MINILM_NAME / "onnx",
            # Chroma's own cache, if it already downloaded the same files.
            Path.home() / ".cache" / "chroma" / "onnx_models" / _MINILM_NAME / "onnx",
        ]

    def _locate_model_dir(self) -> Optional[Path]:
        for candidate in self._candidate_dirs():
            if (candidate / "model.onnx").is_file() and (candidate / "tokenizer.json").is_file():
                return candidate
        return None

    def _download(self) -> Path:
        import requests

        target_root = Path(settings.EMBEDDING_MODEL_DIR) / _MINILM_NAME
        target_root.mkdir(parents=True, exist_ok=True)
        archive = target_root / "onnx.tar.gz"
        logger.info("Downloading embedding model %s to %s", _MINILM_NAME, target_root)
        with requests.get(_MINILM_ARCHIVE_URL, stream=True, timeout=(15, 600)) as resp:
            resp.raise_for_status()
            with open(archive, "wb") as handle:
                for block in resp.iter_content(chunk_size=1024 * 1024):
                    handle.write(block)
        actual = _sha256_file(archive)
        if actual != _MINILM_ARCHIVE_SHA256:
            archive.unlink(missing_ok=True)
            raise EmbeddingUnavailableError(
                f"Embedding model archive checksum mismatch (got {actual[:12]}…); download rejected."
            )
        with tarfile.open(archive, "r:gz") as tar:
            root = target_root.resolve()
            for member in tar.getmembers():
                destination = (target_root / member.name).resolve()
                if not str(destination).startswith(str(root)):
                    raise EmbeddingUnavailableError("Embedding model archive contains an unsafe path.")
            tar.extractall(target_root)
        archive.unlink(missing_ok=True)
        return target_root / "onnx"

    def _ensure_loaded(self) -> None:
        if self._session is not None:
            return
        with self._lock:
            if self._session is not None:
                return
            try:
                import onnxruntime as ort
                from tokenizers import Tokenizer
            except ImportError as exc:
                raise EmbeddingUnavailableError(
                    "onnxruntime and tokenizers are required for the default embedding model."
                ) from exc

            model_dir = self._locate_model_dir()
            if model_dir is None:
                if not settings.EMBEDDING_AUTO_DOWNLOAD:
                    raise EmbeddingUnavailableError(
                        f"Embedding model files not found under {settings.EMBEDDING_MODEL_DIR} "
                        "and EMBEDDING_AUTO_DOWNLOAD is off."
                    )
                try:
                    model_dir = self._download()
                except EmbeddingUnavailableError:
                    raise
                except Exception as exc:
                    raise EmbeddingUnavailableError(
                        f"Could not download the embedding model: {exc}"
                    ) from exc

            try:
                tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
                tokenizer.enable_truncation(max_length=_MINILM_MAX_TOKENS)
                # Pad to the longest text in each batch, not to a fixed 256 tokens.
                tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
                options = ort.SessionOptions()
                options.intra_op_num_threads = max(1, min(8, os.cpu_count() or 1))
                session = ort.InferenceSession(
                    str(model_dir / "model.onnx"),
                    sess_options=options,
                    providers=["CPUExecutionProvider"],
                )
            except Exception as exc:
                raise EmbeddingUnavailableError(f"Could not load the embedding model: {exc}") from exc

            self._input_names = [i.name for i in session.get_inputs()]
            self._tokenizer = tokenizer
            self._session = session
            logger.info("Embedding model %s loaded from %s", self.id, model_dir)

    # -- inference ---------------------------------------------------------

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []
        self._ensure_loaded()
        cleaned = [str(t) if t is not None and str(t).strip() else " " for t in texts]
        # Batch similar lengths together so short texts are not padded to long ones.
        order = sorted(range(len(cleaned)), key=lambda i: len(cleaned[i]))
        batch_size = max(1, int(settings.EMBEDDING_BATCH_SIZE))
        out = np.zeros((len(cleaned), self.dim), dtype=np.float32)
        for start in range(0, len(order), batch_size):
            idxs = order[start : start + batch_size]
            batch = [cleaned[i] for i in idxs]
            with self._lock:
                encoded = self._tokenizer.encode_batch(batch)
                input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
                attention = np.array([e.attention_mask for e in encoded], dtype=np.int64)
                feeds = {"input_ids": input_ids, "attention_mask": attention}
                if "token_type_ids" in self._input_names:
                    feeds["token_type_ids"] = np.zeros_like(input_ids)
                hidden = self._session.run(None, feeds)[0]
            mask = attention[..., None].astype(np.float32)
            pooled = (hidden * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
            norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            norms[norms == 0] = 1e-12
            out[idxs] = (pooled / norms).astype(np.float32)
        return out.tolist()


# ---------------------------------------------------------------------------
# sentence-transformers (opt-in)
# ---------------------------------------------------------------------------


class SentenceTransformerModel(EmbeddingModel):
    provider = "sentence-transformers"
    semantic = True

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        slug = re.sub(r"[^A-Za-z0-9]+", "-", model_name.split("/")[-1]).strip("-")
        self.id = f"st-{slug}"[:48]
        self.revision = "local"
        self._model = None
        self._lock = threading.Lock()

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name)
                self.dim = int(self._model.get_sentence_embedding_dimension())
            except Exception as exc:
                raise EmbeddingUnavailableError(
                    f"Could not load sentence-transformers model {self.model_name}: {exc}"
                ) from exc

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []
        self._ensure_loaded()
        vectors = self._model.encode(
            [str(t or " ") for t in texts],
            convert_to_numpy=True,
            normalize_embeddings=True,
            batch_size=max(1, int(settings.EMBEDDING_BATCH_SIZE)),
        )
        return vectors.astype(np.float32).tolist()

    def info(self) -> Dict[str, Any]:
        if not self.dim:
            self._ensure_loaded()
        return super().info()


# ---------------------------------------------------------------------------
# Stable lexical hashing (explicit opt-in only)
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class StableHashModel(EmbeddingModel):
    """Signed feature hashing over word tokens.

    Deterministic across processes and machines (blake2b, not Python ``hash``).
    It captures word overlap only, so it is reported as ``semantic: false``.
    """

    id = "lexical-hash-v2"
    provider = "hash"
    model_name = "blake2b-feature-hash"
    revision = "2"
    dim = 256
    semantic = False

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        vectors: List[List[float]] = []
        for text in texts:
            vec = np.zeros(self.dim, dtype=np.float32)
            for token in _TOKEN_RE.findall(str(text or "").lower()):
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                value = int.from_bytes(digest, "big")
                vec[value % self.dim] += 1.0 if (value >> 63) & 1 else -1.0
            norm = float(np.linalg.norm(vec))
            if norm > 0:
                vec /= norm
            vectors.append(vec.tolist())
        return vectors


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

LEGACY_COLLECTION = "documents"

_model_lock = threading.Lock()
_active_model: Optional[EmbeddingModel] = None


def collection_name_for(model_id: str) -> str:
    """Chroma collection that holds vectors produced by ``model_id``."""
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", model_id).strip("-_")
    return f"kf_{slug}"[:63].rstrip("-_")


def get_embedding_model() -> EmbeddingModel:
    """Return the configured embedding model (constructed once per process)."""
    global _active_model
    if _active_model is not None:
        return _active_model
    with _model_lock:
        if _active_model is not None:
            return _active_model
        provider = (settings.EMBEDDING_PROVIDER or "onnx-minilm").strip().lower()
        if provider in ("onnx-minilm", "onnx", "minilm", "default"):
            _active_model = OnnxMiniLMModel()
        elif provider in ("sentence-transformers", "sentence_transformers", "st"):
            _active_model = SentenceTransformerModel(settings.MODEL_NAME)
        elif provider == "hash":
            _active_model = StableHashModel()
        else:
            raise EmbeddingUnavailableError(f"Unknown EMBEDDING_PROVIDER: {provider}")
        return _active_model


def reset_embedding_model() -> None:
    """Drop the cached model (tests switch providers through settings)."""
    global _active_model
    with _model_lock:
        _active_model = None
