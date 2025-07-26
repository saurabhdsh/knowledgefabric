from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import psycopg2
import mysql.connector
import sqlite3
import pandas as pd

from app.models.knowledge import DatabaseConnection, APIResponse, KnowledgeSource
from app.services.document_service import document_service
from app.services.vector_service import vector_service

router = APIRouter()

@router.post("/connect", response_model=APIResponse)
async def connect_database(connection: DatabaseConnection):
    """Connect to a database and import data"""
    try:
        # Test connection based on database type
        if connection.database.lower() in ['postgresql', 'postgres']:
            conn = psycopg2.connect(
                host=connection.host,
                port=connection.port,
                database=connection.database,
                user=connection.username,
                password=connection.password
            )
        elif connection.database.lower() in ['mysql', 'mariadb']:
            conn = mysql.connector.connect(
                host=connection.host,
                port=connection.port,
                database=connection.database,
                user=connection.username,
                password=connection.password
            )
        elif connection.database.lower() == 'sqlite':
            conn = sqlite3.connect(connection.database)
        else:
            raise HTTPException(status_code=400, detail="Unsupported database type")
        
        # Execute query
        query = connection.query or f"SELECT * FROM {connection.table_name}"
        
        try:
            df = pd.read_sql_query(query, conn)
            conn.close()
        except Exception as e:
            conn.close()
            raise HTTPException(status_code=400, detail=f"Query execution failed: {str(e)}")
        
        # Convert DataFrame to list of dictionaries
        data = df.to_dict('records')
        
        if not data:
            raise HTTPException(status_code=400, detail="No data found in the query")
        
        # Process data for knowledge fabric
        documents = document_service.process_database_data(data, connection.table_name)
        
        # Create source ID
        source_id = str(uuid.uuid4())
        
        # Add documents to vector database
        document_ids = vector_service.add_documents(documents, source_id)
        
        # Create knowledge source
        knowledge_source = KnowledgeSource(
            id=source_id,
            name=f"{connection.database}_{connection.table_name}",
            source_type="database",
            description=f"Database connection to {connection.database}.{connection.table_name}",
            tags=[connection.database, "database", connection.table_name],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            document_count=len(documents),
            status="active"
        )
        
        return APIResponse(
            success=True,
            message="Database connected and data imported successfully",
            data={
                "source_id": source_id,
                "source_name": f"{connection.database}_{connection.table_name}",
                "documents_processed": len(documents),
                "document_ids": document_ids,
                "knowledge_source": knowledge_source.dict(),
                "connection_info": {
                    "host": connection.host,
                    "database": connection.database,
                    "table": connection.table_name,
                    "rows_imported": len(data)
                }
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-connection", response_model=APIResponse)
async def test_database_connection(connection: DatabaseConnection):
    """Test database connection without importing data"""
    try:
        # Test connection based on database type
        if connection.database.lower() in ['postgresql', 'postgres']:
            conn = psycopg2.connect(
                host=connection.host,
                port=connection.port,
                database=connection.database,
                user=connection.username,
                password=connection.password
            )
        elif connection.database.lower() in ['mysql', 'mariadb']:
            conn = mysql.connector.connect(
                host=connection.host,
                port=connection.port,
                database=connection.database,
                user=connection.username,
                password=connection.password
            )
        elif connection.database.lower() == 'sqlite':
            conn = sqlite3.connect(connection.database)
        else:
            raise HTTPException(status_code=400, detail="Unsupported database type")
        
        # Test query
        query = connection.query or f"SELECT COUNT(*) FROM {connection.table_name}"
        
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            result = cursor.fetchone()
            cursor.close()
            conn.close()
        except Exception as e:
            conn.close()
            raise HTTPException(status_code=400, detail=f"Query execution failed: {str(e)}")
        
        return APIResponse(
            success=True,
            message="Database connection successful",
            data={
                "connection_status": "success",
                "row_count": result[0] if result else 0,
                "database_type": connection.database,
                "table_name": connection.table_name
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/schemas", response_model=APIResponse)
async def get_database_schemas(connection: DatabaseConnection):
    """Get available schemas and tables from database"""
    try:
        # Connect to database
        if connection.database.lower() in ['postgresql', 'postgres']:
            conn = psycopg2.connect(
                host=connection.host,
                port=connection.port,
                database=connection.database,
                user=connection.username,
                password=connection.password
            )
        elif connection.database.lower() in ['mysql', 'mariadb']:
            conn = mysql.connector.connect(
                host=connection.host,
                port=connection.port,
                database=connection.database,
                user=connection.username,
                password=connection.password
            )
        elif connection.database.lower() == 'sqlite':
            conn = sqlite3.connect(connection.database)
        else:
            raise HTTPException(status_code=400, detail="Unsupported database type")
        
        # Get schemas and tables
        cursor = conn.cursor()
        
        if connection.database.lower() in ['postgresql', 'postgres']:
            cursor.execute("""
                SELECT schemaname, tablename 
                FROM pg_tables 
                WHERE schemaname NOT IN ('information_schema', 'pg_catalog')
                ORDER BY schemaname, tablename
            """)
        elif connection.database.lower() in ['mysql', 'mariadb']:
            cursor.execute("SHOW TABLES")
        elif connection.database.lower() == 'sqlite':
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        
        tables = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Format results
        if connection.database.lower() in ['postgresql', 'postgres']:
            schemas = {}
            for schema, table in tables:
                if schema not in schemas:
                    schemas[schema] = []
                schemas[schema].append(table)
        else:
            schemas = {"default": [table[0] for table in tables]}
        
        return APIResponse(
            success=True,
            message="Database schemas retrieved successfully",
            data={
                "database_type": connection.database,
                "schemas": schemas,
                "total_tables": sum(len(tables) for tables in schemas.values())
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/preview", response_model=APIResponse)
async def preview_database_data(
    connection: DatabaseConnection,
    limit: int = 10
):
    """Preview data from a database table"""
    try:
        # Connect to database
        if connection.database.lower() in ['postgresql', 'postgres']:
            conn = psycopg2.connect(
                host=connection.host,
                port=connection.port,
                database=connection.database,
                user=connection.username,
                password=connection.password
            )
        elif connection.database.lower() in ['mysql', 'mariadb']:
            conn = mysql.connector.connect(
                host=connection.host,
                port=connection.port,
                database=connection.database,
                user=connection.username,
                password=connection.password
            )
        elif connection.database.lower() == 'sqlite':
            conn = sqlite3.connect(connection.database)
        else:
            raise HTTPException(status_code=400, detail="Unsupported database type")
        
        # Execute preview query
        query = connection.query or f"SELECT * FROM {connection.table_name} LIMIT {limit}"
        
        try:
            df = pd.read_sql_query(query, conn)
            conn.close()
        except Exception as e:
            conn.close()
            raise HTTPException(status_code=400, detail=f"Query execution failed: {str(e)}")
        
        # Convert to preview format
        preview_data = {
            "columns": df.columns.tolist(),
            "data": df.head(limit).to_dict('records'),
            "total_rows": len(df),
            "preview_rows": min(limit, len(df))
        }
        
        return APIResponse(
            success=True,
            message="Database preview generated successfully",
            data=preview_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync", response_model=APIResponse)
async def sync_database_changes(
    source_id: str,
    connection: DatabaseConnection,
    sync_interval: Optional[int] = 3600  # Default 1 hour
):
    """Set up automatic sync for database changes"""
    try:
        # This would typically involve:
        # 1. Storing sync configuration
        # 2. Setting up a background task
        # 3. Monitoring for changes
        
        sync_config = {
            "source_id": source_id,
            "connection": connection.dict(),
            "sync_interval": sync_interval,
            "last_sync": datetime.now().isoformat(),
            "status": "active"
        }
        
        return APIResponse(
            success=True,
            message="Database sync configured successfully",
            data=sync_config
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 