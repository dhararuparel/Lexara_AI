# Lexara AI - Enterprise RAG-Based Intelligent Knowledge Assistant

Lexara AI is a production-ready, Generative AI-powered knowledge assistant and document intelligence platform. It allows users to upload documents (PDF, DOCX, TXT, MD), index them into a FAISS vector store, and interact with them in real-time using Retrieval-Augmented Generation (RAG) powered by Google's Gemini models.

---

## 🚀 Features

### 💬 Chat & AI Interaction
- **Advanced RAG**: Context-aware retrieval with vector store grounding and document page/chunk source attribution.
- **Chat Branching**: Fork conversation threads from any historic message to explore alternate search prompts.
- **Message Pinning**: Pin crucial AI answers for quick access in the chat sidebar.
- **Public Chat Sharing**: Generate unique, read-only public sharing links for any conversation.
- **Speech Integration**: Voice input (Web Speech API) for hands-free inquiries.

### 📂 Intelligent Document Management
- **Drag-and-Drop Uploader**: Direct upload processing with real-time feedback.
- **Supported Formats**: `.pdf`, `.docx`, `.txt`, `.md`.
- **Text Extraction & OCR**: Uses `PyMuPDF` for PDF rendering, text extraction, and fallbacks.
- **Folder Organization**: Group documents into customizable folders with custom colors.
- **Version Control**: Manage multiple versions of the same document, track revision histories, and compare differences.
- **Auto-Tagging**: AI automatically categorizes uploaded files.

### 🔐 Security & User Auth
- **Multi-method Authentication**: Sign up/in via email credentials, **Google OAuth**, or **GitHub OAuth**.
- **Session Security**: Signed session tokens stored in secure, `HttpOnly` cookies with `SameSite=Lax` parameters.
- **Active Session Auditing**: Review and revoke active devices/browsers logged into your account.
- **Email Verification & Password Reset**: SMTP support for verifying signup emails and requesting password reset tokens.

### 📊 Admin & Analytics
- **Usage Metrics Dashboard**: High-level dashboard showing total queries today, active sessions, and documents uploaded.
- **Admin panel**: Clean control center for user account auditing.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.x, Flask (PWA configured with Service Worker)
- **Web Server**: Gunicorn (configured with `gevent` workers for concurrency)
- **LLM**: Google Gemini API via the official `google-genai` SDK
- **Embeddings**: Google Gemini Embedding API
- **Vector Database**: FAISS (local index files synced with document updates)
- **Database**: PostgreSQL (connection pool wrapper utilizing `psycopg2`)
- **Storage**: Local Disk Storage (or cloud sync using `Cloudinary`)
- **Email Delivery**: Flask-Mail (via SMTP)

---

## 📂 Project Structure

```
Lexara-AI/
├── app.py                 # Main Flask server (Routing, API, & controller endpoints)
├── auth.py                # Session authentication helpers, password hashing & decorators
├── database.py            # PostgreSQL database layer, connection pooling, and tables schemas
├── embeddings.py          # Google GenAI embedding generator helper
├── pdf_processor.py       # Document parsing, layout analysis, & structural metadata extractors
├── rag_pipeline.py        # FAISS vector store indexing and query retrieval RAG pipeline
├── mailer.py              # SMTP configurations for signups and password recovery
├── storage.py             # File storage management (Local Disk & Cloudinary integration)
├── templates/             # Server-side HTML templates
│   ├── index.html         # Main dashboard and workspace app
│   ├── login.html         # Sign up, Sign in, and OAuth entrance page
│   ├── admin.html         # Administrator user metrics dashboard
│   ├── reset_password.html # Password reset form
│   ├── shared_chat.html   # Public shared chat viewer
│   └── workspace_invite.html # Invitation screen
├── static/                # Static assets (icons, CSS, JS, manifest)
│   ├── css/
│   │   ├── style.css      # Custom dashboard styles
│   │   └── login.css      # Login styles
│   ├── js/
│   │   ├── app.js         # Core AJAX/fetch client dashboard implementation
│   │   └── login.js       # Auth validation scripts
│   ├── manifest.json      # PWA application configurations
│   └── sw.js              # Service Worker for offline asset caching
├── render.yaml            # Render blueprint blueprint deployment configurations
├── Procfile               # Deployment startup instructions (WSGI binding)
└── requirements.txt       # Production packages list
```

---

## ⚙️ Environment Configuration

Create a `.env` file in the root directory:

```env
# Core API Keys
GEMINI_API_KEY=your_google_gemini_api_key
SECRET_KEY=your_flask_session_secret_key

# Database Setup
DATABASE_URL=postgresql://user:password@host:port/dbname

# OAuth Settings (Google)
GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret

# OAuth Settings (GitHub)
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret

# Mail server setup (e.g. Gmail SMTP)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_specific_password
MAIL_FROM=your_email@gmail.com

# Cloud Storage (Optional)
USE_CLOUDINARY=false
CLOUDINARY_CLOUD_NAME=your_cloudinary_cloud_name
CLOUDINARY_API_KEY=your_cloudinary_api_key
CLOUDINARY_API_SECRET=your_cloudinary_api_secret
```

---

## 💻 Local Setup & Execution

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/dhararuparel/Lexara_AI.git
   cd Lexara_AI
   ```

2. **Set up a Virtual Environment**:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Verify Database Configuration**:
   Ensure your local or remote PostgreSQL database instance is running and correct `DATABASE_URL` is set in your `.env`.

5. **Run the Server**:
   ```bash
   python app.py
   ```
   Open your browser and navigate to `http://127.0.0.1:5000`.
