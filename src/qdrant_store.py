"""
Qdrant metadata store module for storing and retrieving metadata.
Complements the vector store by handling structured metadata like images.
"""

import os
import logging
from typing import List, Dict, Optional, Any, Union
import time
import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import PointStruct, VectorParams, Distance, Filter, FieldCondition, MatchValue

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class QdrantStore:
    """Manages structured metadata including image information using Qdrant."""
    
    def __init__(self, 
                 host: Optional[str] = None, 
                 port: Optional[int] = None,
                 path: Optional[str] = "./qdrant_db",
                 in_memory: bool = False):
        """
        Initialize the Qdrant metadata store.
        
        Args:
            host: Qdrant server host (if using remote)
            port: Qdrant server port (if using remote)
            path: Path for local persistence (if not using remote)
            in_memory: Whether to use in-memory storage (default: False)
        """
        self.collections = {}
        
        # Setup client based on configuration
        if host and port:
            # Use remote Qdrant instance
            self.client = QdrantClient(host=host, port=port)
            logger.info(f"Connected to remote Qdrant server at {host}:{port}")
        elif in_memory:
            # Use in-memory storage
            self.client = QdrantClient(location=":memory:")
            logger.info("Using in-memory Qdrant storage")
        else:
            # Use local persistence
            os.makedirs(path, exist_ok=True)
            self.client = QdrantClient(path=path)
            logger.info(f"Using local Qdrant storage at {path}")
    
    def _get_or_create_collection(self, collection_name: str) -> None:
        """Ensure collection exists, creating it if necessary."""
        try:
            # Check if collection exists
            collections = self.client.get_collections().collections
            collection_names = [collection.name for collection in collections]
            
            if collection_name not in collection_names:
                # Create collection with necessary vectors and payload schema
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=1,  # Placeholder vector size
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created new Qdrant collection: {collection_name}")
            else:
                logger.info(f"Using existing Qdrant collection: {collection_name}")
                
        except Exception as e:
            logger.error(f"Error creating Qdrant collection {collection_name}: {str(e)}")
            raise
    
    def add_metadata(self, collection_name: str, documents: List[Dict]) -> bool:
        """
        Add metadata to the Qdrant store.
        
        Args:
            collection_name: Name of the collection
            documents: List of document metadata to add
            
        Returns:
            Success status
        """
        try:
            # Ensure collection exists
            self._get_or_create_collection(collection_name)
            
            # Process and upload metadata in batches
            batch_size = 100
            points = []
            
            for i, doc in enumerate(documents):
                # Extract metadata to store
                metadata = doc.get('metadata', {})
                url = doc.get('url', '')
                
                # Extract image info if available
                images = doc.get('images', [])
                
                # Add any other metadata fields here
                payload = {
                    "url": url,
                    "metadata": metadata,
                    "images": images,
                    "indexed_at": time.time()
                }
                
                # Generate a unique ID for each point
                point_id = str(uuid.uuid4())
                
                # Create point with a unique ID and dummy vector (since we're just using Qdrant for metadata)
                point = PointStruct(
                    id=point_id,
                    vector=[0.0],  # Dummy vector
                    payload=payload
                )
                points.append(point)
                
                # Upload in batches
                if len(points) >= batch_size or i == len(documents) - 1:
                    if points:  # Make sure points list is not empty
                        self.client.upsert(
                            collection_name=collection_name,
                            points=points
                        )
                        points = []  # Clear points after batch upload
            
            logger.info(f"Added metadata for {len(documents)} documents to Qdrant collection {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding metadata to Qdrant collection {collection_name}: {str(e)}")
            return False
    
    def get_images(self, collection_name: str, limit: int = 100) -> List[Dict]:
        """
        Retrieve all images from the collection.
        
        Args:
            collection_name: Name of the collection
            limit: Maximum number of results to return
            
        Returns:
            List of image information
        """
        try:
            # Ensure collection exists
            try:
                self._get_or_create_collection(collection_name)
            except Exception:
                # If collection doesn't exist, return empty list
                return []
                
            # Query for all points and filter those with images in Python
            # This approach doesn't use IsNotEmpty since it's not available
            search_result = self.client.scroll(
                collection_name=collection_name,
                limit=limit,
                with_payload=True,
                with_vectors=False
            )
            
            # Extract image information
            results = []
            points, _ = search_result  # Unpack tuple (points, next_page_offset)
            
            for point in points:
                if "images" in point.payload and point.payload["images"]:
                    # Only process points that have non-empty images list
                    for image in point.payload["images"]:
                        results.append({
                            "url": image.get("src", ""),
                            "alt": image.get("alt", ""),
                            "page_url": point.payload.get("url", ""),
                            "dimensions": f"{image.get('width', 'unknown')}x{image.get('height', 'unknown')}"
                        })
            
            return results
            
        except Exception as e:
            logger.error(f"Error retrieving images from Qdrant collection {collection_name}: {str(e)}")
            return []
    
    def search_by_url(self, collection_name: str, url: str) -> Optional[Dict]:
        """
        Find metadata for a specific URL.
        
        Args:
            collection_name: Name of the collection
            url: URL to search for
            
        Returns:
            Metadata for the URL if found
        """
        try:
            # Ensure collection exists
            try:
                self._get_or_create_collection(collection_name)
            except Exception:
                return None
                
            search_result = self.client.scroll(
                collection_name=collection_name,
                limit=1,
                with_payload=True,
                with_vectors=False,
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="url",
                            match=MatchValue(value=url)
                        )
                    ]
                )
            )
            
            points, _ = search_result  # Unpack tuple
            if points:
                return points[0].payload
            return None
            
        except Exception as e:
            logger.error(f"Error searching Qdrant collection {collection_name} by URL: {str(e)}")
            return None
    
    def get_collections(self) -> List[str]:
        """Get all collection names in the Qdrant store."""
        try:
            collections = self.client.get_collections().collections
            return [collection.name for collection in collections]
        except Exception as e:
            logger.error(f"Error listing Qdrant collections: {str(e)}")
            return []
    
    def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection from the Qdrant store."""
        try:
            self.client.delete_collection(collection_name=collection_name)
            logger.info(f"Deleted Qdrant collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting Qdrant collection {collection_name}: {str(e)}")
            return False
        
        