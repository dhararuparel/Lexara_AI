# LEXARA AI - RAG-Based Intelligent Knowledge Assistant

A Generative AI-powered knowledge assistant that allows users to upload documents and interact with them using natural language queries through Retrieval-Augmented Generation (RAG).

## Features

- Upload and process multiple document formats (PDF, DOCX, TXT)
- Semantic search using vector embeddings
- Context-aware responses using RAG approach
- Conversational memory
- Document summarization
- Interactive chat interface

## Tech Stack

- **Language**: Python
- **LLM**: OpenAI GPT
- **Framework**: LangChain
- **Embeddings**: OpenAI Embeddings
- **Vector Database**: FAISS
- **Document Processing**: PyPDF2, python-docx
- **Frontend**: Streamlit

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up environment variables in `.env`
4. Run the application: `streamlit run app.py`

## Project Structure

```
documind-ai/
├── app.py                 # Main Streamlit application
├── src/
│   ├── document_processor.py  # Document processing utilities
│   ├── vector_store.py        # Vector database operations
│   ├── rag_engine.py          # RAG implementation
│   └── chat_interface.py      # Chat functionality
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
└── README.md             # Project documentation
```
