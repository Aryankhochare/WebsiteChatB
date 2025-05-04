"""
Vector database module for storing and retrieving document embeddings.
Provides functionality for similarity search and document management.
"""

import os
import logging
from typing import List, Dict, Optional, Any, Union

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VectorStore:
    """Manages document vectors for efficient similarity search."""
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        """
        Initialize the vector store with configuration parameters.
        
        Args:
            persist_directory: Directory to persist vector database (default: "./chroma_db")
        """
        self.persist_directory = persist_directory
        
        # Create persist directory if it doesn't exist
        os.makedirs(persist_directory, exist_ok=True)
        
        # Initialize ChromaDB client with persistence
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Use default embedding function (all-MiniLM-L6-v2)
        self.embedding_function = embedding_functions.DefaultEmbeddingFunction()
        
        # Keep track of collections
        self.collections = {}
        logger.info(f"Initialized vector store with persistence at {persist_directory}")
    
    def _get_or_create_collection(self, collection_name: str) -> Any:
        """Get or create a collection for the specified URL."""
        if collection_name in self.collections:
            return self.collections[collection_name]
        
        try:
            # Try to get existing collection
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )
            self.collections[collection_name] = collection
            logger.info(f"Retrieved existing collection: {collection_name}")
            return collection
        except Exception:
            # Create new collection if it doesn't exist
            collection = self.client.create_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )
            self.collections[collection_name] = collection
            logger.info(f"Created new collection: {collection_name}")
            return collection
    
    def _sanitize_collection_name(self, url: str) -> str:
        """Convert URL to a valid collection name."""
        # Replace non-alphanumeric characters with underscores
        import re
        # Extract domain name
        import urllib.parse
        domain = urllib.parse.urlparse(url).netloc
        # Remove www if present
        if domain.startswith('www.'):
            domain = domain[4:]
        # Replace dots and other chars with underscores
        collection_name = re.sub(r'[^a-zA-Z0-9]', '_', domain)
        # Add timestamp to make unique
        import time
        timestamp = int(time.time())
        return f"{collection_name}_{timestamp}"

    def create_document_chunks(self, document: Dict, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Dict]:
        """
        Split document into smaller chunks for better retrieval.
        
        Args:
            document: Document dictionary with content and metadata
            chunk_size: Number of characters per chunk (default: 1000)
            chunk_overlap: Number of overlapping characters (default: 200)
            
        Returns:
            List of document chunks
        """
        content = document['content']
        chunks = []
        
        # Simple chunk splitting by character count
        for i in range(0, len(content), chunk_size - chunk_overlap):
            chunk_content = content[i:i + chunk_size]
            
            # Skip if chunk is too small
            if len(chunk_content) < 100:
                continue
            
            # Create chunk metadata
            # ChromaDB doesn't handle complex metadata well, so keep it simple
            # Store only basic metadata in ChromaDB
            chunk_metadata = {
                "chunk_id": str(len(chunks)),
                "source_url": document['url'],
                "title": document.get('metadata', {}).get('title', ''),
                "chunk_start": str(i),
                "chunk_end": str(i + len(chunk_content))
            }
                
            chunk = {
                "content": chunk_content,
                "metadata": chunk_metadata,
                "url": document['url']
            }
            chunks.append(chunk)
            
        return chunks
    
    def add_documents(self, documents: List[Dict], collection_name: Optional[str] = None) -> str:
        """
        Add documents to the vector store.
        
        Args:
            documents: List of documents to add
            collection_name: Optional name for the collection (if None, generated from first URL)
            
        Returns:
            Name of the collection
        """
        if not documents:
            raise ValueError("No documents provided")
        
        # Generate collection name if not provided
        if not collection_name:
            collection_name = self._sanitize_collection_name(documents[0]['url'])
        
        # Get or create collection
        collection = self._get_or_create_collection(collection_name)
        
        # Process documents into chunks
        all_chunks = []
        for doc in documents:
            chunks = self.create_document_chunks(doc)
            all_chunks.extend(chunks)
        
        # Add documents in batches to avoid memory issues
        batch_size = 100
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i + batch_size]
            
            # Prepare data for ChromaDB
            ids = [f"{collection_name}_{i + j}" for j in range(len(batch))]
            texts = [chunk['content'] for chunk in batch]
            metadatas = [chunk['metadata'] for chunk in batch]
            
            # Add to collection
            collection.add(
                ids=ids,
                documents=texts,
                metadatas=metadatas
            )
            
        logger.info(f"Added {len(all_chunks)} chunks from {len(documents)} documents to collection {collection_name}")
        return collection_name
    
    def search(self, query: str, collection_name: str, top_k: int = 5) -> List[Dict]:
        """
        Search for similar documents in the vector store.
        
        Args:
            query: Query string
            collection_name: Name of the collection to search
            top_k: Number of results to return (default: 5)
            
        Returns:
            List of matching documents with similarity scores
        """
        try:
            collection = self._get_or_create_collection(collection_name)
            
            # Perform search
            results = collection.query(
                query_texts=[query],
                n_results=top_k
            )
            
            # Format results
            formatted_results = []
            if results["documents"]:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0]
                )):
                    formatted_results.append({
                        "content": doc,
                        "metadata": metadata,
                        "score": 1.0 - distance  # Convert distance to similarity score
                    })
            
            return formatted_results
        except Exception as e:
            logger.error(f"Error searching collection {collection_name}: {str(e)}")
            return []
    
    def get_collections(self) -> List[str]:
        """Get list of all collections in the database."""
        return [col.name for col in self.client.list_collections()]
    
    def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection from the database."""
        try:
            self.client.delete_collection(collection_name)
            if collection_name in self.collections:
                del self.collections[collection_name]
            logger.info(f"Deleted collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting collection {collection_name}: {str(e)}")
            return False