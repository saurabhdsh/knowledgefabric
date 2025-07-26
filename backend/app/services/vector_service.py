import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict, Any, Optional
import uuid
import json
import os
from datetime import datetime
from app.core.config import settings

class VectorService:
    def __init__(self):
        try:
            self.client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_DIRECTORY,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
        except Exception as e:
            print(f"Warning: ChromaDB initialization error: {e}")
            # Create a fallback client
            self.client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_DIRECTORY,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
        
        # Initialize the embedding model
        try:
            self.model = SentenceTransformer(settings.MODEL_NAME)
        except Exception as e:
            print(f"Warning: Model initialization error: {e}")
            # Use a fallback model
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Get or create collections
        try:
            self.documents_collection = self.client.get_or_create_collection(
                name="documents",
                metadata={"hnsw:space": "cosine"}
            )
            
            self.sources_collection = self.client.get_or_create_collection(
                name="sources",
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            print(f"Warning: Collection creation error: {e}")
            # Try to get existing collections
            try:
                self.documents_collection = self.client.get_collection("documents")
                self.sources_collection = self.client.get_collection("sources")
            except Exception as e2:
                print(f"Error getting collections: {e2}")
                # Create minimal collections
                self.documents_collection = self.client.create_collection("documents")
                self.sources_collection = self.client.create_collection("sources")
    
    def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Create embeddings for a list of texts"""
        embeddings = self.model.encode(texts, convert_to_tensor=False)
        return embeddings.tolist()
    
    def add_documents(self, documents: List[Dict[str, Any]], source_id: str) -> List[str]:
        """Add documents to the vector database"""
        if not documents:
            return []
        
        # Extract texts and metadata
        texts = [doc["content"] for doc in documents]
        metadatas = []
        ids = []
        
        for i, doc in enumerate(documents):
            metadata = {
                "source_id": source_id,
                "source_name": doc.get("source_name", "Unknown"),
                "page_number": doc.get("page_number"),
                "file_name": doc.get("file_name"),
                "created_at": doc.get("created_at"),
                **doc.get("metadata", {})
            }
            metadatas.append(metadata)
            ids.append(f"{source_id}_{i}_{uuid.uuid4().hex[:8]}")
        
        # Create embeddings
        embeddings = self.create_embeddings(texts)
        
        # Add to collection
        self.documents_collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        
        return ids
    
    def search_documents(self, query: str, limit: int = 5, threshold: float = 0.7, 
                        filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search for similar documents"""
        # Create query embedding
        query_embedding = self.create_embeddings([query])[0]
        
        # Prepare where clause for filters
        where_clause = None
        if filters:
            where_clause = {}
            for key, value in filters.items():
                where_clause[f"metadata.{key}"] = value
        
        # Search in collection
        results = self.documents_collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where=where_clause
        )
        
        # Process results
        processed_results = []
        if results["documents"] and results["documents"][0]:
            for i, (doc, metadata, distance) in enumerate(zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            )):
                # Convert distance to similarity score (cosine similarity)
                similarity_score = 1 - distance
                
                if similarity_score >= threshold:
                    processed_results.append({
                        "id": results["ids"][0][i],
                        "content": doc,
                        "source": metadata.get("source_name", "Unknown"),
                        "similarity_score": similarity_score,
                        "metadata": metadata,
                        "page_number": metadata.get("page_number")
                    })
        
        return processed_results
    
    def get_source_statistics(self, source_id: str) -> Dict[str, Any]:
        """Get statistics for a specific source"""
        # Count documents for this source
        count_result = self.documents_collection.count(
            where={"metadata.source_id": source_id}
        )
        
        return {
            "source_id": source_id,
            "document_count": count_result,
            "status": "active" if count_result > 0 else "empty"
        }
    
    def delete_source_documents(self, source_id: str) -> bool:
        """Delete all documents for a specific source"""
        try:
            # Get all documents for this source
            results = self.documents_collection.get(
                where={"metadata.source_id": source_id}
            )
            
            if results["ids"]:
                # Delete documents
                self.documents_collection.delete(
                    ids=results["ids"]
                )
            
            return True
        except Exception as e:
            print(f"Error deleting source documents: {e}")
            return False
    
    def get_all_statistics(self) -> Dict[str, Any]:
        """Get overall statistics"""
        total_documents = self.documents_collection.count()
        
        # Get unique sources
        all_docs = self.documents_collection.get()
        unique_sources = set()
        if all_docs["metadatas"]:
            for metadata in all_docs["metadatas"]:
                if metadata and "source_id" in metadata:
                    unique_sources.add(metadata["source_id"])
        
        return {
            "total_documents": total_documents,
            "total_sources": len(unique_sources),
            "total_embeddings": total_documents,
            "model_name": settings.MODEL_NAME
        }
    
    def update_model(self, new_model_name: str) -> bool:
        """Update the embedding model"""
        try:
            self.model = SentenceTransformer(new_model_name)
            return True
        except Exception as e:
            print(f"Error updating model: {e}")
            return False

    def get_all_sources(self):
        """Get all knowledge sources"""
        try:
            # Get all documents to extract source information
            all_docs = self.documents_collection.get()
            
            # Group by source
            sources = {}
            for i, metadata in enumerate(all_docs["metadatas"]):
                if metadata and "source_id" in metadata:
                    source_id = metadata["source_id"]
                    source_name = metadata.get("source_name", "Unknown")
                    
                    if source_id not in sources:
                        sources[source_id] = {
                            "id": source_id,
                            "name": source_name,
                            "source_type": metadata.get("file_type", "unknown"),
                            "description": metadata.get("description", ""),
                            "tags": metadata.get("tags", []),
                            "created_at": metadata.get("created_at"),
                            "updated_at": metadata.get("created_at"),
                            "document_count": 0,
                            "status": "active",
                            "model_status": "trained",  # Default status
                            "last_training": metadata.get("created_at"),
                            "chunks_count": 0,
                            "embedding_count": 0
                        }
                    
                    sources[source_id]["document_count"] += 1
                    sources[source_id]["chunks_count"] += 1
                    sources[source_id]["embedding_count"] += 1
            
            # Convert to list and add real statistics
            source_list = list(sources.values())
            
            # Add real statistics for each source
            for source in source_list:
                # Get actual document count for this source
                source_docs = self.documents_collection.get(
                    where={"metadata.source_id": source["id"]}
                )
                source["document_count"] = len(source_docs["documents"]) if source_docs["documents"] else 0
                source["chunks_count"] = source["document_count"]
                source["embedding_count"] = source["document_count"]
                
                # Add real training status (for now, assume trained if documents exist)
                if source["document_count"] > 0:
                    source["model_status"] = "trained"
                else:
                    source["model_status"] = "not_trained"
            
            return source_list
        except Exception as e:
            print(f"Error getting all sources: {e}")
            return []

    def get_source(self, source_id: str):
        """Get a specific knowledge source"""
        try:
            sources = self.get_all_sources()
            for source in sources:
                if source["id"] == source_id:
                    return source
            return None
        except Exception as e:
            print(f"Error getting source {source_id}: {e}")
            return None

    def delete_source(self, source_id: str) -> bool:
        """Delete a knowledge source"""
        try:
            # Delete documents for this source
            self.documents_collection.delete(
                where={"metadata.source_id": source_id}
            )
            return True
        except Exception as e:
            print(f"Error deleting source {source_id}: {e}")
            return False

    def get_stats(self):
        """Get knowledge fabric statistics"""
        try:
            all_docs = self.documents_collection.get()
            total_documents = len(all_docs["documents"]) if all_docs["documents"] else 0
            
            # Count unique sources
            sources = set()
            for metadata in all_docs["metadatas"]:
                if metadata and "source_id" in metadata:
                    sources.add(metadata["source_id"])
            
            return {
                "total_sources": len(sources),
                "total_documents": total_documents,
                "total_embeddings": total_documents,
                "model_status": "active",
                "last_training": None
            }
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {
                "total_sources": 0,
                "total_documents": 0,
                "total_embeddings": 0,
                "model_status": "inactive",
                "last_training": None
            }

    def get_source_documents(self, source_id: str):
        """Get documents for a specific source"""
        try:
            results = self.documents_collection.get(
                where={"metadata.source_id": source_id}
            )
            return results
        except Exception as e:
            print(f"Error getting source documents: {e}")
            return {"documents": [], "metadatas": [], "ids": []}

    def export_source(self, source_id: str):
        """Export a knowledge source"""
        try:
            source = self.get_source(source_id)
            if not source:
                return None
            
            documents = self.get_source_documents(source_id)
            return {
                "source": source,
                "documents": documents
            }
        except Exception as e:
            print(f"Error exporting source: {e}")
            return None

    def add_documents_simple(self, documents: List[str], source_name: str, source_type: str, metadata: Dict[str, Any] = None) -> str:
        """Add documents with simplified interface"""
        if not documents:
            return None
        
        source_id = f"{source_type}_{uuid.uuid4().hex[:8]}"
        
        # Prepare documents for vector service
        doc_list = []
        for i, doc in enumerate(documents):
            doc_metadata = metadata or {}
            doc_metadata.update({
                "source_id": source_id,
                "source_name": source_name,
                "source_type": source_type,
                "file_type": source_type
            })
            
            doc_list.append({
                "content": doc,
                "source_name": source_name,
                "page_number": i + 1,
                "file_name": source_name,
                "created_at": datetime.now().isoformat(),
                "metadata": doc_metadata
            })
        
        # Add to vector database
        doc_ids = self.add_documents(doc_list, source_id)
        return source_id

    def search_similar_chunks(self, query: str, source_id: str = None, top_k: int = 3) -> List[Dict[str, Any]]:
        """Search for similar chunks in the knowledge base"""
        try:
            # Create query embedding
            query_embedding = self.create_embeddings([query])[0]
            
            # Prepare where clause for source filtering
            where_clause = None
            if source_id:
                where_clause = {"source_id": source_id}
            
            # Search in collection
            results = self.documents_collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_clause
            )
            
            # Process results
            processed_results = []
            if results["documents"] and results["documents"][0]:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0]
                )):
                    processed_results.append({
                        "content": doc,
                        "metadata": metadata,
                        "similarity_score": 1 - distance,  # Convert distance to similarity
                        "rank": i + 1
                    })
            
            return processed_results
            
        except Exception as e:
            print(f"Error in search_similar_chunks: {e}")
            return []

# Global instance
vector_service = VectorService() 