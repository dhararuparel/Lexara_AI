<div align="center">

<br/>

![Lexara AI Banner](static/lexara_banner_v2.png)

<br/>

[![Live Demo](https://img.shields.io/badge/🚀%20Live%20Demo-lexara--ai.onrender.com-7C3AED?style=for-the-badge)](https://lexara-ai.onrender.com/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1.0-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-2.5%20Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Latest-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![FAISS](https://img.shields.io/badge/FAISS-Vector%20Store-FF6F00?style=for-the-badge&logo=meta&logoColor=white)](https://github.com/facebookresearch/faiss)
[![PWA](https://img.shields.io/badge/PWA-Ready-5A0FC8?style=for-the-badge&logo=pwa&logoColor=white)](https://web.dev/progressive-web-apps)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

<br/>

</div>

### 🌐 [**Try the Live Demo → lexara-ai.onrender.com**](https://lexara-ai.onrender.com/)

---

## 🌟 What is Lexara AI?

**Lexara AI** is a production-ready, full-stack intelligent knowledge assistant that turns your static documents into a **dynamic, conversational knowledge base**. Upload any document, and Lexara instantly indexes it into a FAISS vector store, enabling you to ask natural language questions and receive accurate, context-grounded answers — all powered by **Google Gemini's state-of-the-art LLMs** and a sophisticated **Retrieval-Augmented Generation (RAG)** pipeline.

Built for real-world deployment, Lexara includes enterprise features like **team workspaces**, **OAuth authentication**, **2FA security**, **real-time streaming responses**, and a full **admin analytics dashboard** — all from a single, self-contained Python application.

---

## ✨ Feature Highlights

### 🤖 AI & RAG Intelligence
- **Streaming RAG Responses** — Real-time token-by-token generation via Server-Sent Events (SSE)
- **HNSW Vector Search** — High-performance approximate nearest neighbor search with FAISS
- **Gemini 2.5 Flash** — Powered by Google's latest multimodal model
- **Multi-turn Conversation** — Chat history-aware context window (last 6 exchanges)
- **Answer Regeneration** — Re-ask any question for a fresh AI perspective
- **Document Confidence Scoring** — Know how grounded each answer is in source material
- **@Mention Scoping** — Focus a query to a single document with `@filename`

### 💬 Chat Experience
- **Chat Branching** — Fork any conversation from any historical message to explore alternate paths
- **Message Pinning** — Pin crucial AI responses for quick sidebar access
- **Public Chat Sharing** — Generate read-only shareable links for any conversation
- **Chat Export to PDF** — Download beautifully formatted conversation transcripts
- **Voice Input** — Hands-free queries via Web Speech API
- **Saved Prompts Library** — Bookmark frequently used questions as reusable templates
- **Full-text Message Search** — Search across all your conversation history

### 📂 Document Intelligence
- **Multi-format Ingestion** — PDF, DOCX, TXT, Markdown
- **Web URL Ingestion** — Index any public webpage directly into your knowledge base
- **YouTube Transcript Ingestion** — Ask questions about any YouTube video
- **PDF OCR Fallback** — `PyMuPDF` rendering with `pytesseract` OCR for scanned PDFs
- **Document Summarization** — AI-generated summaries with one click
- **Key Topic Extraction** — Automatically surface core concepts from any document
- **Auto-Suggested Questions** — AI generates starter questions for each document
- **Document Comparison** — Side-by-side AI analysis of any two documents
- **Version Control** — Track revision history across multiple uploads of the same file
- **Folder Organization** — Group documents into custom color-coded folders
- **Auto-Tagging** — AI auto-categorizes documents on upload
- **Duplicate Detection** — Smart warnings when re-uploading an existing file

### 🔐 Security & Authentication
- **Multi-method Auth** — Email/password, Google OAuth 2.0, GitHub OAuth
- **Two-Factor Authentication (TOTP)** — QR code-based 2FA via `pyotp` compatible with any authenticator app
- **Email Verification** — Signup verification via SMTP with token-secured links
- **Password Reset Flow** — Secure time-limited reset tokens delivered by email
- **HttpOnly Cookie Sessions** — Signed tokens with `SameSite=Lax` protection
- **Active Session Auditing** — View all logged-in devices and revoke any or all sessions
- **Account Self-Deletion** — GDPR-friendly full data purge on request

### 👥 Team Collaboration
- **Team Workspaces** — Shared document libraries with role-based access control
- **Invite by Email** — Send workspace invitations with accept-flow
- **Role Management** — `Owner`, `Admin`, `Editor`, `Viewer` permission tiers
- **Activity Feed** — Track what teammates have uploaded or queried
- **Workspace Document Sharing** — Scoped knowledge bases per team

### 📊 Analytics & Admin
- **Personal Usage Dashboard** — Queries per day, documents uploaded, chat activity
- **Usage Tier Limits** — Configurable per-user plan quotas for docs and queries
- **Admin Control Panel** — Full user account auditing for platform administrators
- **Message Feedback** — Thumbs up/down rating system to track AI answer quality
- **Document Coverage Analytics** — Track which pages and chunks are referenced most

### 🚀 Production Infrastructure
- **Progressive Web App (PWA)** — Installable on mobile & desktop with offline caching
- **Service Worker** — Asset caching via `sw.js` for offline-capable browsing
- **Gunicorn + Gevent** — Async WSGI server for high-concurrency production loads
- **Cloudinary Integration** — Optional cloud file storage for scalable deployments
- **Render Blueprint** — One-click deployment configuration via `render.yaml`
- **ProxyFix Middleware** — Correct HTTPS detection behind reverse proxies
- **Lazy Import Optimization** — Heavy modules deferred for fast server cold starts

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Lexara AI Architecture                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Browser / PWA Client                                                  │
│   ┌───────────────────────────────────────────────────────┐             │
│   │  HTML + Vanilla JS  │  Service Worker  │  Web Speech  │             │
│   └─────────────────────────────┬─────────────────────────┘             │
│                                 │ HTTPS / SSE Streams                   │
│   Flask Application (app.py)    ▼                                       │
│   ┌─────────────────────────────────────────────────────┐               │
│   │  Auth │ Documents │ Chats │ Workspaces │ Admin API   │               │
│   │  OAuth (Google / GitHub) │ TOTP 2FA │ SMTP Mail     │               │
│   └──────────┬────────────────────────┬────────────────┘               │
│              │                        │                                 │
│   ┌──────────▼──────────┐  ┌──────────▼──────────────────┐            │
│   │   RAG Pipeline      │  │   PostgreSQL (Supabase)      │            │
│   │  ┌───────────────┐  │  │  Users │ Chats │ Documents   │            │
│   │  │ FAISS HNSW    │  │  │  Sessions │ Workspaces       │            │
│   │  │ Vector Store  │  │  │  Prompts │ Analytics         │            │
│   │  │ (per-user)    │  │  └──────────────────────────────┘            │
│   │  └───────┬───────┘  │                                              │
│   │          │           │  ┌─────────────────────────────┐            │
│   │  ┌───────▼───────┐  │  │  Storage                     │            │
│   │  │ Google Gemini │  │  │  Local Disk / Cloudinary CDN  │            │
│   │  │ Embeddings &  │  │  └─────────────────────────────┘            │
│   │  │ Generation    │  │                                              │
│   │  └───────────────┘  │                                              │
│   └─────────────────────┘                                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| **Backend Framework** | Flask | `3.1.0` |
| **WSGI Server** | Gunicorn + Gevent | `23.0.0` / `24.11.1` |
| **LLM & Embeddings** | Google Gemini (`gemini-2.5-flash-lite`) | `google-genai 1.14.0` |
| **Vector Database** | FAISS (HNSW Index, per-user) | `faiss-cpu 1.12.0` |
| **Relational Database** | PostgreSQL (via Supabase) | `psycopg2-binary 2.9.10` |
| **PDF Processing** | PyMuPDF + pytesseract OCR | `1.25.5` |
| **DOCX Processing** | python-docx | `1.1.2` |
| **OAuth** | Authlib | `1.4.1` |
| **2FA / TOTP** | pyotp + qrcode | `2.9.0` / `8.0` |
| **Email** | Flask-Mail (SMTP) | `0.10.0` |
| **Cloud Storage** | Cloudinary | `1.42.1` |
| **PDF Export** | fpdf2 | `2.8.3` |
| **YouTube Ingestion** | youtube-transcript-api | `1.2.4` |
| **Numerical Computing** | NumPy | `2.2.6` |
| **Frontend** | Vanilla HTML + CSS + JavaScript | — |
| **PWA** | Service Worker + Web Manifest | — |

---

## 📂 Project Structure

```
Lexara-AI/
│
├── 📄 app.py                    # Core Flask application — all routes, API endpoints,
│                                # OAuth flows, streaming SSE, and middleware
│
├── 🔐 auth.py                   # JWT token generation, password hashing (Werkzeug),
│                                # and @require_auth decorator
│
├── 🗄️  database.py              # Full PostgreSQL data layer — connection pooling,
│                                # table schemas, and all CRUD operations
│
├── 🧠 rag_pipeline.py           # Core RAG engine — FAISS HNSW indexing, Gemini
│                                # embedding retrieval, streaming generation,
│                                # document comparison, URL & YouTube ingestion
│
├── 📑 pdf_processor.py          # Document parsing — PDF layout analysis, text
│                                # extraction, OCR fallback, chunk generation
│
├── 🔢 embeddings.py             # Google GenAI embedding wrapper with
│                                # batch processing and normalization
│
├── 📧 mailer.py                 # SMTP email service — verification emails,
│                                # password resets, workspace invitations
│
├── 💾 storage.py                # File storage abstraction — local disk and
│                                # Cloudinary cloud storage with unified API
│
├── 📁 templates/
│   ├── index.html               # Main PWA dashboard and workspace UI
│   ├── login.html               # Auth page — signup, login, OAuth buttons
│   ├── admin.html               # Administrator analytics and user management
│   ├── reset_password.html      # Password reset form
│   ├── shared_chat.html         # Public read-only chat viewer
│   └── workspace_invite.html    # Team workspace invitation acceptance page
│
├── 📁 static/
│   ├── css/
│   │   ├── style.css            # Main dashboard styles
│   │   └── login.css            # Authentication page styles
│   ├── js/
│   │   ├── app.js               # Frontend AJAX/fetch client — full dashboard logic
│   │   └── login.js             # Client-side auth validation and flow
│   ├── manifest.json            # PWA app manifest (name, icons, display mode)
│   └── sw.js                    # Service Worker for offline asset caching
│
├── 📁 vector_store/             # FAISS index files (per-user, gitignored)
├── 📁 uploads/                  # Temporary file uploads (gitignored)
│
├── ⚙️  render.yaml              # Render.com deployment blueprint
├── 🚀 Procfile                  # Gunicorn startup command for PaaS
├── 📦 requirements.txt          # Python production dependencies
├── 🔒 .env.example              # Environment variable template (safe to commit)
└── 🔒 .gitignore                # Ignores .env, uploads/, vector_store/, __pycache__/
```

---

## ⚙️ Environment Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```env
# ── Core ────────────────────────────────────────────────────────────
GEMINI_API_KEY=your_google_gemini_api_key_here
SECRET_KEY=your_very_long_random_secret_key_here

# ── Database (PostgreSQL) ────────────────────────────────────────────
# Supabase connection string recommended for production
DATABASE_URL=postgresql://user:password@host:port/dbname

# ── Google OAuth ─────────────────────────────────────────────────────
# https://console.cloud.google.com/ → Credentials → OAuth 2.0 Client IDs
GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret

# ── GitHub OAuth ─────────────────────────────────────────────────────
# https://github.com/settings/developers → OAuth Apps
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret

# ── Email / SMTP ─────────────────────────────────────────────────────
# For Gmail: enable 2FA → App Passwords → generate 16-char password
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your@gmail.com
MAIL_PASSWORD=your_app_specific_password
MAIL_FROM=noreply@yourdomain.com

# ── Cloud Storage (Optional) ──────────────────────────────────────────
# Set USE_CLOUDINARY=true for production; false uses local disk storage
USE_CLOUDINARY=false
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

> **⚠️ Security Notice:** Never commit your `.env` file. It contains sensitive secrets. The `.gitignore` already excludes it. Only commit `.env.example` with placeholder values.

---

## 💻 Local Development Setup

### Prerequisites

- Python **3.11+**
- PostgreSQL database (local instance or [Supabase](https://supabase.com) free tier)
- Google Gemini API key ([get one here](https://ai.google.dev))
- *(Optional)* Google & GitHub OAuth app credentials

### Step-by-Step

**1. Clone the repository**
```bash
git clone https://github.com/dhararuparel/Lexara_AI.git
cd Lexara_AI
```

**2. Create and activate a virtual environment**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

**3. Install all dependencies**
```bash
pip install -r requirements.txt
```

**4. Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys, database URL, and SMTP credentials
```

**5. Initialize the database**

Database tables are created automatically on first run via `init_db()`. Ensure your `DATABASE_URL` points to a running PostgreSQL instance.

**6. Run the development server**
```bash
python app.py
```

Open your browser and navigate to **http://127.0.0.1:5000**

> **💡 Tip:** For production-like local testing, run Gunicorn directly:
> ```bash
> gunicorn app:app --workers 1 --worker-class gevent --worker-connections 10 --timeout 300
> ```

---

## ☁️ Production Deployment (Render)

Lexara includes a ready-to-use **`render.yaml`** blueprint for one-click deployment on [Render.com](https://render.com).

### Quick Deploy Steps

1. Fork this repository to your GitHub account
2. Go to [render.com](https://render.com) → **New** → **Blueprint**
3. Connect your forked repository
4. Render will automatically detect `render.yaml` and create the web service
5. Set all environment variables in the Render dashboard (they are marked `sync: false` in the blueprint for security)
6. Deploy! 🚀

### Required Render Environment Variables

Set these in your Render service dashboard under **Environment**:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Your PostgreSQL connection string |
| `GEMINI_API_KEY` | Google Gemini API key |
| `SECRET_KEY` | Long random secret for session signing |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `GITHUB_CLIENT_ID` | GitHub OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth app client secret |
| `MAIL_USERNAME` | Gmail address for SMTP |
| `MAIL_PASSWORD` | Gmail app-specific password *(not your Gmail password)* |
| `MAIL_FROM` | Sender email address |
| `CLOUDINARY_CLOUD_NAME` | *(if `USE_CLOUDINARY=true`)* |
| `CLOUDINARY_API_KEY` | *(if `USE_CLOUDINARY=true`)* |
| `CLOUDINARY_API_SECRET` | *(if `USE_CLOUDINARY=true`)* |

> **⚠️ Important:** When deploying to Render, set `USE_CLOUDINARY=true` and configure Cloudinary credentials. Local disk storage is **not persistent** on Render's ephemeral filesystem.

---

## 🔑 OAuth & SMTP Setup

### Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth 2.0 Client ID** → Application type: **Web application**
3. Add Authorized Redirect URIs:
   - `http://127.0.0.1:5000/auth/google/callback` *(local)*
   - `https://your-domain.com/auth/google/callback` *(production)*
4. Copy **Client ID** and **Client Secret** → add to `.env`

### GitHub OAuth

1. Go to **GitHub** → Settings → **Developer settings** → **OAuth Apps** → **New OAuth App**
2. Set **Authorization callback URL**:
   - `http://127.0.0.1:5000/auth/github/callback` *(local)*
   - `https://your-domain.com/auth/github/callback` *(production)*
3. Copy **Client ID** and **Client Secret** → add to `.env`

### Gmail App Password (SMTP)

1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** if not already active
3. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
4. Create a password for **Mail** → Copy the 16-character password
5. Use this as `MAIL_PASSWORD` in `.env` *(not your regular Gmail password)*

---

## 🧪 API Reference

<details>
<summary><b>🔐 Authentication</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/signup` | Register a new account |
| `POST` | `/api/auth/login` | Login (supports TOTP 2FA code) |
| `POST` | `/api/auth/logout` | Clear session cookie |
| `GET` | `/api/auth/me` | Get current authenticated user |
| `POST` | `/api/auth/update` | Update name / change password |
| `POST` | `/api/auth/delete-account` | Permanently delete account & data |
| `GET` | `/api/auth/verify-email` | Verify email via link token |
| `POST` | `/api/auth/resend-verification` | Resend verification email |
| `POST` | `/api/auth/forgot-password` | Send password reset email |
| `POST` | `/api/auth/reset-password` | Reset password via token |
| `POST` | `/api/auth/2fa/setup` | Generate 2FA secret + QR code |
| `POST` | `/api/auth/2fa/verify` | Verify and enable 2FA |
| `POST` | `/api/auth/2fa/disable` | Disable 2FA |
| `GET` | `/api/auth/sessions` | List all active sessions |
| `DELETE` | `/api/auth/sessions/:id` | Revoke a specific session |
| `POST` | `/api/auth/sessions/revoke-all` | Revoke all other sessions |
| `GET` | `/auth/google` | Initiate Google OAuth flow |
| `GET` | `/auth/github` | Initiate GitHub OAuth flow |

</details>

<details>
<summary><b>📂 Documents</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/documents` | List all user documents |
| `POST` | `/api/documents/upload` | Upload one or more files |
| `DELETE` | `/api/documents/:id` | Delete a document + vectors |
| `POST` | `/api/documents/:id/summarize` | AI-generate document summary |
| `GET` | `/api/documents/:id/questions` | Get AI-suggested questions |
| `GET` | `/api/documents/:id/topics` | Extract key topics |
| `GET` | `/api/documents/:id/versions` | List document version history |
| `POST` | `/api/documents/compare` | Compare two documents side-by-side |
| `GET` | `/api/documents/search` | Full-text search across documents |
| `GET` | `/api/documents/:id/preview` | Serve file for inline preview |
| `POST` | `/api/documents/:id/tags` | Add a tag to a document |
| `GET` | `/api/documents/:id/tags` | Get all tags for a document |
| `POST` | `/api/documents/:id/move` | Move document to a folder |
| `POST` | `/api/ingest/url` | Index a web URL |
| `POST` | `/api/ingest/youtube` | Index a YouTube video transcript |

</details>

<details>
<summary><b>💬 Chats & Messaging</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/chats` | List all chats |
| `POST` | `/api/chats` | Create a new chat |
| `DELETE` | `/api/chats/:id` | Delete a chat |
| `GET` | `/api/chats/:id/messages` | Get messages in a chat |
| `POST` | `/api/chats/:id/ask` | Ask a question (SSE streaming) |
| `POST` | `/api/chats/:id/regenerate` | Regenerate last AI response |
| `POST` | `/api/chats/:id/branch` | Fork a conversation from a message |
| `GET` | `/api/chats/:id/export` | Export chat as PDF |
| `POST` | `/api/chats/:id/share` | Create a public share link |
| `GET` | `/api/chats/:id/share` | Get existing share token |
| `GET` | `/share/:token` | View publicly shared chat (no auth) |
| `POST` | `/api/messages/:id/feedback` | Rate an AI response (±1) |
| `POST` | `/api/messages/:id/pin` | Pin a message |
| `DELETE` | `/api/messages/:id/unpin` | Unpin a message |
| `GET` | `/api/search` | Search across all message history |

</details>

<details>
<summary><b>📁 Folders</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/folders` | List all folders |
| `POST` | `/api/folders` | Create a new folder (with custom color) |
| `DELETE` | `/api/folders/:id` | Delete a folder |

</details>

<details>
<summary><b>👥 Workspaces & Collaboration</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/workspaces` | List all user workspaces |
| `POST` | `/api/workspaces` | Create a new workspace |
| `PATCH` | `/api/workspaces/:id` | Update workspace name/description |
| `DELETE` | `/api/workspaces/:id` | Delete a workspace |
| `GET` | `/api/workspaces/:id/members` | List workspace members |
| `POST` | `/api/workspaces/:id/members` | Invite a member by email |
| `PATCH` | `/api/workspaces/:id/members/:mid` | Update member role |
| `DELETE` | `/api/workspaces/:id/members/:mid` | Remove a member |
| `GET` | `/api/workspaces/:id/documents` | List workspace documents |
| `GET` | `/api/workspace-invite/info` | Get invite details by token |
| `POST` | `/api/workspace-invite/accept` | Accept a workspace invitation |

</details>

<details>
<summary><b>📊 Analytics & Misc</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/analytics` | Get personal usage analytics |
| `GET` | `/api/suggest` | Get AI-generated suggested questions |
| `GET` | `/api/prompts` | List saved prompt templates |
| `POST` | `/api/prompts` | Save a new prompt template |
| `DELETE` | `/api/prompts/:id` | Delete a saved prompt |
| `POST` | `/api/clear-all` | Clear all documents and vectors |
| `POST` | `/api/purge-stale-vectors` | Remove orphaned FAISS vectors |

</details>

---

## 🛡️ Security Design

| Layer | Implementation |
|-------|---------------|
| **Session Tokens** | `HttpOnly` cookies — tokens never exposed to JavaScript |
| **CSRF Protection** | `SameSite=Lax` cookie attribute |
| **Password Hashing** | Werkzeug PBKDF2 with salt |
| **Two-Factor Auth** | RFC 6238 TOTP (compatible with Google Authenticator, Authy, etc.) |
| **Email Verification** | Cryptographically random URL-safe tokens via `secrets.token_urlsafe` |
| **Password Reset** | 1-hour expiry, single-use tokens |
| **HTTPS Awareness** | `ProxyFix` middleware for correct scheme detection behind proxies |
| **Email Enumeration** | Forgot-password endpoint always returns success — never reveals if email exists |
| **Data Cascade** | All user data (documents, chats, sessions) purged on account deletion via DB cascade |
| **OAuth Secrets** | All client secrets loaded from environment variables — never hardcoded |

---

## 🗺️ Roadmap

- [ ] **Stripe Billing** — Free / Pro / Enterprise subscription tiers with usage limits
- [ ] **REST API Keys** — Let external clients query Lexara via API key
- [ ] **Slack Bot Integration** — Ask Lexara directly from any Slack channel
- [ ] **Google Drive / Dropbox Sync** — Import and sync documents from cloud storage
- [ ] **Chrome Extension** — Clip any webpage directly into your knowledge base
- [ ] **Notion Page Ingestion** — Index Notion pages via URL paste
- [ ] **Document Expiry** — Auto-remove documents after a configurable date
- [ ] **White-label Mode** — Custom branding, domain, and logo for agencies
- [ ] **Zapier / Webhook Triggers** — Automate workflows on upload or query events
- [ ] **Multi-language UI** — Auto-detect and respond in the user's browser language
- [ ] **Answer Quality Heatmaps** — Aggregate thumbs up/down analytics over time
- [ ] **Microsoft OAuth** — Sign in with Microsoft / Azure Active Directory

---

## 🤝 Contributing

Contributions are warmly welcomed! Here's how to get started:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/amazing-feature`
3. **Commit** your changes: `git commit -m 'feat: add amazing feature'`
4. **Push** to your branch: `git push origin feature/amazing-feature`
5. **Open** a Pull Request

Please ensure your code follows existing patterns and includes appropriate comments.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Built with ❤️ by [Dhara Ruparel](https://github.com/dhararuparel)**

*Lexara AI — Making your documents talk back*

⭐ **Star this repo** if you find it useful!

</div>
