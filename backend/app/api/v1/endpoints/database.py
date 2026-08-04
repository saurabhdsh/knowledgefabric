from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import psycopg2
import mysql.connector
import sqlite3
import pandas as pd
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from app.models.knowledge import DatabaseConnection, MongoDBConnection, APIResponse, KnowledgeSource
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

# MongoDB Atlas specific endpoints
@router.post("/mongodb/connect", response_model=APIResponse)
async def connect_mongodb(connection: MongoDBConnection):
    """Connect to MongoDB Atlas and import one or more collections into a single source."""
    try:
        collection_names = connection.resolved_collection_names()
        if not collection_names:
            raise HTTPException(
                status_code=400,
                detail="Select at least one collection (collection_name or collection_names).",
            )

        client = MongoClient(connection.connection_string, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        db = client[connection.database_name]
        available = set(db.list_collection_names())
        missing = [n for n in collection_names if n not in available]
        if missing:
            client.close()
            raise HTTPException(
                status_code=400,
                detail=f"Collection(s) not found: {', '.join(missing)}",
            )

        query = connection.query or {}
        projection = connection.projection
        limit = connection.limit or 1000

        processed_data = []
        per_collection = []
        for coll_name in collection_names:
            collection = db[coll_name]
            cursor = collection.find(query, projection).limit(limit)
            data = list(cursor)
            for doc in data:
                doc_dict = {}
                for key, value in doc.items():
                    if hasattr(value, '__dict__'):
                        doc_dict[key] = str(value)
                    else:
                        doc_dict[key] = value
                doc_dict["__source_collection"] = coll_name
                processed_data.append(doc_dict)
            per_collection.append({"name": coll_name, "documents_imported": len(data)})

        if not processed_data:
            client.close()
            raise HTTPException(status_code=400, detail="No data found in the selected collection(s)")

        source_label = (
            collection_names[0]
            if len(collection_names) == 1
            else f"{connection.database_name}_multi"
        )
        documents = document_service.process_database_data(processed_data, source_label)
        source_id = str(uuid.uuid4())
        document_ids = vector_service.add_documents(documents, source_id)

        fabric_label = (
            "_".join(collection_names)
            if len(collection_names) <= 3
            else f"{len(collection_names)}_collections"
        )
        knowledge_source = KnowledgeSource(
            id=source_id,
            name=f"{connection.database_name}_{fabric_label}",
            source_type="database",
            description=(
                f"MongoDB Atlas connection to {connection.database_name}: "
                f"{', '.join(collection_names)}"
            ),
            tags=[
                connection.database_name,
                "mongodb",
                "atlas",
                *collection_names,
                *(["multi-collection"] if len(collection_names) > 1 else []),
            ],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            document_count=len(documents),
            status="active"
        )

        client.close()

        return APIResponse(
            success=True,
            message="MongoDB Atlas connected and data imported successfully",
            data={
                "source_id": source_id,
                "source_name": f"{connection.database_name}_{fabric_label}",
                "documents_processed": len(documents),
                "document_ids": document_ids,
                "knowledge_source": knowledge_source.dict(),
                "connection_info": {
                    "database": connection.database_name,
                    "collection": collection_names[0],
                    "collections": collection_names,
                    "documents_imported": len(processed_data),
                    "per_collection": per_collection,
                }
            }
        )

    except HTTPException:
        raise
    except ConnectionFailure as e:
        raise HTTPException(status_code=400, detail=f"MongoDB connection failed: {str(e)}")
    except ServerSelectionTimeoutError as e:
        raise HTTPException(status_code=400, detail=f"MongoDB server selection timeout: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/mongodb/test-connection", response_model=APIResponse)
async def test_mongodb_connection(connection: MongoDBConnection):
    """Test MongoDB Atlas connection without importing data."""
    try:
        client = MongoClient(connection.connection_string, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        db = client[connection.database_name]
        available = db.list_collection_names()
        selected = connection.resolved_collection_names()

        document_count = 0
        per_collection = []
        if selected:
            missing = [n for n in selected if n not in available]
            if missing:
                client.close()
                raise HTTPException(
                    status_code=400,
                    detail=f"Collection(s) not found: {', '.join(missing)}",
                )
            for name in selected:
                count = db[name].count_documents(connection.query or {})
                document_count += count
                per_collection.append({"name": name, "document_count": count})
        else:
            document_count = sum(db[n].count_documents({}) for n in available[:20])

        client.close()

        return APIResponse(
            success=True,
            message="MongoDB Atlas connection successful",
            data={
                "connection_status": "success",
                "document_count": document_count,
                "database_name": connection.database_name,
                "collection_name": selected[0] if len(selected) == 1 else None,
                "collections": selected or available,
                "per_collection": per_collection,
                "total_collections_in_db": len(available),
            }
        )

    except HTTPException:
        raise
    except ConnectionFailure as e:
        raise HTTPException(status_code=400, detail=f"MongoDB connection failed: {str(e)}")
    except ServerSelectionTimeoutError as e:
        raise HTTPException(status_code=400, detail=f"MongoDB server selection timeout: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/mongodb/collections", response_model=APIResponse)
async def get_mongodb_collections(connection: MongoDBConnection):
    """Get available collections from MongoDB database"""
    try:
        # Connect to MongoDB
        client = MongoClient(connection.connection_string, serverSelectionTimeoutMS=5000)
        
        # Test the connection
        client.admin.command('ping')
        
        # Get database
        db = client[connection.database_name]
        
        # Get collections
        collections = db.list_collection_names()
        
        # Get collection info
        collection_info = []
        for collection_name in collections:
            collection = db[collection_name]
            count = collection.count_documents({})
            collection_info.append({
                "name": collection_name,
                "document_count": count
            })
        
        # Close connection
        client.close()
        
        return APIResponse(
            success=True,
            message="MongoDB collections retrieved successfully",
            data={
                "database_name": connection.database_name,
                "collections": collection_info,
                "total_collections": len(collections)
            }
        )
        
    except ConnectionFailure as e:
        raise HTTPException(status_code=400, detail=f"MongoDB connection failed: {str(e)}")
    except ServerSelectionTimeoutError as e:
        raise HTTPException(status_code=400, detail=f"MongoDB server selection timeout: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/mongodb/preview", response_model=APIResponse)
async def preview_mongodb_data(
    connection: MongoDBConnection,
    limit: int = 10
):
    """Preview data from one or more MongoDB collections."""
    try:
        collection_names = connection.resolved_collection_names()
        if not collection_names:
            raise HTTPException(status_code=400, detail="Select at least one collection to preview.")

        client = MongoClient(connection.connection_string, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        db = client[connection.database_name]
        query = connection.query or {}
        projection = connection.projection

        per_collection = []
        sample_documents = []
        total_documents = 0
        for coll_name in collection_names:
            collection = db[coll_name]
            count = collection.count_documents(query)
            total_documents += count
            docs = list(collection.find(query, projection).limit(limit))
            for doc in docs:
                sample = {k: (str(v) if hasattr(v, "__dict__") else v) for k, v in doc.items()}
                sample["__source_collection"] = coll_name
                sample_documents.append(sample)
            per_collection.append({
                "collection_name": coll_name,
                "total_documents": count,
                "preview_count": len(docs),
            })

        client.close()

        return APIResponse(
            success=True,
            message="MongoDB preview generated successfully",
            data={
                "sample_documents": sample_documents,
                "total_documents": total_documents,
                "preview_count": len(sample_documents),
                "collection_name": collection_names[0] if len(collection_names) == 1 else None,
                "collections": collection_names,
                "per_collection": per_collection,
                "database_name": connection.database_name,
            }
        )

    except HTTPException:
        raise
    except ConnectionFailure as e:
        raise HTTPException(status_code=400, detail=f"MongoDB connection failed: {str(e)}")
    except ServerSelectionTimeoutError as e:
        raise HTTPException(status_code=400, detail=f"MongoDB server selection timeout: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 