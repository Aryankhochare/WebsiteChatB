# 🤖 RAG-Powered Website Chatbot

A Retrieval-Augmented Generation (RAG) chatbot that can **scrape any website recursively**, process and store the data using **LangChain, ChromaDB, and Qdrant**, and answer questions based on real-time web content using **Gemini LLM**.

---

## 🚀 Features

- 🔍 **Recursive Web Scraping** with BeautifulSoup
- ✂️ **Content Chunking & Cleaning** via LangChain
- 📦 **Vector Embedding Storage** using ChromaDB
- 🧠 **Metadata Management** with Qdrant
- 🤖 **LLM-based Query Answering** using Gemini (Google Generative AI)
- ⚡ FastAPI-based Modular API
- 🖼️ Heading and image extraction support
- 🔧 Swagger UI for easy testing

---

## ⚙️ Setup Instructions
1. Clone the Repository
2. Intall Dependencies
   2.1 pip install -r requirements.txt
3. Add your environment variables
4. Add your environment variables in .env
   4.1 GOOGLE_API_KEY=your_gemini_api_key
   4.2 .env.sample is provided

## 🛠️ Tech Stack

| Component       | Library                |
|----------------|------------------------|
| Web Framework   | FastAPI + Uvicorn      |
| Scraping        | BeautifulSoup4, Requests |
| LLM             | google-generativeai    |
| RAG Framework   | LangChain              |
| Vector DB       | ChromaDB               |
| Metadata Store  | Qdrant                 |
| Async Support   | aiohttp, httpx         |
| Environment     | python-dotenv          |
| Validation      | pydantic, validators   |
| HTML Parsing    | lxml, html5lib         |


---

## 📁 Folder Structure

├── .env # Environment variables (API keys, etc.)
├── .gitignore
├── app.log # Optional log file
├── app.py # Alternate FastAPI app file (if used)
├── main.py # Main FastAPI app entry point
├── requirements.txt # Project dependencies

├── chroma_db/ # ChromaDB vector storage
│ └── chroma.sqlite3

├── qdrant_db/ # Qdrant metadata store
│ ├── .lock
│ ├── meta.json
│ └── collection/ # Vector metadata collections

├── src/ # Core logic modules
│ ├── gemini_client.py # Gemini API integration
│ ├── qdrant_store.py # Qdrant indexing and retrieval
│ ├── rag_engine.py # RAG query pipeline
│ ├── scraper.py # Recursive web scraper
│ ├── vectorstore.py # ChromaDB vector store wrapper
│ ├── init.py
│ └── pycache/

├── static/ # Static frontend assets (optional)
│ ├── css/
│ │ └── style.css
│ └── js/
│ └── main.js

│
├───templates
│       images.html
│       index.html
│
└───__pycache__

