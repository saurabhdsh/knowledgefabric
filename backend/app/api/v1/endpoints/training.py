from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional
import uuid

from app.models.knowledge import TrainingRequest, TrainingResponse, APIResponse
from app.services.training_service import training_service
from app.services.vector_service import vector_service

router = APIRouter()

@router.post("/start", response_model=APIResponse)
async def start_training(request: TrainingRequest):
    """Start training a new model"""
    try:
        # Get all documents for training
        all_docs = vector_service.documents_collection.get()
        
        if not all_docs["documents"]:
            raise HTTPException(status_code=400, detail="No documents available for training")
        
        # Convert to training format
        documents = []
        for i, doc in enumerate(all_docs["documents"]):
            documents.append({
                "content": doc,
                "metadata": all_docs["metadatas"][i] if all_docs["metadatas"] else {}
            })
        
        # Start training
        result = training_service.train_model(
            documents=documents,
            epochs=request.epochs,
            learning_rate=request.learning_rate,
            batch_size=request.batch_size
        )
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return APIResponse(
            success=True,
            message="Model training started successfully",
            data=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status", response_model=APIResponse)
async def get_training_status():
    """Get current training status"""
    try:
        status = training_service.get_training_status()
        
        return APIResponse(
            success=True,
            message="Training status retrieved",
            data=status
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models", response_model=APIResponse)
async def list_available_models():
    """List all available trained models"""
    try:
        models = training_service.get_available_models()
        
        return APIResponse(
            success=True,
            message=f"Found {len(models)} trained models",
            data=models
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/models/{model_id}/load", response_model=APIResponse)
async def load_model(model_id: str):
    """Load a specific trained model"""
    try:
        success = training_service.load_model(model_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Update vector service with new model
        vector_service.update_model(model_id)
        
        return APIResponse(
            success=True,
            message=f"Model {model_id} loaded successfully",
            data={"model_id": model_id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/models/{model_id}", response_model=APIResponse)
async def delete_model(model_id: str):
    """Delete a trained model"""
    try:
        success = training_service.delete_model(model_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Model not found")
        
        return APIResponse(
            success=True,
            message=f"Model {model_id} deleted successfully",
            data={"model_id": model_id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/fine-tune", response_model=APIResponse)
async def fine_tune_model(
    source_ids: List[str],
    epochs: int = 3,
    learning_rate: float = 2e-5,
    batch_size: int = 32
):
    """Fine-tune model on specific knowledge sources"""
    try:
        # Get documents from specific sources
        all_documents = []
        
        for source_id in source_ids:
            results = vector_service.documents_collection.get(
                where={"metadata.source_id": source_id}
            )
            
            for i, doc in enumerate(results["documents"]):
                all_documents.append({
                    "content": doc,
                    "metadata": results["metadatas"][i] if results["metadatas"] else {}
                })
        
        if not all_documents:
            raise HTTPException(status_code=400, detail="No documents found for specified sources")
        
        # Start fine-tuning
        result = training_service.train_model(
            documents=all_documents,
            epochs=epochs,
            learning_rate=learning_rate,
            batch_size=batch_size
        )
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return APIResponse(
            success=True,
            message="Model fine-tuning started successfully",
            data=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance", response_model=APIResponse)
async def get_model_performance():
    """Get model performance metrics"""
    try:
        # This would typically include metrics like:
        # - Training accuracy
        # - Validation accuracy
        # - Loss curves
        # - Embedding quality metrics
        
        # For now, return basic information
        current_model = training_service.current_model_id or training_service.model_name
        
        performance_data = {
            "current_model": current_model,
            "model_type": "sentence-transformers",
            "embedding_dimension": 384,  # This should be dynamic
            "training_status": "completed" if not training_service.is_training else "training",
            "last_training": None,  # Would be updated during training
            "total_documents_trained": 0,  # Would be updated during training
            "model_size_mb": 0,  # Would be calculated
            "inference_speed_ms": 0  # Would be measured
        }
        
        return APIResponse(
            success=True,
            message="Model performance metrics retrieved",
            data=performance_data
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/evaluate", response_model=APIResponse)
async def evaluate_model(test_queries: List[str]):
    """Evaluate model performance on test queries"""
    try:
        if not test_queries:
            raise HTTPException(status_code=400, detail="No test queries provided")
        
        evaluation_results = []
        
        for query in test_queries:
            # Perform search
            results = vector_service.search_documents(query, limit=5)
            
            evaluation_results.append({
                "query": query,
                "results_count": len(results),
                "top_result_score": results[0]["similarity_score"] if results else 0,
                "average_score": sum(r["similarity_score"] for r in results) / len(results) if results else 0
            })
        
        # Calculate overall metrics
        total_queries = len(evaluation_results)
        avg_top_score = sum(r["top_result_score"] for r in evaluation_results) / total_queries
        avg_average_score = sum(r["average_score"] for r in evaluation_results) / total_queries
        
        return APIResponse(
            success=True,
            message="Model evaluation completed",
            data={
                "total_queries": total_queries,
                "average_top_score": avg_top_score,
                "average_overall_score": avg_average_score,
                "evaluation_results": evaluation_results
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 

@router.get("/validate/{model_id}")
async def validate_model(model_id: str):
    """Validate if a model is properly trained and working"""
    try:
        validation_result = training_service.validate_model(model_id)
        return APIResponse(
            success=True,
            message="Model validation completed",
            data=validation_result,
            error=None
        )
    except Exception as e:
        return APIResponse(
            success=False,
            message="Failed to validate model",
            data=None,
            error=str(e)
        )

@router.get("/models/{model_id}/status")
async def get_model_status(model_id: str):
    """Get detailed status of a specific model"""
    try:
        status = training_service.get_model_status(model_id)
        return APIResponse(
            success=True,
            message="Model status retrieved",
            data=status,
            error=None
        )
    except Exception as e:
        return APIResponse(
            success=False,
            message="Failed to get model status",
            data=None,
            error=str(e)
        )

@router.get("/models")
async def list_models_with_validation():
    """List all available models with validation status"""
    try:
        models = training_service.get_available_models()
        return APIResponse(
            success=True,
            message="Models retrieved with validation",
            data=models,
            error=None
        )
    except Exception as e:
        return APIResponse(
            success=False,
            message="Failed to retrieve models",
            data=None,
            error=str(e)
        ) 