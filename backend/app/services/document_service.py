import PyPDF2
import os
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import aiofiles
from fastapi import UploadFile
from app.core.config import settings

class DocumentService:
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR
        os.makedirs(self.upload_dir, exist_ok=True)
    
    async def save_uploaded_file(self, file: UploadFile) -> str:
        """Save uploaded file and return the file path"""
        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4().hex}{file_extension}"
        file_path = os.path.join(self.upload_dir, unique_filename)
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        return file_path
    
    def extract_text_from_pdf(self, file_path: str) -> List[Dict[str, Any]]:
        """Extract text from PDF file with page information"""
        documents = []
        
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    text = page.extract_text()
                    
                    if text.strip():  # Only add non-empty pages
                        documents.append({
                            "content": text.strip(),
                            "page_number": page_num,
                            "file_name": os.path.basename(file_path),
                            "source_name": os.path.splitext(os.path.basename(file_path))[0],
                            "created_at": datetime.now().isoformat(),
                            "metadata": {
                                "total_pages": len(pdf_reader.pages),
                                "file_size": os.path.getsize(file_path),
                                "file_type": "pdf"
                            }
                        })
        
        except Exception as e:
            print(f"Error extracting text from PDF {file_path}: {e}")
            raise Exception(f"Failed to extract text from PDF: {str(e)}")
        
        return documents
    
    def extract_text_from_txt(self, file_path: str) -> List[Dict[str, Any]]:
        """Extract text from TXT file"""
        documents = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                
                # Split content into chunks (you can customize this)
                chunks = self._split_text_into_chunks(content, chunk_size=1000)
                
                for i, chunk in enumerate(chunks):
                    if chunk.strip():
                        documents.append({
                            "content": chunk.strip(),
                            "page_number": i + 1,
                            "file_name": os.path.basename(file_path),
                            "source_name": os.path.splitext(os.path.basename(file_path))[0],
                            "created_at": datetime.now().isoformat(),
                            "metadata": {
                                "chunk_number": i + 1,
                                "total_chunks": len(chunks),
                                "file_size": os.path.getsize(file_path),
                                "file_type": "txt"
                            }
                        })
        
        except Exception as e:
            print(f"Error extracting text from TXT {file_path}: {e}")
            raise Exception(f"Failed to extract text from TXT: {str(e)}")
        
        return documents
    
    def _split_text_into_chunks(self, text: str, chunk_size: int = 1000) -> List[str]:
        """Split text into chunks of specified size"""
        words = text.split()
        chunks = []
        current_chunk = []
        current_size = 0
        
        for word in words:
            word_size = len(word) + 1  # +1 for space
            if current_size + word_size > chunk_size and current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_size = word_size
            else:
                current_chunk.append(word)
                current_size += word_size
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def validate_file(self, file: UploadFile) -> bool:
        """Validate uploaded file"""
        # Check file extension
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in settings.ALLOWED_EXTENSIONS:
            return False
        
        # Check file size (basic validation)
        # Note: For production, you should check file size before saving
        return True
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get information about a file"""
        if not os.path.exists(file_path):
            return {}
        
        stat = os.stat(file_path)
        return {
            "file_name": os.path.basename(file_path),
            "file_size": stat.st_size,
            "file_type": os.path.splitext(file_path)[1],
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
        }
    
    def delete_file(self, file_path: str) -> bool:
        """Delete a file"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")
            return False
    
    def process_database_data(self, data: List[Dict[str, Any]], source_name: str) -> List[Dict[str, Any]]:
        """Process data from database connection"""
        row_documents = self._build_row_documents(data, source_name)
        linked_documents = self._build_linked_row_documents(data, source_name)
        if linked_documents:
            # Keep both granular row chunks (for deterministic counts) and linked chunks (for relational reasoning).
            return row_documents + linked_documents
        return row_documents

    def _build_row_documents(self, data: List[Dict[str, Any]], source_name: str) -> List[Dict[str, Any]]:
        """Build one chunk per row for deterministic aggregations."""
        documents = []
        for i, row in enumerate(data):
            content = self._row_to_text(row)
            column_keys = [str(k) for k in row.keys()] if row else []
            duplicate_match_type = self._first_present(row, ("duplicate_match_type", "match_type", "label"))
            prior_match = self._first_present(row, ("prior_matching_claim_id", "prior_id", "parent_id", "original_id"))
            claim_id = self._first_present(row, ("claim_id", "id", "record_id"))
            documents.append({
                "content": content,
                "page_number": i + 1,
                "file_name": f"{source_name}_db",
                "source_name": source_name,
                "created_at": datetime.now().isoformat(),
                "metadata": {
                    "row_number": i + 1,
                    "total_rows": len(data),
                    "source_type": "database",
                    "chunk_type": "row",
                    "columns": ",".join(column_keys),
                    "duplicate_match_type": duplicate_match_type,
                    "prior_matching_claim_id": prior_match,
                    "claim_id": claim_id,
                }
            })
        return documents

    def _build_linked_row_documents(self, data: List[Dict[str, Any]], source_name: str) -> List[Dict[str, Any]]:
        """
        Build deterministic relational chunks for any tabular dataset.
        Strategy:
        - infer a primary id column
        - detect reference/link columns that point to primary ids
        - emit pair chunks that contain both linked rows
        """
        if not data:
            return []

        columns = [str(k).strip() for k in (data[0] or {}).keys()]
        primary_id_col = self._infer_primary_id_column(data, columns)
        if not primary_id_col:
            return []

        id_to_row: Dict[str, Dict[str, Any]] = {}
        for row in data:
            row_id = self._string_value(row.get(primary_id_col))
            if row_id:
                id_to_row[row_id] = row

        link_cols = self._infer_link_columns(data, columns, primary_id_col, id_to_row)
        if not link_cols:
            return []

        rows_with_idx: List[Tuple[int, Dict[str, Any]]] = list(enumerate(data))
        documents: List[Dict[str, Any]] = []
        seen_pairs = set()

        for row_idx, row in rows_with_idx:
            row_id = self._string_value(row.get(primary_id_col))
            if not row_id:
                continue
            for link_col in link_cols:
                target_id = self._string_value(row.get(link_col))
                if not target_id:
                    continue
                pair_key = (link_col, row_id, target_id)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                target_row = id_to_row.get(target_id)
                header = [
                    "Linked Row Pair",
                    f"primary_id_column: {primary_id_col}",
                    f"source_row_id: {row_id}",
                    f"link_column: {link_col}",
                    f"target_row_id: {target_id}",
                ]
                source_text = self._row_to_text(row)
                target_text = self._row_to_text(target_row) if target_row else f"{primary_id_col}: {target_id} | target row not found in dataset"
                content = "\n".join(
                    header + [
                        "",
                        f"Source Row: {source_text}",
                        f"Target Row: {target_text}",
                    ]
                )

                documents.append({
                    "content": content,
                    "page_number": len(documents) + 1,
                    "file_name": f"{source_name}_db",
                    "source_name": source_name,
                    "created_at": datetime.now().isoformat(),
                    "metadata": {
                        "source_type": "database",
                        "chunk_type": "linked_pair",
                        "row_number": row_idx + 1,
                        "primary_id_column": primary_id_col,
                        "source_row_id": row_id,
                        "target_row_id": target_id,
                        "link_column": link_col,
                        "pair_found_target": bool(target_row),
                    }
                })

        return documents

    def _infer_primary_id_column(self, data: List[Dict[str, Any]], columns: List[str]) -> Optional[str]:
        """Infer the main row id column with deterministic heuristics."""
        if not columns:
            return None

        preferred = ["id", "claim_id", "record_id", "row_id"]
        lowered = {c.lower(): c for c in columns}
        for pref in preferred:
            if pref in lowered:
                return lowered[pref]

        candidates = [c for c in columns if c.lower() == "id" or c.lower().endswith("_id")]
        if not candidates:
            return None

        best_col = None
        best_score = -1.0
        row_count = max(len(data), 1)
        for col in candidates:
            non_empty = [self._string_value(r.get(col)) for r in data]
            non_empty = [v for v in non_empty if v]
            if not non_empty:
                continue
            unique_ratio = len(set(non_empty)) / float(len(non_empty))
            coverage = len(non_empty) / float(row_count)
            score = (unique_ratio * 0.8) + (coverage * 0.2)
            if score > best_score:
                best_score = score
                best_col = col

        return best_col

    def _infer_link_columns(
        self,
        data: List[Dict[str, Any]],
        columns: List[str],
        primary_id_col: str,
        id_to_row: Dict[str, Dict[str, Any]],
    ) -> List[str]:
        """Infer columns that reference another row id in the same dataset."""
        link_keywords = ("parent", "prior", "prev", "original", "source", "reference", "ref", "match", "related")
        results: List[str] = []
        total_rows = max(len(data), 1)
        id_set = set(id_to_row.keys())

        for col in columns:
            if col == primary_id_col:
                continue
            col_l = col.lower()
            name_looks_like_link = (
                col_l.endswith("_id")
                or col_l.endswith("id")
                or "_id_" in col_l
                or any(k in col_l for k in link_keywords)
            )
            if not name_looks_like_link:
                continue

            values = [self._string_value(r.get(col)) for r in data]
            non_empty = [v for v in values if v]
            if not non_empty:
                continue

            matched = sum(1 for v in non_empty if v in id_set)
            match_ratio = matched / float(len(non_empty))
            coverage = len(non_empty) / float(total_rows)
            # Require enough signal to avoid noisy, accidental linking.
            if matched >= 3 and match_ratio >= 0.3 and coverage >= 0.02:
                results.append(col)

        return results

    def _first_present(self, row: Dict[str, Any], candidate_keys: Tuple[str, ...]) -> str:
        """Return the first non-empty value among case-insensitive candidate keys."""
        if not row:
            return ""
        normalized = {str(k).strip().lower(): k for k in row.keys()}
        for key in candidate_keys:
            actual = normalized.get(str(key).strip().lower())
            if not actual:
                continue
            value = self._string_value(row.get(actual))
            if value:
                return value
        return ""

    def _string_value(self, value: Any) -> str:
        """Normalize nullable values into trimmed strings."""
        if value is None:
            return ""
        text = str(value).strip()
        if text.lower() in ("none", "nan", "null"):
            return ""
        return text
    
    def _row_to_text(self, row: Dict[str, Any]) -> str:
        """Convert database row to text representation"""
        if not row:
            return ""
        
        text_parts = []
        for key, value in row.items():
            if value is not None:
                text_parts.append(f"{key}: {value}")
        
        return " | ".join(text_parts)

    def extract_text_from_pdf_simple(self, file_path: str) -> str:
        """Extract text from a PDF file (simple version)"""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return ""

    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Split text into overlapping chunks"""
        if not text:
            return []
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # If this is not the first chunk, include some overlap
            if start > 0:
                start = start - overlap
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end
        
        return chunks

    def get_uploaded_files(self) -> List[Dict[str, Any]]:
        """Get list of uploaded files"""
        try:
            files = []
            upload_dir = settings.UPLOAD_DIR
            
            if os.path.exists(upload_dir):
                for filename in os.listdir(upload_dir):
                    file_path = os.path.join(upload_dir, filename)
                    if os.path.isfile(file_path):
                        file_stat = os.stat(file_path)
                        files.append({
                            "name": filename,
                            "path": file_path,
                            "size": file_stat.st_size,
                            "created_at": datetime.fromtimestamp(file_stat.st_ctime).isoformat()
                        })
            
            return files
        except Exception as e:
            print(f"Error getting uploaded files: {e}")
            return []

# Global instance
document_service = DocumentService() 