from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import List, Optional
import uuid
from datetime import datetime

from app.models.knowledge import UploadRequest, APIResponse, KnowledgeSource
from app.services.document_service import document_service
from app.services.vector_service import vector_service

router = APIRouter()

@router.get("/files", response_model=APIResponse)
async def get_uploaded_files():
    """Get list of uploaded files"""
    try:
        files = document_service.get_uploaded_files()
        return APIResponse(
            success=True,
            message="Uploaded files retrieved successfully",
            data=files
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=APIResponse)
async def upload_files(
    files: List[UploadFile] = File(...)
):
    """Upload multiple files (general endpoint)"""
    try:
        results = []
        
        for file in files:
            try:
                print(f"Processing file: {file.filename}, size: {file.size}")
                
                # Validate file
                if not document_service.validate_file(file):
                    print(f"File validation failed for: {file.filename}")
                    results.append({
                        "file": file.filename,
                        "status": "error",
                        "message": "Invalid file type"
                    })
                    continue
                
                # Save file
                file_path = await document_service.save_uploaded_file(file)
                print(f"File saved to: {file_path}")
                
                results.append({
                    "file": file.filename,
                    "status": "success",
                    "file_path": file_path
                })
                
            except Exception as e:
                print(f"Error processing file {file.filename}: {e}")
                results.append({
                    "file": file.filename,
                    "status": "error",
                    "message": str(e)
                })
        
        return APIResponse(
            success=True,
            message=f"Uploaded {len(files)} files",
            data={
                "total_files": len(files),
                "results": results
            }
        )
        
    except Exception as e:
        print(f"Upload error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/pdf", response_model=APIResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form("")
):
    """Upload and process a PDF file"""
    try:
        # Validate file
        if not document_service.validate_file(file):
            raise HTTPException(status_code=400, detail="Invalid file type")
        
        # Save file
        file_path = await document_service.save_uploaded_file(file)
        
        # Extract text from PDF
        documents = document_service.extract_text_from_pdf(file_path)
        
        if not documents:
            raise HTTPException(status_code=400, detail="No text content found in PDF")
        
        # Create source ID
        source_id = str(uuid.uuid4())
        
        # Add documents to vector database
        document_ids = vector_service.add_documents(documents, source_id)
        
        # Create knowledge source
        source_name = file.filename.replace('.pdf', '')
        knowledge_source = KnowledgeSource(
            id=source_id,
            name=source_name,
            source_type="pdf",
            description=description,
            tags=tags.split(",") if tags else [],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            document_count=len(documents),
            status="active"
        )
        
        return APIResponse(
            success=True,
            message="PDF uploaded and processed successfully",
            data={
                "source_id": source_id,
                "source_name": source_name,
                "documents_processed": len(documents),
                "document_ids": document_ids,
                "knowledge_source": knowledge_source.dict()
            }
        )
        
    except Exception as e:
        # Clean up file if it was saved
        if 'file_path' in locals():
            document_service.delete_file(file_path)
        
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/text", response_model=APIResponse)
async def upload_text(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form("")
):
    """Upload and process a text file"""
    try:
        # Validate file
        if not document_service.validate_file(file):
            raise HTTPException(status_code=400, detail="Invalid file type")
        
        # Save file
        file_path = await document_service.save_uploaded_file(file)
        
        # Extract text from file
        documents = document_service.extract_text_from_txt(file_path)
        
        if not documents:
            raise HTTPException(status_code=400, detail="No text content found in file")
        
        # Create source ID
        source_id = str(uuid.uuid4())
        
        # Add documents to vector database
        document_ids = vector_service.add_documents(documents, source_id)
        
        # Create knowledge source
        source_name = file.filename.replace('.txt', '')
        knowledge_source = KnowledgeSource(
            id=source_id,
            name=source_name,
            source_type="text",
            description=description,
            tags=tags.split(",") if tags else [],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            document_count=len(documents),
            status="active"
        )
        
        return APIResponse(
            success=True,
            message="Text file uploaded and processed successfully",
            data={
                "source_id": source_id,
                "source_name": source_name,
                "documents_processed": len(documents),
                "document_ids": document_ids,
                "knowledge_source": knowledge_source.dict()
            }
        )
        
    except Exception as e:
        # Clean up file if it was saved
        if 'file_path' in locals():
            document_service.delete_file(file_path)
        
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/multiple", response_model=APIResponse)
async def upload_multiple_files(
    files: List[UploadFile] = File(...),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form("")
):
    """Upload and process multiple files"""
    try:
        results = []
        total_documents = 0
        
        for file in files:
            try:
                # Validate file
                if not document_service.validate_file(file):
                    results.append({
                        "file": file.filename,
                        "status": "error",
                        "message": "Invalid file type"
                    })
                    continue
                
                # Save file
                file_path = await document_service.save_uploaded_file(file)
                
                # Process based on file type
                file_extension = file.filename.lower().split('.')[-1]
                
                if file_extension == 'pdf':
                    documents = document_service.extract_text_from_pdf(file_path)
                elif file_extension == 'txt':
                    documents = document_service.extract_text_from_txt(file_path)
                else:
                    results.append({
                        "file": file.filename,
                        "status": "error",
                        "message": "Unsupported file type"
                    })
                    continue
                
                if not documents:
                    results.append({
                        "file": file.filename,
                        "status": "error",
                        "message": "No content found"
                    })
                    continue
                
                # Create source ID
                source_id = str(uuid.uuid4())
                
                # Add documents to vector database
                document_ids = vector_service.add_documents(documents, source_id)
                
                total_documents += len(documents)
                
                results.append({
                    "file": file.filename,
                    "status": "success",
                    "source_id": source_id,
                    "documents_processed": len(documents)
                })
                
            except Exception as e:
                results.append({
                    "file": file.filename,
                    "status": "error",
                    "message": str(e)
                })
        
        return APIResponse(
            success=True,
            message=f"Processed {len(files)} files",
            data={
                "total_files": len(files),
                "total_documents": total_documents,
                "results": results
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 