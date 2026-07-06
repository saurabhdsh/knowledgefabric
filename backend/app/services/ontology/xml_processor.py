"""XML parsing and tag hierarchy extraction for ontology candidates."""
import xml.etree.ElementTree as ET
import re
from typing import Any, Dict, List, Optional, Tuple

from app.models.ontology import OntologyEvidence, SourceArtifact


class XMLProcessor:
    """Parse XML and extract tag hierarchy (parent = entity candidate, leaf = attribute candidate)."""

    def process(
        self, artifact: SourceArtifact
    ) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]], List[OntologyEvidence]]:
        """
        Process XML file. Returns:
        - full_text (flattened text for LLM)
        - node_hierarchy: list of {path, tag, parent_path, depth, is_leaf, text_sample}
        - repeated_groups: list of paths that repeat (nested entity candidates)
        - evidence_list
        """
        full_text_parts: List[str] = []
        node_hierarchy: List[Dict[str, Any]] = []
        repeated_groups: List[str] = []
        evidence_list: List[OntologyEvidence] = []

        try:
            tree = ET.parse(artifact.file_path)
            root = tree.getroot()
            self._walk(
                root, "", 0, full_text_parts, node_hierarchy, artifact.id, evidence_list
            )
            repeated_groups = self._find_repeated_groups(node_hierarchy)
        except ET.ParseError as e:
            full_text_parts.append(f"[XML parse error: {e}]")
        except Exception as e:
            full_text_parts.append(f"[Error: {e}]")

        full_text = "\n".join(full_text_parts)
        return full_text, node_hierarchy, repeated_groups, evidence_list

    def _walk(
        self,
        elem: ET.Element,
        parent_path: str,
        depth: int,
        text_parts: List[str],
        hierarchy: List[Dict[str, Any]],
        artifact_id: str,
        evidence: List[OntologyEvidence],
    ) -> None:
        tag = self._normalize_tag(elem.tag)
        path = f"{parent_path}/{tag}" if parent_path else tag
        text = (elem.text or "").strip()
        tail = (elem.tail or "").strip()
        children = list(elem)
        is_leaf = len(children) == 0

        if text:
            text_parts.append(text)
        sample = (text or "")[:300]
        if not sample and children:
            sample = f"<{tag}> ({len(children)} children)"

        hierarchy.append({
            "path": path,
            "tag": tag,
            "parent_path": parent_path,
            "depth": depth,
            "is_leaf": is_leaf,
            "text_sample": sample,
            "child_count": len(children),
        })

        evidence.append(
            OntologyEvidence(
                id=f"evt_{artifact_id}_{path.replace('/', '_')}_{len(evidence)}",
                artifact_id=artifact_id,
                artifact_type="xml",
                xml_path=path,
                text_snippet=sample or path,
                extraction_stage="xml_processor",
            )
        )

        for child in children:
            self._walk(
                child, path, depth + 1, text_parts, hierarchy, artifact_id, evidence
            )
        if tail:
            text_parts.append(tail)

    def _normalize_tag(self, tag: str) -> str:
        """Strip namespace if present."""
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    def _find_repeated_groups(self, hierarchy: List[Dict[str, Any]]) -> List[str]:
        """Find parent paths whose same-named children repeat (suggest nested entity)."""
        parent_counts: Dict[str, Dict[str, int]] = {}
        for node in hierarchy:
            parent = node["parent_path"]
            tag = node["tag"]
            if parent not in parent_counts:
                parent_counts[parent] = {}
            parent_counts[parent][tag] = parent_counts[parent].get(tag, 0) + 1

        repeated: List[str] = []
        for parent, counts in parent_counts.items():
            for tag, count in counts.items():
                if count > 1:
                    repeated.append(f"{parent}/{tag}")
        return list(set(repeated))
