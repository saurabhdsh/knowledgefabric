"""Extract text from images (PNG, JPG, etc.) via OCR for ontology discovery."""
from typing import Any, Dict, List, Tuple

from app.models.ontology import OntologyEvidence, SourceArtifact


class ImageProcessor:
    """Extract text from images using OCR (pytesseract). Falls back to placeholder if OCR unavailable."""

    def process(self, artifact: SourceArtifact) -> Tuple[str, List[Dict[str, Any]], List[OntologyEvidence]]:
        """
        Process an image artifact. Returns:
        - full_text: OCR text or placeholder
        - sections: list of {heading, content, page_number} (page_number 1 for single image)
        - evidence_list
        """
        full_text_parts: List[str] = []
        sections: List[Dict[str, Any]] = []
        evidence_list: List[OntologyEvidence] = []

        try:
            try:
                from PIL import Image
            except ImportError:
                full_text_parts.append(f"[Image: {artifact.file_name} — Pillow not installed; add Pillow to process images]")
                sections.append({
                    "heading": "Image",
                    "content": full_text_parts[0],
                    "page_number": 1,
                })
                evidence_list.append(
                    OntologyEvidence(
                        id=f"evt_{artifact.id}_img_0",
                        artifact_id=artifact.id,
                        artifact_type="image",
                        page_number=1,
                        text_snippet=full_text_parts[0][:500],
                        extraction_stage="image_processor",
                    )
                )
                full_text = "\n\n".join(full_text_parts)
                return full_text, sections, evidence_list

            img = Image.open(artifact.file_path)
            # Convert to RGB if necessary (e.g. RGBA, P mode)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            try:
                import pytesseract
                text = (pytesseract.image_to_string(img) or "").strip()
            except Exception:
                text = ""

            if text:
                full_text_parts.append(text)
                sections.append({
                    "heading": "Image content",
                    "content": text,
                    "page_number": 1,
                })
                evidence_list.append(
                    OntologyEvidence(
                        id=f"evt_{artifact.id}_img_0",
                        artifact_id=artifact.id,
                        artifact_type="image",
                        page_number=1,
                        text_snippet=text[:500],
                        extraction_stage="image_processor",
                    )
                )
            else:
                placeholder = f"[Image: {artifact.file_name} — no text detected by OCR]"
                full_text_parts.append(placeholder)
                sections.append({"heading": "Image", "content": placeholder, "page_number": 1})
                evidence_list.append(
                    OntologyEvidence(
                        id=f"evt_{artifact.id}_img_0",
                        artifact_id=artifact.id,
                        artifact_type="image",
                        page_number=1,
                        text_snippet=placeholder[:500],
                        extraction_stage="image_processor",
                    )
                )
        except Exception as e:
            full_text_parts.append(f"[Image: {artifact.file_name} — error: {e}]")
            sections.append({
                "heading": "Image",
                "content": full_text_parts[-1],
                "page_number": 1,
            })
            evidence_list.append(
                OntologyEvidence(
                    id=f"evt_{artifact.id}_img_0",
                    artifact_id=artifact.id,
                    artifact_type="image",
                    page_number=1,
                    text_snippet=str(e)[:500],
                    extraction_stage="image_processor",
                )
            )

        full_text = "\n\n".join(full_text_parts)
        return full_text, sections, evidence_list
