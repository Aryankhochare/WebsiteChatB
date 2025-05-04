"""
RAG Engine that combines scraping, vector storage, metadata storage, and LLM generation.
Provides a unified interface for the RAG pipeline with enhanced image handling.
"""

import os
import logging
from typing import List, Dict, Optional, Any, Tuple, Union
from urllib.parse import urlparse
import time

from .scraper import WebScraper
from .vectorstore import VectorStore
from .qdrant_store import QdrantStore
from .gemini_client import GeminiClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RAGEngine:
    """
    Retrieval-Augmented Generation engine for website content.
    Combines web scraping, vector storage, metadata storage, and LLM generation.
    """
    
    def __init__(self, 
                 max_depth: int = 2, 
                 max_pages: int = 50,
                 vector_persist_directory: str = "./chroma_db",
                 metadata_persist_directory: str = "./qdrant_db",
                 gemini_api_key: Optional[str] = None,
                 base_url: str = "http://localhost:8000"):
        """
        Initialize the RAG engine.
        
        Args:
            max_depth: Maximum scraping depth (default: 2)
            max_pages: Maximum pages to scrape (default: 50)
            vector_persist_directory: Directory for vector store (default: "./chroma_db")
            metadata_persist_directory: Directory for metadata store (default: "./qdrant_db")
            gemini_api_key: API key for Gemini (default: from environment)
            base_url: Base URL for application (default: "http://localhost:8000")
        """
        # Initialize dependencies
        self.scraper = WebScraper(max_depth=max_depth, max_pages=max_pages)
        self.vector_store = VectorStore(persist_directory=vector_persist_directory)
        self.metadata_store = QdrantStore(path=metadata_persist_directory)
        self.gemini_client = GeminiClient(api_key=gemini_api_key)
        
        # Configuration
        self.config = {
            "base_url": base_url
        }
        
        # Keep track of indexed websites
        self.indexed_websites = {}
        
        logger.info("Initialized RAG Engine with ChromaDB and Qdrant storage")
    
    def _get_domain_name(self, url: str) -> str:
        """Extract domain name from URL."""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    
    async def index_website(self, url: str) -> Tuple[str, int]:
        """
        Index a website by scraping content and storing in vector DB and metadata store.
        
        Args:
            url: URL to index
            
        Returns:
            Tuple of (collection_name, document_count)
        """
        start_time = time.time()
        logger.info(f"Starting indexing of website: {url}")
        
        # Scrape the website
        scraped_documents = self.scraper.scrape_url(url)
        
        if not scraped_documents:
            logger.warning(f"No content found at {url}")
            return None, 0
        
        # Generate a collection name
        domain_name = self._get_domain_name(url)
        collection_name = f"{domain_name}_{int(start_time)}"
        
        # Add documents to vector store for text search
        self.vector_store.add_documents(scraped_documents, collection_name)
        
        # Add metadata to Qdrant store for rich media and structured data
        self.metadata_store.add_metadata(collection_name, scraped_documents)
        
        # Record website metadata
        self.indexed_websites[collection_name] = {
            'url': url,
            'document_count': len(scraped_documents),
            'indexed_at': start_time,
            'domain': domain_name,
            'image_count': sum(len(doc.get('images', [])) for doc in scraped_documents)
        }
        
        elapsed_time = time.time() - start_time
        logger.info(f"Finished indexing {url}. Indexed {len(scraped_documents)} documents in {elapsed_time:.2f} seconds")
        
        return collection_name, len(scraped_documents)
    
    async def query(self, question: str, collection_name: str, top_k: int = 5) -> str:
        """
        Query the RAG system with a question.
        
        Args:
            question: User question
            collection_name: Vector store collection to query
            top_k: Number of documents to retrieve (default: 5)
            
        Returns:
            Generated answer
        """
        return await self.handle_query(question, collection_name, top_k)
    
    async def handle_query(self, question: str, collection_name: str, top_k: int = 5) -> str:
        """
        Process a query and generate a response.
        
        Args:
            question: User's question or query
            collection_name: Name of the collection to query
            top_k: Number of documents to retrieve
            
        Returns:
            Response text
        """
        start_time = time.time()
        logger.info(f"Processing query: '{question}' on collection '{collection_name}'")
        
        # Check if this is an image-related query
        image_keywords = ["image", "picture", "photo", "show me", "display", "visual"]
        is_image_query = any(keyword in question.lower() for keyword in image_keywords)
        
        if is_image_query:
            return await self._handle_image_query(question, collection_name)
        
        # Regular text query - retrieve relevant documents
        retrieved_docs = self.vector_store.search(question, collection_name, top_k)
        
        if not retrieved_docs:
            return "I couldn't find any relevant information to answer your question. Please try asking something related to the website content."
        
        # Create context from retrieved documents
        context = self.gemini_client.create_context_prompt(retrieved_docs)
        
        # Generate response
        response = await self.gemini_client.generate_response(question, context)
        
        elapsed_time = time.time() - start_time
        logger.info(f"Query processed in {elapsed_time:.2f} seconds")
        
        return response
    
    async def _handle_image_query(self, question: str, collection_name: str) -> str:
        """
        Handle queries specifically asking for images.
        
        Args:
            question: User's question or query
            collection_name: Name of the collection to query
            
        Returns:
            Response with images
        """
        # Get base URL from configuration
        base_url = self.config.get("base_url", "http://localhost:8000")
        
        # Get images from the metadata store
        images = self.metadata_store.get_images(collection_name)
        
        # Generate a response with the images
        return self._generate_image_response(collection_name, images, base_url)
    
    def _format_image_display_for_response(self, collection_name, images, base_url=""):
        """
        Format images for display in the chat response.
        
        Args:
            collection_name: Name of the collection
            images: List of image information from the Qdrant store
            base_url: Base URL for the application (optional)
            
        Returns:
            Formatted HTML for displaying images in the chat
        """
        # If no images, return a message
        if not images:
            return f"No images found in collection '{collection_name}'."
        
        # Limit to the first 6 images for the chat display
        display_images = images[:6]
        
        # Create HTML for image display
        html = f"""
        <div style="margin-top: 20px; margin-bottom: 20px;">
            <h3 style="margin-bottom: 10px;">Images from {collection_name} ({len(images)} found)</h3>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
        """
        
        # Add each image
        for img in display_images:
            img_url = img.get("url", "")
            img_alt = img.get("alt", "Image")
            page_url = img.get("page_url", "")
            dimensions = img.get("dimensions", "unknown")
            
            html += f"""
            <div style="border: 1px solid #ddd; border-radius: 8px; overflow: hidden;">
                <div style="height: 120px; overflow: hidden; background-color: #f0f0f0; position: relative;">
                    <img src="{img_url}" alt="{img_alt}" style="width: 100%; height: 100%; object-fit: cover;">
                </div>
                <div style="padding: 8px; font-size: 12px;">
                    <p style="margin: 0; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{img_alt}</p>
                    <p style="margin: 0; color: #777; font-size: 10px;">{dimensions}</p>
                    <div style="display: flex; justify-content: space-between; margin-top: 5px;">
                        <a href="{img_url}" target="_blank" style="text-decoration: none; color: #0066cc; font-size: 11px;">Download</a>
                        <a href="{page_url}" target="_blank" style="text-decoration: none; color: #666; font-size: 11px;">Source</a>
                    </div>
                </div>
            </div>
            """
        
        html += """
            </div>
        """
        
        # Add link to view all images if there are more than displayed
        if len(images) > len(display_images):
            html += f"""
            <div style="margin-top: 10px; text-align: center;">
                <a href="{base_url}/images/{collection_name}" target="_blank" style="text-decoration: none; color: #0066cc;">
                    View all {len(images)} images
                </a>
            </div>
            """
        
        html += "</div>"
        
        return html
    
    def _generate_image_response(self, collection_name, images, base_url=""):
        """
        Generate a complete response about images for the chatbot.
        
        Args:
            collection_name: Name of the collection
            images: List of image information from the Qdrant store
            base_url: Base URL for the application (optional)
            
        Returns:
            Complete response with image display HTML
        """
        if not images:
            return f"I couldn't find any images in the collection '{collection_name}'."
        
        # Create a summary of the images
        image_types = {}
        for img in images:
            alt = img.get("alt", "").lower()
            for keyword in ["logo", "banner", "product", "icon", "photo", "thumbnail", "chart", "graph"]:
                if keyword in alt:
                    image_types[keyword] = image_types.get(keyword, 0) + 1
        
        # Create the response
        response = f"I found {len(images)} images in the collection '{collection_name}'."
        
        if image_types:
            response += " These include "
            type_descriptions = [f"{count} {img_type}s" for img_type, count in image_types.items()]
            response += ", ".join(type_descriptions) + "."
        
        # Add the formatted HTML display
        response += "\n\n" + self._format_image_display_for_response(collection_name, images, base_url)
        
        response += f"\n\nYou can view all images at {base_url}/images/{collection_name} or download them directly from the preview above."
        
        return response
    
    def get_images(self, collection_name: str, limit: int = 20) -> List[Dict]:
        """
        Get image information from a collection.
        
        Args:
            collection_name: Name of the collection
            limit: Maximum number of images to return
            
        Returns:
            List of image information dictionaries
        """
        return self.metadata_store.get_images(collection_name, limit)
    
    def get_indexed_websites(self) -> Dict:
        """Get information about indexed websites."""
        return self.indexed_websites
    
    def get_collections(self) -> List[str]:
        """Get all available collections from both stores."""
        vector_collections = self.vector_store.get_collections()
        metadata_collections = self.metadata_store.get_collections()
        
        # Return unique collection names from both stores
        return list(set(vector_collections + metadata_collections))
    
    def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection and its data from both stores."""
        vector_result = self.vector_store.delete_collection(collection_name)
        metadata_result = self.metadata_store.delete_collection(collection_name)
        
        if collection_name in self.indexed_websites:
            del self.indexed_websites[collection_name]
            
        return vector_result and metadata_result
    
    # Add this method to your RAGEngine class in src/rag_engine.py

def get_collection_size(self, collection_name: str) -> int:
    """
    Get the number of documents in a collection.
    
    Args:
        collection_name: Name of the collection
        
    Returns:
        int: Number of documents in the collection or 0 if not found
    """
    try:
        # First try to get from metadata if available
        indexed_websites = self.get_indexed_websites()
        if collection_name in indexed_websites:
            return indexed_websites[collection_name].get("document_count", 0)
            
        # If not in metadata, try to get directly from the vector store
        # This approach depends on your specific vector store implementation
        if hasattr(self, 'vector_store') and self.vector_store:
            # If using ChromaDB
            try:
                # For ChromaDB
                collection = self.vector_store.get_collection(collection_name)
                if collection:
                    return collection.count()
            except Exception as e:
                logger.warning(f"Could not get collection size from ChromaDB: {str(e)}")
                
        # If using Qdrant
        try:
            if hasattr(self, 'metadata_store') and self.metadata_store:
                count = self.metadata_store.get_document_count(collection_name)
                if count > 0:
                    return count
        except Exception as e:
            logger.warning(f"Could not get collection size from Qdrant: {str(e)}")
            
        # If we couldn't get the count, check if collection directory exists
        # and estimate from files (this is a fallback approach)
        import os
        if hasattr(self, 'vector_store') and hasattr(self.vector_store, 'persist_directory'):
            vector_db_path = os.path.join(self.vector_store.persist_directory, collection_name)
            if os.path.exists(vector_db_path) and os.path.isdir(vector_db_path):
                # Collection exists, but we can't get exact count
                # Return 1 as a placeholder to indicate it's not empty
                return 1
            
        return 0
    except Exception as e:
        logger.error(f"Error getting collection size: {str(e)}")
        return 0