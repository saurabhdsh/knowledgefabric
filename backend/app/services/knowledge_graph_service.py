import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Set


class KnowledgeGraphService:
    """Builds a lightweight entity-relationship graph from fabric chunks."""

    def __init__(self) -> None:
        self.stopwords = {
            "the", "and", "for", "with", "that", "this", "from", "have", "were", "been",
            "into", "your", "their", "about", "also", "than", "there", "which", "when",
            "what", "will", "would", "could", "should", "such", "using", "used", "use",
            "over", "under", "between", "across", "within", "without", "very", "more",
            "most", "some", "many", "other", "same", "only", "each", "both", "through",
            "while", "where", "whose", "them", "they", "these", "those", "then", "into",
            "are", "is", "was", "be", "to", "of", "in", "on", "by", "or", "as", "at",
            "an", "a", "it", "if", "we", "you", "our", "can", "may", "not",
            "file", "files", "document", "documents", "data", "row", "rows",
            "source", "type", "name", "value", "table", "database", "servicenow",
            "created", "updated", "status", "model", "chunk", "chunks", "total",
        }
        self.noise_tokens = {"knowledge", "fabric", "knowledge_fabric", "knowledge-fabric", "pdf", "txt", "csv", "xlsx"}
        self.entity_aliases = {
            "patients": "patient",
            "studies": "study",
            "analyses": "analysis",
            "events": "event",
            "days": "day",
            "ions": "ion",
            "igator": "investigator",
            "invest igator": "investigator",
            "invest": "investigator",
            "treatm": "treatment",
            "treatm ent": "treatment",
            "lesio": "lesion",
            "pat": "patient",
            "pati": "patient",
        }
        self.weak_terms = {
            "after", "during", "before", "time", "date", "day", "first", "least",
            "must", "based", "all", "any", "who", "has", "related", "page",
        }
        self.generic_domain_terms = {
            "study", "clinical", "protocol", "analysis", "trial", "primary",
            "response", "baseline", "follow", "criteria", "performed",
        }
        self.domain_priority_terms = {
            "cancer", "breast cancer", "disease", "drug", "therapy", "treatment",
            "adverse", "event", "survival", "progression", "investigator",
            "dose", "pfs", "fulvestrant", "lilly",
        }
        self.ocr_noise_patterns = [
            re.compile(r"^[a-z]{1,2}$"),
            re.compile(r"^[a-z]*\d+[a-z]*$"),
            re.compile(r".*(?:ive|ent|com|pat|lesio|treatm)$"),
        ]

    def _is_ocr_noise(self, token: str) -> bool:
        if len(token) <= 2:
            return True
        if len(token) == 3 and token not in {"pfs", "api"}:
            return True
        return any(pattern.match(token) for pattern in self.ocr_noise_patterns)

    def _normalize_token(self, token: str) -> str:
        normalized = token.lower().replace("_", " ").replace("-", " ").strip()
        normalized = re.sub(r"\s+", " ", normalized)
        if normalized in self.entity_aliases:
            normalized = self.entity_aliases[normalized]
        return normalized

    def _extract_entities(self, text: str, exclude_terms: Set[str]) -> List[str]:
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text)
        cleaned: List[str] = []
        for token in tokens:
            normalized = self._normalize_token(token)
            for part in normalized.split():
                if part in self.stopwords or part in self.noise_tokens or part in exclude_terms:
                    continue
                if part in self.weak_terms:
                    continue
                if part.isdigit() or len(part) < 3:
                    continue
                if self._is_ocr_noise(part):
                    continue
                cleaned.append(part)

        # Add simple noun-like bigrams for more meaningful entities.
        bigrams: List[str] = []
        for i in range(len(cleaned) - 1):
            first = cleaned[i]
            second = cleaned[i + 1]
            if first == second:
                continue
            bigram = f"{first} {second}"
            if bigram not in exclude_terms and first not in self.weak_terms and second not in self.weak_terms:
                bigrams.append(bigram)

        return cleaned + bigrams

    def build_graph(self, fabric_id: str, fabric_name: str, documents: List[str]) -> Dict[str, Any]:
        exclude_terms: Set[str] = set()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", fabric_name.lower()):
            exclude_terms.add(self._normalize_token(token))

        entity_counts: Counter[str] = Counter()
        pair_counts: defaultdict[tuple[str, str], int] = defaultdict(int)
        doc_frequency: Counter[str] = Counter()

        # Build entities + pair co-occurrence from sentence windows.
        for content in documents:
            seen_in_doc: Set[str] = set()
            chunks = re.split(r"[.!?\n]+", content)
            for sentence in chunks:
                entities = list(dict.fromkeys(self._extract_entities(sentence, exclude_terms)))
                if len(entities) < 1:
                    continue

                for entity in entities:
                    entity_counts[entity] += 1

                # Co-occurrence relation inside the same sentence.
                max_entities = min(len(entities), 10)
                for i in range(max_entities):
                    for j in range(i + 1, max_entities):
                        a, b = sorted((entities[i], entities[j]))
                        pair_counts[(a, b)] += 1
                seen_in_doc.update(entities)
            for ent in seen_in_doc:
                doc_frequency[ent] += 1

        # Weighted score: frequent + appears across chunks.
        scored_entities: List[tuple[str, float]] = []
        for entity, count in entity_counts.items():
            freq = doc_frequency.get(entity, 1)
            score = (count * 0.75) + (freq * 1.5)
            if entity in self.generic_domain_terms:
                score *= 0.58
            if entity in self.domain_priority_terms:
                score *= 1.45
            if " " in entity and entity not in self.generic_domain_terms:
                score *= 1.15
            if entity in self.weak_terms:
                continue
            if count >= 3 and freq >= 2:
                scored_entities.append((entity, score))

        scored_entities.sort(key=lambda item: item[1], reverse=True)
        all_entities_ranked = [name for name, _ in scored_entities]
        # Keep rendered graph compact, but preserve total metrics separately.
        top_entities = all_entities_ranked[:32]
        top_set = set(top_entities)
        all_set = set(all_entities_ranked)

        nodes: List[Dict[str, Any]] = [
            {"id": f"fabric:{fabric_id}", "label": fabric_name, "type": "fabric", "weight": 1}
        ]
        for entity in top_entities:
            nodes.append(
                {
                    "id": f"entity:{entity}",
                    "label": entity,
                    "type": "entity",
                    "weight": int(entity_counts[entity]),
                }
            )

        links: List[Dict[str, Any]] = []
        for entity in top_entities:
            links.append(
                {
                    "source": f"fabric:{fabric_id}",
                    "target": f"entity:{entity}",
                    "relation": "mentions",
                    "weight": int(entity_counts[entity]),
                }
            )

        related_edges: List[Dict[str, Any]] = []
        total_related_edges = 0
        for (a, b), weight in pair_counts.items():
            if weight < 4:
                continue
            if a in all_set and b in all_set:
                total_related_edges += 1
            if a in top_set and b in top_set:
                related_edges.append(
                    {
                        "source": f"entity:{a}",
                        "target": f"entity:{b}",
                        "relation": "related_to",
                        "weight": int(weight),
                    }
                )

        # Keep strongest relationships only to avoid hairball graph.
        related_edges.sort(key=lambda edge: edge["weight"], reverse=True)
        max_related_edges = min(140, max(40, len(top_entities) * 4))
        links.extend(related_edges[:max_related_edges])

        total_node_count = len(all_entities_ranked) + 1  # + fabric node
        total_edge_count = len(all_entities_ranked) + total_related_edges

        return {
            "fabric_id": fabric_id,
            "fabric_name": fabric_name,
            "node_count": total_node_count,
            "edge_count": total_edge_count,
            "rendered_node_count": len(nodes),
            "rendered_edge_count": len(links),
            "nodes": nodes,
            "edges": links,
        }


knowledge_graph_service = KnowledgeGraphService()
