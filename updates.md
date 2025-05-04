---

## 📅 Development Timeline

### 🟢 Day 1 – Setup & Scraper Module
- Decided the problem statement RAG-Website chatbot
- Initialized the FastAPI project and created `/scrape` endpoint.

### 🔵 Day 2 – Processing, Chunking & Indexing
- Built recursive web scraping logic using `requests`, `BeautifulSoup4`, and `validators`.
- Parsed website content, images, and metadata (titles, headings).
- Ensured support for multiple HTML parsers (`lxml`, `html5lib`).
- Cleaned and chunked scraped text using `LangChain`'s `RecursiveCharacterTextSplitter`.
- Embedded chunks and indexed them using `ChromaDB`.
- Stored metadata (like page source, image URLs) separately in `Qdrant`.
- Set up `.env` for secure API key management (`python-dotenv`).

### 🔴 Day 3 – Query Engine & Integration
- Implemented the `/query` endpoint to receive user questions.
- Used `LangChain` + `LlamaIndex` to fetch relevant context chunks.
- Integrated `google-generativeai` to generate answers via Gemini.
- Tested end-to-end pipeline
- Created Git Repo and pushed code to GitHub.
- Recorded Vedio
