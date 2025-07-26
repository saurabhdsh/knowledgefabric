import PyPDF2
import os
import uuid
from typing import List, Dict, Any, Optional
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
        documents = []
        
        for i, row in enumerate(data):
            # Convert row to text representation
            content = self._row_to_text(row)
            
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
                    "columns": list(row.keys()) if row else []
                }
            })
        
        return documents
    
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