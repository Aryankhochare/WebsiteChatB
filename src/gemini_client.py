"""
Google Gemini API client for generating responses.
Handles API authentication and prompt formatting.
"""

import os
import logging
from typing import List, Dict, Optional, Any

import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GeminiClient:
    """Client for interacting with Google's Gemini API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Gemini API client.
        
        Args:
            api_key: Google API key for Gemini (default: from environment)
        """
        # Use provided API key or get from environment
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        
        if not self.api_key:
            raise ValueError("Gemini API key not found. Set GOOGLE_API_KEY in .env file or pass it directly.")
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        
        # Set default model
        self.model_name = "gemini-1.5-pro"
        self.model = genai.GenerativeModel(self.model_name)
        
        logger.info(f"Initialized Gemini client with model: {self.model_name}")
    
    def create_context_prompt(self, retrieved_docs: List[Dict]) -> str:
        """
        Create a context prompt from retrieved documents.
        
        Args:
            retrieved_docs: List of documents from vector search
            
        Returns:
            Formatted context string
        """
        if not retrieved_docs:
            return "No relevant information found."
        
        # Format context from retrieved documents
        context_parts = []
        
        for i, doc in enumerate(retrieved_docs, 1):
            content = doc['content']
            source_url = doc['metadata'].get('source_url', 'Unknown source')
            title = doc['metadata'].get('title', 'Untitled section')
            
            context_part = f"[Document {i}] {title}\nSource: {source_url}\n\n{content}\n"
            context_parts.append(context_part)
        
        return "\n---\n".join(context_parts)
    
    async def generate_response(self, query: str, context: str) -> str:
        """
        Generate a response using Gemini API.
        
        Args:
            query: User question
            context: Context information from retrieved documents
            
        Returns:
            Generated response
        """
        try:
            # Build the system prompt with instructions
            system_prompt = """
            You are an AI assistant powered by Google Gemini, serving as a helpful and informative chatbot for a website.
            Your task is to answer questions based ONLY on the context provided below.
            If the answer cannot be found in the context, politely state that you don't have enough information rather than making up an answer.
            Always provide accurate, factual responses based solely on the context.
            Format your response in a clear, concise manner. If appropriate, use markdown formatting for readability.
            
            Remember:
            1. Only use information found in the context below
            2. If information is missing, acknowledge the limitations
            3. Do not reference that you're using "context" or "documents" in your answer
            4. Do not mention that you're an AI unless directly asked about your nature
            5. Make your response conversational and helpful
            """
            
            # Build the complete prompt
            prompt = f"""
            {system_prompt}
            
            CONTEXT:
            {context}
            
            USER QUESTION:
            {query}
            
            YOUR RESPONSE:
            """
            
            # Generate content
            response = await self.model.generate_content_async(prompt)
            
            if not response.text:
                return "I apologize, but I couldn't generate a proper response. Please try rephrasing your question."
            
            return response.text
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return f"I encountered an error while generating your response. Please try again later."

    def set_model(self, model_name: str) -> bool:
        """
        Change the Gemini model being used.
        
        Args:
            model_name: Name of the model to use
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.model_name = model_name
            self.model = genai.GenerativeModel(model_name)
            logger.info(f"Changed model to: {model_name}")
            return True
        except Exception as e:
            logger.error(f"Error setting model {model_name}: {str(e)}")
            return False