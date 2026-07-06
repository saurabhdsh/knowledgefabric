"""Load source artifacts (PDF/DOCX/XML) from ontology-only upload directory. Not shared with Knowledge Fabric."""
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.models.ontology import SourceArtifact


class ArtifactLoader:
    """Loads files from the ontology upload directory only. Never reads from main app UPLOAD_DIR."""

    ALLOWED_EXTENSIONS = (".pdf", ".xml", ".docx", ".png", ".jpg", ".jpeg", ".gif", ".webp")

    def __init__(self):
        ontology_dir = getattr(settings, "ONTOLOGY_UPLOAD_DIR", None) or os.path.join(settings.ONTOLOGY_DATA_DIR, "uploads")
        self.upload_dir = os.path.abspath(ontology_dir)
        self._main_upload_dir = os.path.abspath(settings.UPLOAD_DIR)
        os.makedirs(self.upload_dir, exist_ok=True)

    def get_available_files(self) -> List[Dict[str, Any]]:
        """List files in ontology upload directory only. Never returns files from Knowledge Fabric uploads."""
        files: List[Dict[str, Any]] = []
        if not os.path.isdir(self.upload_dir):
            return files
        try:
            if os.path.samefile(self.upload_dir, self._main_upload_dir):
                return files
        except OSError:
            pass
        for filename in os.listdir(self.upload_dir):
            if not filename.startswith("."):
                ext = os.path.splitext(filename)[1].lower()
                if ext in self.ALLOWED_EXTENSIONS:
                    file_path = os.path.join(self.upload_dir, filename)
                    if os.path.isfile(file_path):
                        try:
                            stat = os.stat(file_path)
                            files.append({
                                "name": filename,
                                "path": file_path,
                                "size": stat.st_size,
                                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                            })
                        except OSError:
                            pass
        return files

    def resolve_artifact_ids_to_paths(
        self, artifact_ids: List[str], project_id: str
    ) -> List[SourceArtifact]:
        """
        Resolve artifact IDs (file names or paths) to full paths and create SourceArtifact.
        """
        available = {os.path.basename(f["path"]): f for f in self.get_available_files()}
        for f in self.get_available_files():
            available[f["path"]] = f
            available[f["name"]] = f

        search_roots = [
            self.upload_dir,
            os.path.abspath(settings.UPLOAD_DIR),
        ]

        artifacts: List[SourceArtifact] = []
        for aid in artifact_ids:
            if os.path.isfile(aid):
                art = self._path_to_artifact(aid, project_id)
                if art:
                    artifacts.append(art)
                continue
            if aid in available:
                info = available[aid]
                art = self._path_to_artifact(info["path"], project_id, info.get("name", aid))
                if art:
                    artifacts.append(art)
                continue
            resolved = False
            for root in search_roots:
                candidate = os.path.join(root, aid)
                if os.path.isfile(candidate):
                    art = self._path_to_artifact(candidate, project_id, aid)
                    if art:
                        artifacts.append(art)
                    resolved = True
                    break
            if resolved:
                continue
            candidate = os.path.join(self.upload_dir, aid)
            if os.path.isfile(candidate):
                art = self._path_to_artifact(candidate, project_id, aid)
                if art:
                    artifacts.append(art)
        return artifacts

    def _path_to_artifact(
        self, file_path: str, project_id: str, file_name: Optional[str] = None
    ) -> Optional[SourceArtifact]:
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            return None
        name = file_name or os.path.basename(file_path)
        if ext == ".pdf":
            source_type = "pdf"
        elif ext == ".docx":
            source_type = "docx"
        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            source_type = "image"
        else:
            source_type = "xml"
        return SourceArtifact(
            id=f"art_{uuid.uuid4().hex[:12]}",
            file_name=name,
            file_path=os.path.abspath(file_path),
            source_type=source_type,
            project_id=project_id,
            ingestion_time=datetime.utcnow(),
            metadata={"path": file_path},
        )
