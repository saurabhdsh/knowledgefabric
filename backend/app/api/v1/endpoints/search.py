from fastapi import APIRouter, HTTPException
from typing import Optional
import time

from app.models.knowledge import SearchRequest, SearchResponse, SearchResult, APIResponse
from app.services.vector_service import vector_service

router = APIRouter()

@router.post("/", response_model=SearchResponse)
async def search_knowledge(request: SearchRequest):
    """Search the knowledge fabric for relevant information"""
    try:
        start_time = time.time()
        
        # Perform search
        results = vector_service.search_documents(
            query=request.query,
            limit=request.limit,
            threshold=request.threshold,
            filters=request.filters
        )
        
        # Convert to SearchResult objects
        search_results = []
        for result in results:
            search_result = SearchResult(
                id=result["id"],
                content=result["content"],
                source=result["source"],
                similarity_score=result["similarity_score"],
                metadata=result["metadata"],
                page_number=result.get("page_number")
            )
            search_results.append(search_result)
        
        processing_time = time.time() - start_time
        
        return SearchResponse(
            results=search_results,
            total_results=len(search_results),
            query=request.query,
            processing_time=processing_time
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/semantic", response_model=SearchResponse)
async def semantic_search(
    query: str,
    limit: int = 5,
    threshold: float = 0.7,
    context_window: int = 3
):
    """Perform semantic search with context window"""
    try:
        start_time = time.time()
        
        # Perform initial search
        initial_results = vector_service.search_documents(
            query=query,
            limit=limit * 2,  # Get more results for context
            threshold=threshold
        )
        
        # Group results by source and add context
        grouped_results = {}
        for result in initial_results:
            source = result["source"]
            if source not in grouped_results:
                grouped_results[source] = []
            grouped_results[source].append(result)
        
        # Create contextual results
        contextual_results = []
        for source, results in grouped_results.items():
            # Sort by page number if available
            sorted_results = sorted(results, key=lambda x: x.get("page_number", 0))
            
            # Create context windows
            for i, result in enumerate(sorted_results):
                context_start = max(0, i - context_window)
                context_end = min(len(sorted_results), i + context_window + 1)
                
                # Build contextual content
                context_parts = []
                for j in range(context_start, context_end):
                    if j != i:  # Don't include the main result twice
                        context_parts.append(sorted_results[j]["content"][:200] + "...")
                
                contextual_content = result["content"]
                if context_parts:
                    contextual_content = f"Context: {' '.join(context_parts)}\n\nMain Content: {result['content']}"
                
                contextual_results.append({
                    "id": result["id"],
                    "content": contextual_content,
                    "source": result["source"],
                    "similarity_score": result["similarity_score"],
                    "metadata": result["metadata"],
                    "page_number": result.get("page_number")
                })
        
        # Sort by similarity and take top results
        contextual_results.sort(key=lambda x: x["similarity_score"], reverse=True)
        final_results = contextual_results[:limit]
        
        # Convert to SearchResult objects
        search_results = []
        for result in final_results:
            search_result = SearchResult(
                id=result["id"],
                content=result["content"],
                source=result["source"],
                similarity_score=result["similarity_score"],
                metadata=result["metadata"],
                page_number=result.get("page_number")
            )
            search_results.append(search_result)
        
        processing_time = time.time() - start_time
        
        return SearchResponse(
            results=search_results,
            total_results=len(search_results),
            query=query,
            processing_time=processing_time
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/suggestions")
async def get_search_suggestions(query: str, limit: int = 5):
    """Get search suggestions based on partial query"""
    try:
        # This is a simple implementation - in production you might want to use
        # a more sophisticated approach like autocomplete from previous searches
        suggestions = []
        
        # For now, return some basic suggestions
        if "how" in query.lower():
            suggestions = ["How to", "How do I", "How can I"]
        elif "what" in query.lower():
            suggestions = ["What is", "What are", "What does"]
        elif "when" in query.lower():
            suggestions = ["When to", "When is", "When does"]
        elif "where" in query.lower():
            suggestions = ["Where to", "Where is", "Where can I"]
        elif "why" in query.lower():
            suggestions = ["Why is", "Why does", "Why should I"]
        else:
            suggestions = ["What is", "How to", "When to", "Where to", "Why is"]
        
        return APIResponse(
            success=True,
            message="Search suggestions retrieved",
            data={
                "query": query,
                "suggestions": suggestions[:limit]
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/statistics")
async def get_search_statistics():
    """Get search and knowledge fabric statistics"""
    try:
        stats = vector_service.get_all_statistics()
        
        return APIResponse(
            success=True,
            message="Statistics retrieved successfully",
            data=stats
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 