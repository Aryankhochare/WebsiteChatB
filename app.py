"""
FastAPI application for the RAG-powered website chatbot.
Provides API endpoints for indexing websites and querying content with enhanced image handling.
"""

import os
import logging
from typing import List, Dict, Optional, Any
import asyncio

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, HttpUrl

from src.rag_engine import RAGEngine

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="RAG Website Chatbot API",
    description="API for indexing websites and querying content using RAG with image support",
    version="1.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Get application base URL from environment or use default
base_url = os.getenv("BASE_URL", "http://localhost:8000")

# Initialize RAG engine
rag_engine = RAGEngine(
    max_depth=int(os.getenv("MAX_DEPTH", "2")),
    max_pages=int(os.getenv("MAX_PAGES", "50")),
    vector_persist_directory=os.getenv("VECTOR_DB_PATH", "./chroma_db"),
    metadata_persist_directory=os.getenv("METADATA_DB_PATH", "./qdrant_db"),
    gemini_api_key=os.getenv("GOOGLE_API_KEY"),
    base_url=base_url
)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Pydantic models for API requests and responses
class IndexRequest(BaseModel):
    url: HttpUrl
    max_depth: Optional[int] = 2
    max_pages: Optional[int] = 50

class QueryRequest(BaseModel):
    query: str
    collection_name: str
    top_k: Optional[int] = 5

class IndexResponse(BaseModel):
    collection_name: str
    document_count: int
    message: str
    status: str

class QueryResponse(BaseModel):
    query: str
    response: str
    collection_name: str

class CollectionInfo(BaseModel):
    name: str
    url: str
    document_count: int
    indexed_at: float
    domain: str
    image_count: int

class ImageInfo(BaseModel):
    url: str
    alt: Optional[str] = None
    page_url: Optional[str] = None
    dimensions: Optional[str] = None

class ImagesResponse(BaseModel):
    collection_name: str
    images: List[Dict[str, Any]]
    count: int

# Routes
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Render the home page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api")
async def api_info():
    """API information endpoint."""
    return {
        "message": "RAG Website Chatbot API with Image Support",
        "docs": "/docs",
        "version": "1.1.0"
    }

@app.post("/index", response_model=IndexResponse)
async def index_website(request: IndexRequest, background_tasks: BackgroundTasks):
    """
    Index a website by URL.
    
    - **url**: URL to index
    - **max_depth**: Maximum crawl depth (optional)
    - **max_pages**: Maximum number of pages to crawl (optional)
    """
    # Update RAG engine configuration
    rag_engine.scraper.max_depth = request.max_depth
    rag_engine.scraper.max_pages = request.max_pages
    
    try:
        # Start indexing in background task
        collection_name, document_count = await rag_engine.index_website(str(request.url))
        
        if not collection_name or document_count == 0:
            raise HTTPException(status_code=400, detail="Failed to index website - no content found")
        
        return {
            "collection_name": collection_name,
            "document_count": document_count,
            "message": f"Successfully indexed {document_count} pages from {request.url}",
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Error indexing website: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error indexing website: {str(e)}")

@app.post("/query", response_model=QueryResponse)
async def query_collection(request: QueryRequest):
    """
    Query indexed website content.
    
    - **query**: Question or query to answer
    - **collection_name**: Name of the indexed collection to query
    - **top_k**: Number of documents to retrieve (optional)
    
    Note: Including image-related terms like 'image', 'picture', 'photo', etc. 
    will trigger the image display functionality.
    """
    try:
        # Check if collection exists
        collections = rag_engine.get_collections()
        if request.collection_name not in collections:
            raise HTTPException(status_code=404, detail=f"Collection '{request.collection_name}' not found")
        
        # Generate response using the enhanced handle_query method
        response = await rag_engine.handle_query(
            question=request.query,
            collection_name=request.collection_name,
            top_k=request.top_k
        )
        
        return {
            "query": request.query,
            "response": response,
            "collection_name": request.collection_name
        }
    except Exception as e:
        logger.error(f"Error querying collection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error querying collection: {str(e)}")

@app.get("/collections", response_model=List[str])
async def list_collections():
    """List all indexed collections."""
    try:
        collections = rag_engine.get_collections()
        return collections
    except Exception as e:
        logger.error(f"Error listing collections: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing collections: {str(e)}")

@app.get("/collections/{collection_name}", response_model=CollectionInfo)
@app.get("/collection/{collection_name}", response_model=CollectionInfo)
async def get_collection_info(collection_name: str):
    """Get information about a specific collection."""
    try:
        # Check if collection exists
        collections = rag_engine.get_collections()
        if collection_name not in collections:
            raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
        
        # Get collection info
        indexed_websites = rag_engine.get_indexed_websites()
        if collection_name not in indexed_websites:
            # Try to create a minimal info object if collection exists but metadata is missing
            return {
                "name": collection_name,
                "url": "",
                "document_count": rag_engine.get_collection_size(collection_name),
                "indexed_at": 0,
                "domain": collection_name.split('_')[0] if '_' in collection_name else collection_name,
                "image_count": 0
            }
        
        collection_info = indexed_websites[collection_name]
        return {
            "name": collection_name,
            **collection_info
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting collection info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting collection info: {str(e)}")

@app.delete("/collections/{collection_name}")
@app.delete("/collection/{collection_name}")
async def delete_collection(collection_name: str):
    """Delete a collection and all its data."""
    try:
        # Check if collection exists
        collections = rag_engine.get_collections()
        if collection_name not in collections:
            raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
        
        # Delete collection
        success = rag_engine.delete_collection(collection_name)
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to delete collection '{collection_name}'")
        
        return {"message": f"Collection '{collection_name}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting collection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting collection: {str(e)}")

from fastapi.responses import JSONResponse

@app.get("/images/{collection_name}")
async def view_collection_images(collection_name: str, limit: int = Query(20, ge=1, le=100)):
    """Return images from a specific collection as JSON."""
    try:
        # Check if collection exists
        collections = rag_engine.get_collections()
        if collection_name not in collections:
            raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
        
        # Get images
        images = rag_engine.get_images(collection_name, limit)
        
        # Return JSON
        return {
            "collection_name": collection_name,
            "images": images,
            "count": len(images)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting collection images: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting collection images: {str(e)}")


@app.get("/api/images/{collection_name}", response_model=ImagesResponse)
async def get_collection_images(
    collection_name: str, 
    limit: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = None,
    category: Optional[str] = None,
    sort: Optional[str] = "newest"
):
    """Get images from a specific collection as JSON data."""
    try:
        # Check if collection exists
        collections = rag_engine.get_collections()
        if collection_name not in collections:
            raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
        
        # Get images with pagination, filtering and sorting
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        
        # Get images from RAG engine
        all_images = rag_engine.get_images(collection_name, None)  # Get all images
        filtered_images = []
        
        # Apply search filter if provided
        if search and search.strip():
            search_term = search.lower()
            all_images = [img for img in all_images if 
                         (img.get('alt') and search_term in img.get('alt', '').lower())]
        
        # Apply category filter if provided
        if category and category != 'all':
            all_images = [img for img in all_images if img.get('category') == category]
        
        # Apply sorting
        if sort == "newest":
            all_images.sort(key=lambda x: x.get('indexed_at', 0), reverse=True)
        elif sort == "oldest":
            all_images.sort(key=lambda x: x.get('indexed_at', 0))
        elif sort == "size_desc":
            all_images.sort(key=lambda x: x.get('file_size', 0), reverse=True)
        elif sort == "size_asc":
            all_images.sort(key=lambda x: x.get('file_size', 0))
        elif sort == "alpha":
            all_images.sort(key=lambda x: x.get('alt', '').lower())
        
        # Apply pagination
        paginated_images = all_images[start_idx:end_idx]
        
        return {"collection_name": collection_name, "images": paginated_images, "count": len(all_images)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting collection images: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting collection images: {str(e)}")

@app.get("/image-categories/{collection_name}")
async def get_image_categories(collection_name: str):
    """Get all image categories from a collection."""
    try:
        # Check if collection exists
        collections = rag_engine.get_collections()
        if collection_name not in collections:
            raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
        
        # Get all images
        images = rag_engine.get_images(collection_name, None)
        
        # Extract unique categories
        categories = set()
        for image in images:
            if image.get('category'):
                categories.add(image.get('category'))
        
        return list(categories)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting image categories: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting image categories: {str(e)}")

@app.get("/collection-stats/{collection_name}")
async def get_collection_stats(collection_name: str):
    """Get statistics for a specific collection with better error handling."""
    try:
        # Check if collection exists
        collections = rag_engine.get_collections()
        if collection_name not in collections:
            logger.warning(f"Collection '{collection_name}' not found in available collections")
            raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
        
        # Initialize default stats
        stats = {
            "pages_count": 0,
            "images_count": 0,
            "content_size": 0
        }
        
        # Try to get info from indexed_websites first
        try:
            indexed_websites = rag_engine.get_indexed_websites()
            if collection_name in indexed_websites:
                collection_info = indexed_websites[collection_name]
                stats["pages_count"] = collection_info.get("document_count", 0)
                stats["images_count"] = collection_info.get("image_count", 0)
            else:
                logger.warning(f"Collection '{collection_name}' exists but not found in indexed_websites")
        except Exception as e:
            logger.error(f"Error getting indexed website info: {str(e)}")
            # Continue with default stats
        
        # If we couldn't get pages_count from indexed_websites, try another approach
        if stats["pages_count"] == 0:
            try:
                # Try to use the fixed get_collection_size method
                collection_size = rag_engine.get_collection_size(collection_name)
                if collection_size is not None and collection_size > 0:
                    stats["pages_count"] = collection_size
            except Exception as e:
                logger.error(f"Error getting collection size: {str(e)}")
        
        # Calculate content size if possible
        try:
            if hasattr(rag_engine, 'vector_store') and hasattr(rag_engine.vector_store, 'persist_directory'):
                vector_db_path = os.path.join(rag_engine.vector_store.persist_directory, collection_name)
                if os.path.exists(vector_db_path):
                    stats["content_size"] = sum(os.path.getsize(os.path.join(vector_db_path, f)) 
                                               for f in os.listdir(vector_db_path) 
                                               if os.path.isfile(os.path.join(vector_db_path, f)))
        except Exception as e:
            logger.error(f"Error calculating content size: {str(e)}")
        
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting collection stats: {str(e)}")
        # Return basic stats even in case of errors
        return {
            "pages_count": 0,
            "images_count": 0,
            "content_size": 0
        }

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "rag-website-chatbot"}

# Metrics endpoint
@app.get("/metrics")
async def metrics():
    """Basic metrics about the service."""
    try:
        collections = rag_engine.get_collections()
        websites = rag_engine.get_indexed_websites()
        
        return {
            "total_collections": len(collections),
            "indexed_websites": len(websites),
            "collections": collections
        }
    except Exception as e:
        logger.error(f"Error getting metrics: {str(e)}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)