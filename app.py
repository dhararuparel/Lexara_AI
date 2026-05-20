"""
Lexara AI — Production Flask Backend
"""

import os
import json

# ── Suppress TensorFlow / oneDNN noise before any imports ──────────
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")   # suppress C++ TF logs
os.environ.setdefault("ABSL_MIN_LOG_LEVEL", "3")      # suppress absl logs
import logging
logging.getLogger("tensorflow").setLevel(logging.ERROR)
logging.getLogger("absl").setLevel(logging.ERROR)
# Suppress the tf_keras deprecation warning
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*sparse_softmax_cross_entropy.*")
from flask import Flask, request, jsonify, render_template, Response, stream_with_context, make_response, redirect, session
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth

from database import (
    init_db, create_user, get_user_by_email,
    add_document, get_user_documents, delete_document, get_document_stats,
    create_chat, get_user_chats, delete_chat, update_chat_title,
    add_message, get_chat_messages, get_analytics
)
from auth import hash_password, check_password, generate_token, require_auth
from pdf_processor import process_document
from rag_pipeline import RAGPipeline
from mailer import init_mail, send_verification_email, send_reset_email

from storage import save_file, get_file_path, delete_file, get_file_size

load_dotenv()
init_db()

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
app.secret_key = os.getenv("SECRET_KEY", "Lexara-secret")

# Fix datetime serialization for jsonify
import datetime
class CustomJSONProvider(app.json_provider_class):
    def default(self, o):
        if isinstance(o, (datetime.datetime, datetime.date)):
            return o.isoformat()
        return super().default(o)
app.json_provider_class = CustomJSONProvider
app.json = CustomJSONProvider(app)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
init_mail(app)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
rag = RAGPipeline(gemini_api_key=GEMINI_API_KEY)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

# ── OAuth setup ────────────────────────────────────────────────────
oauth = OAuth(app)

oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

oauth.register(
    name="github",
    client_id=os.getenv("GITHUB_CLIENT_ID"),
    client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "user:email"},
)


def allowed_file(filename):
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS


# ── Pages ──────────────────────────────────────────────────────────

@app.route("/")
def index():
    from flask import redirect
    token = request.cookies.get("token")
    if not token:
        return redirect("/login")
    from auth import verify_token
    if not verify_token(token):
        return redirect("/login")
    return render_template("index.html")


@app.route("/login")
def login_page():
    return render_template("login.html")


# ── Auth ───────────────────────────────────────────────────────────

@app.route("/api/auth/signup", methods=["POST"])
def signup():
    data = request.get_json() or {}
    name  = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    pwd   = data.get("password", "")

    if not name or not email or not pwd:
        return jsonify({"error": "All fields required"}), 400
    if len(pwd) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if get_user_by_email(email):
        return jsonify({"error": "Email already registered"}), 409

    user = create_user(name, email, hash_password(pwd))

    # Send verification email in background — don't block signup
    import secrets as _sec, threading as _th
    vtoken = _sec.token_urlsafe(32)
    from database import set_verify_token
    set_verify_token(user["id"], vtoken)
    _th.Thread(target=send_verification_email, args=(email, name, vtoken, request.host_url), daemon=True).start()

    token = generate_token(user["id"], user["email"])
    _track_session(user["id"], token)
    res = make_response(jsonify({"token": token, "user": {"id": user["id"], "name": user["name"], "email": user["email"]}}))
    res.set_cookie("token", token, httponly=True, max_age=72*3600, samesite="Lax")
    return res


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    pwd   = data.get("password", "")
    totp_code = data.get("totp_code", "").strip()

    user = get_user_by_email(email)
    if not user or not check_password(pwd, user["password"]):
        return jsonify({"error": "Invalid email or password"}), 401

    # 2FA check
    if user.get("totp_enabled") and user.get("totp_secret"):
        if not totp_code:
            return jsonify({"error": "2FA code required", "requires_2fa": True}), 401
        import pyotp
        totp = pyotp.TOTP(user["totp_secret"])
        if not totp.verify(totp_code, valid_window=1):
            return jsonify({"error": "Invalid 2FA code"}), 401

    token = generate_token(user["id"], user["email"])
    _track_session(user["id"], token)
    res = make_response(jsonify({"token": token, "user": {"id": user["id"], "name": user["name"], "email": user["email"]}}))
    res.set_cookie("token", token, httponly=True, max_age=72*3600, samesite="Lax")
    return res


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    res = make_response(jsonify({"message": "Logged out"}))
    res.delete_cookie("token")
    return res


@app.route("/api/auth/delete-account", methods=["POST"])
@require_auth
def delete_account(current_user):
    user_id = current_user["id"]
    # Clear vector store first
    try:
        rag.clear_user(user_id)
    except Exception:
        pass
    # Delete user row — CASCADE handles all related data
    with __import__("database")._conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
        conn.commit()
    res = make_response(jsonify({"message": "Account deleted"}))
    res.delete_cookie("token")
    return res


@app.route("/api/auth/me", methods=["GET"])
@require_auth
def me(current_user):
    return jsonify({"user": {"id": current_user["id"], "name": current_user["name"], "email": current_user["email"]}})


# ── Documents ──────────────────────────────────────────────────────

@app.route("/api/documents", methods=["GET"])
@require_auth
def list_documents(current_user):
    docs = get_user_documents(current_user["id"])
    return jsonify({"documents": docs})


@app.route("/api/documents/upload", methods=["POST"])
@require_auth
def upload(current_user):
    # Tier limit check
    from database import check_tier_limit, get_user_tier
    allowed, limit, _ = check_tier_limit(current_user["id"], "docs")
    if not allowed:
        tier = get_user_tier(current_user["id"])
        return jsonify({"error": f"Document limit reached ({limit} docs on {tier} plan). Upgrade to add more.", "limit_reached": True}), 429

    if "files" not in request.files:
        return jsonify({"error": "No files provided"}), 400

    files = request.files.getlist("files")
    results = []
    user_id = current_user["id"]
    folder_id = request.form.get("folder_id") or None

    for file in files:
        if not file or not file.filename:
            continue
        if not allowed_file(file.filename):
            results.append({"file": file.filename, "error": "Unsupported file type"})
            continue

        orig_name = file.filename
        filename  = f"u{user_id}_{secure_filename(orig_name)}"
        file_type = os.path.splitext(orig_name)[1].lower().lstrip(".")

        # Save to storage (local or Cloudinary)
        identifier = save_file(file, filename)
        file_size  = get_file_size(identifier)

        # Get a local path for processing
        local_path, is_temp = get_file_path(identifier)
        try:
            chunks, pages, chunk_count = process_document(local_path, orig_name)
            full_text = " ".join(c["text"] for c in chunks)[:500000]

            from database import get_latest_version
            existing_version = get_latest_version(orig_name, user_id)
            version = existing_version + 1 if existing_version > 0 else 1

            if existing_version > 0:
                rag.remove_document(user_id, orig_name)

            rag.add_chunks(user_id, chunks)
            add_document(user_id, identifier, orig_name, file_size, file_type, pages, chunk_count,
                         folder_id=folder_id, full_text=full_text, version=version)
            results.append({"file": orig_name, "chunks": chunk_count, "pages": pages, "version": version})
            from database import log_activity
            log_activity(user_id, "uploaded_document", "document", None, orig_name)
        except Exception as e:
            import traceback; traceback.print_exc()
            results.append({"file": orig_name, "error": str(e)})
        finally:
            if is_temp and os.path.exists(local_path):
                os.remove(local_path)

    return jsonify({"results": results, "documents": get_user_documents(user_id)})


@app.route("/api/documents/<int:doc_id>", methods=["DELETE"])
@require_auth
def delete_doc(current_user, doc_id):
    doc = delete_document(doc_id, current_user["id"])
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    # Remove from vector store
    rag.remove_document(current_user["id"], doc["orig_name"])
    rag.purge_stale_vectors(current_user["id"])
    # Delete from storage (local or Cloudinary)
    delete_file(doc["filename"])
    from database import log_activity
    log_activity(current_user["id"], "deleted_document", "document", doc_id, doc["orig_name"])
    return jsonify({"message": "Deleted"})


@app.route("/api/documents/<int:doc_id>/summarize", methods=["POST"])
@require_auth
def summarize(current_user, doc_id):
    docs = get_user_documents(current_user["id"])
    doc  = next((d for d in docs if d["id"] == doc_id), None)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    summary = rag.summarize_document(current_user["id"], doc["orig_name"])
    return jsonify({"summary": summary})


@app.route("/api/documents/<int:doc_id>/questions", methods=["GET"])
@require_auth
def suggest_questions(current_user, doc_id):
    docs = get_user_documents(current_user["id"])
    doc  = next((d for d in docs if d["id"] == doc_id), None)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    questions = rag.suggest_questions(current_user["id"], doc["orig_name"])
    return jsonify({"questions": questions})


@app.route("/api/documents/<int:doc_id>/topics", methods=["GET"])
@require_auth
def key_topics(current_user, doc_id):
    docs = get_user_documents(current_user["id"])
    doc  = next((d for d in docs if d["id"] == doc_id), None)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    topics = rag.extract_key_topics(current_user["id"], doc["orig_name"])
    return jsonify({"topics": topics})


# ── Chats ──────────────────────────────────────────────────────────

@app.route("/api/chats", methods=["GET"])
@require_auth
def list_chats(current_user):
    chats = get_user_chats(current_user["id"])
    return jsonify({"chats": chats})


@app.route("/api/chats", methods=["POST"])
@require_auth
def new_chat(current_user):
    chat = create_chat(current_user["id"])
    return jsonify({"chat": dict(chat)})


@app.route("/api/chats/<int:chat_id>", methods=["DELETE"])
@require_auth
def remove_chat(current_user, chat_id):
    delete_chat(chat_id, current_user["id"])
    return jsonify({"message": "Deleted"})


@app.route("/api/chats/<int:chat_id>/messages", methods=["GET"])
@require_auth
def get_messages(current_user, chat_id):
    msgs = get_chat_messages(chat_id)
    return jsonify({"messages": msgs})


# ── Ask (Streaming SSE) ────────────────────────────────────────────

@app.route("/api/chats/<int:chat_id>/ask", methods=["POST"])
@require_auth
def ask(current_user, chat_id):
    data     = request.get_json() or {}
    question = data.get("question", "").strip()
    mention_doc = data.get("mention_doc", "").strip()

    if not question:
        return jsonify({"error": "Question is required"}), 400
    if not GEMINI_API_KEY:
        return jsonify({"error": "GEMINI_API_KEY not configured"}), 500

    # Tier limit check
    from database import check_tier_limit, get_user_tier
    allowed, limit, _ = check_tier_limit(current_user["id"], "queries")
    if not allowed:
        tier = get_user_tier(current_user["id"])
        return jsonify({"error": f"Daily query limit reached ({limit}/day on {tier} plan). Upgrade to continue.", "limit_reached": True}), 429

    user_id = current_user["id"]

    # Save user message immediately
    add_message(chat_id, "user", question)

    # Auto-title chat on first message
    chats = get_user_chats(user_id)
    chat  = next((c for c in chats if c["id"] == chat_id), None)
    if chat and chat["title"] == "New Chat":
        title = question[:50] + ("..." if len(question) > 50 else "")
        update_chat_title(chat_id, title)

    def generate():
        full_answer = ""
        confidence_val = None
        try:
            recent_msgs = get_chat_messages(chat_id)[-6:]
            result = rag.build_prompt_with_history(user_id, question, recent_msgs,
                                                    mention_doc=mention_doc if mention_doc else None)

            sources, prompt, confidence = result
            confidence_val = confidence

            for token in rag.stream_answer(prompt):
                full_answer += token
                yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            import traceback; traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"
        finally:
            if full_answer:
                add_message(chat_id, "assistant", full_answer, None, None, None)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


# ── Analytics ──────────────────────────────────────────────────────

@app.route("/api/auth/update", methods=["POST"])
@require_auth
def update_profile(current_user):
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    old_pwd = data.get("old_password", "")
    new_pwd = data.get("new_password", "")

    if not name:
        return jsonify({"error": "Name is required"}), 400

    with __import__("database")._conn() as conn:
        with conn.cursor() as cur:
            if new_pwd:
                if not check_password(old_pwd, current_user["password"]):
                    return jsonify({"error": "Current password is incorrect"}), 400
                if len(new_pwd) < 6:
                    return jsonify({"error": "Password must be at least 6 characters"}), 400
                cur.execute("UPDATE users SET name=%s, password=%s WHERE id=%s",
                            (name, hash_password(new_pwd), current_user["id"]))
            else:
                cur.execute("UPDATE users SET name=%s WHERE id=%s", (name, current_user["id"]))
        conn.commit()

    return jsonify({"message": "Profile updated"})


@app.route("/api/clear-all", methods=["POST"])
@require_auth
def clear_all(current_user):
    rag.clear_user(current_user["id"])
    # Delete all document records
    with __import__("database")._conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE user_id=%s", (current_user["id"],))
        conn.commit()
    return jsonify({"message": "Cleared"})


@app.route("/api/purge-stale-vectors", methods=["POST"])
@require_auth
def purge_stale_vectors(current_user):
    """Remove vectors for documents no longer in the knowledge base."""
    rag.purge_stale_vectors(current_user["id"])
    return jsonify({"message": "Stale vectors purged"})


# ── Analytics ──────────────────────────────────────────────────────

@app.route("/api/analytics", methods=["GET"])
@require_auth
def analytics(current_user):
    data = get_analytics(current_user["id"])
    return jsonify(data)


# ── Suggested questions (global) ───────────────────────────────────

@app.route("/api/suggest", methods=["GET"])
@require_auth
def suggest(current_user):
    docs = get_user_documents(current_user["id"])
    if not docs:
        return jsonify({"questions": []})
    # Always purge stale vectors before generating suggestions
    rag.purge_stale_vectors(current_user["id"])
    doc_names = [d["orig_name"] for d in docs]
    questions = rag.suggest_questions_from_docs(current_user["id"], doc_names)
    return jsonify({"questions": questions})


# ── URL & YouTube Ingestion ────────────────────────────────────────

@app.route("/api/ingest/url", methods=["POST"])
@require_auth
def ingest_url(current_user):
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL required"}), 400
    try:
        added, total = rag.ingest_url(current_user["id"], url)
        from database import add_document
        add_document(current_user["id"], url[:100], url[:100], 0, "url", 1, total)
        return jsonify({"message": f"Indexed {added} chunks from URL", "chunks": added})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ingest/youtube", methods=["POST"])
@require_auth
def ingest_youtube(current_user):
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL required"}), 400
    try:
        added, source_name = rag.ingest_youtube(current_user["id"], url)
        from database import add_document
        add_document(current_user["id"], url[:100], source_name, 0, "youtube", 1, added)
        return jsonify({"message": f"Indexed {added} chunks from YouTube", "chunks": added, "title": source_name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Message Feedback ───────────────────────────────────────────────

@app.route("/api/messages/<int:msg_id>/feedback", methods=["POST"])
@require_auth
def message_feedback(current_user, msg_id):
    data = request.get_json() or {}
    rating = data.get("rating")
    if rating not in [1, -1]:
        return jsonify({"error": "Rating must be 1 or -1"}), 400
    from database import add_feedback
    add_feedback(msg_id, rating)
    return jsonify({"message": "Feedback saved"})


# ── Pin / Unpin Messages ───────────────────────────────────────────

@app.route("/api/messages/<int:msg_id>/pin", methods=["POST"])
@require_auth
def pin_msg(current_user, msg_id):
    data = request.get_json() or {}
    chat_id = data.get("chat_id")
    from database import pin_message
    pin_message(chat_id, msg_id)
    return jsonify({"message": "Pinned"})


@app.route("/api/messages/<int:msg_id>/unpin", methods=["DELETE"])
@require_auth
def unpin_msg(current_user, msg_id):
    from database import unpin_message
    unpin_message(msg_id)
    return jsonify({"message": "Unpinned"})


# ── Document Tags ──────────────────────────────────────────────────

@app.route("/api/documents/<int:doc_id>/tags", methods=["POST"])
@require_auth
def add_doc_tag(current_user, doc_id):
    data = request.get_json() or {}
    tag = data.get("tag", "").strip()
    if not tag:
        return jsonify({"error": "Tag required"}), 400
    from database import add_tag
    add_tag(doc_id, current_user["id"], tag)
    return jsonify({"message": "Tag added"})


@app.route("/api/documents/<int:doc_id>/tags", methods=["GET"])
@require_auth
def get_doc_tags_route(current_user, doc_id):
    from database import get_doc_tags
    tags = get_doc_tags(doc_id)
    return jsonify({"tags": tags})


# ── Message Search ─────────────────────────────────────────────────

@app.route("/api/search", methods=["GET"])
@require_auth
def search_chats(current_user):
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})
    from database import search_messages
    results = search_messages(current_user["id"], q)
    return jsonify({"results": results})


# ── Chat Export ────────────────────────────────────────────────────

@app.route("/api/chats/<int:chat_id>/export", methods=["GET"])
@require_auth
def export_chat(current_user, chat_id):
    import re, io
    from fpdf import FPDF
    from datetime import datetime

    msgs = get_chat_messages(chat_id)
    if not msgs:
        return jsonify({"error": "No messages"}), 404

    chats = get_user_chats(current_user["id"])
    chat  = next((c for c in chats if c["id"] == chat_id), None)
    raw_title = chat["title"] if chat else f"Chat {chat_id}"

    # ── Single sanitizer: handles ALL text going into FPDF ──────────
    _UNI_MAP = str.maketrans({
        '\u2022':'-','\u2023':'-','\u25e6':'-','\u2043':'-','\u2219':'-',
        '\u2013':'-','\u2014':'-','\u2015':'-',
        '\u2018':"'",'\u2019':"'",'\u201a':"'",'\u201b':"'",
        '\u201c':'"','\u201d':'"','\u201e':'"','\u201f':'"',
        '\u2026':'...','\u00b7':'-','\u2192':'->','\u2190':'<-',
        '\u2713':'v','\u2714':'v','\u2715':'x','\u2716':'x',
        '\u00b0':'deg','\u00ae':'(R)','\u00a9':'(C)','\u2122':'(TM)',
        '\u00e0':'a','\u00e1':'a','\u00e2':'a','\u00e3':'a',
        '\u00e4':'a','\u00e5':'a','\u00e6':'ae','\u00e7':'c',
        '\u00e8':'e','\u00e9':'e','\u00ea':'e','\u00eb':'e',
        '\u00ec':'i','\u00ed':'i','\u00ee':'i','\u00ef':'i',
        '\u00f0':'d','\u00f1':'n','\u00f2':'o','\u00f3':'o',
        '\u00f4':'o','\u00f5':'o','\u00f6':'o','\u00f8':'o',
        '\u00f9':'u','\u00fa':'u','\u00fb':'u','\u00fc':'u',
        '\u00fd':'y','\u00ff':'y','\u00df':'ss',
    })

    def safe(text):
        """Make any string safe for FPDF (latin-1 only) — nuclear approach."""
        if not text:
            return ''
        text = text.translate(_UNI_MAP)
        # Final fallback: encode to ascii ignoring everything else
        return text.encode('ascii', errors='ignore').decode('ascii')

    def strip_md(text):
        """Strip markdown formatting and sanitize for PDF."""
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text, flags=re.DOTALL)
        text = re.sub(r'\*(.+?)\*',     r'\1', text, flags=re.DOTALL)
        text = re.sub(r'#{1,6}\s+', '', text)
        text = re.sub(r'```[\s\S]*?```', lambda m: m.group().strip('`').strip(), text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        text = re.sub(r'^\s*[-*+]\s+', '- ', text, flags=re.MULTILINE)
        text = re.sub(r'\(Source:[^)]+\)', '', text)
        text = re.sub(r'\[Source:[^\]]+\]', '', text)
        return safe(text.strip())

    title = safe(raw_title)
    date_str = safe(datetime.now().strftime('%B %d, %Y') + '  |  ' + str(len(msgs)) + ' messages')

    class ChatPDF(FPDF):
        def header(self):
            self.set_font('Helvetica', 'B', 10)
            self.set_text_color(124, 58, 237)
            self.cell(0, 8, safe('Lexara AI'), ln=False)
            self.set_font('Helvetica', '', 8)
            self.set_text_color(100, 116, 139)
            self.cell(0, 8, '  ' + title, ln=True, align='R')
            self.set_draw_color(124, 58, 237)
            self.set_line_width(0.4)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(3)

        def footer(self):
            self.set_y(-12)
            self.set_font('Helvetica', '', 7)
            self.set_text_color(148, 163, 184)
            self.cell(0, 8, safe('Page ' + str(self.page_no()) + ' - Generated by Lexara AI'), align='C')

    pdf = ChatPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    pdf.set_font('Helvetica', 'B', 16)
    pdf.set_text_color(15, 23, 42)
    pdf.multi_cell(0, 9, title, align='L')
    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 6, date_str, ln=True)
    pdf.ln(4)

    for m in msgs:
        is_user = m["role"] == "user"
        content = strip_md(m["content"] or "")
        if not content:
            continue

        pdf.set_font('Helvetica', 'B', 7.5)
        if is_user:
            pdf.set_text_color(124, 58, 237)
            pdf.cell(0, 5, safe('YOU'), ln=True)
        else:
            pdf.set_text_color(8, 145, 178)
            pdf.cell(0, 5, safe('LEXARA AI'), ln=True)

        pdf.set_font('Helvetica', '', 9.5)
        pdf.set_text_color(15, 23, 42)
        pdf.set_left_margin(18)
        pdf.set_right_margin(15)

        y_before = pdf.get_y()
        pdf.multi_cell(0, 6, content)
        y_after = pdf.get_y()

        if is_user:
            pdf.set_draw_color(124, 58, 237)
        else:
            pdf.set_draw_color(8, 145, 178)
        pdf.set_line_width(1.5)
        pdf.line(16, y_before, 16, y_after)

        pdf.set_left_margin(15)
        pdf.set_right_margin(15)
        pdf.ln(4)

    buf = io.BytesIO()
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    buf.write(pdf_bytes)
    buf.seek(0)

    safe_name = re.sub(r'[^\w\s-]', '', raw_title)[:40].strip().replace(' ', '_') or 'chat'
    from flask import Response as FlaskResponse
    return FlaskResponse(
        buf.read(),
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{safe_name}.pdf"'}
    )


# ── Google OAuth ───────────────────────────────────────────────────

@app.route("/auth/google")
def google_login():
    redirect_uri = request.host_url.rstrip("/") + "/auth/google/callback"
    return oauth.google.authorize_redirect(redirect_uri)


@app.route("/auth/google/callback")
def google_callback():
    token = oauth.google.authorize_access_token()
    userinfo = token.get("userinfo") or oauth.google.userinfo()
    email = userinfo["email"].lower()
    name  = userinfo.get("name", email.split("@")[0])
    return _oauth_login_or_create(name, email)


# ── GitHub OAuth ───────────────────────────────────────────────────

@app.route("/auth/github")
def github_login():
    redirect_uri = request.host_url.rstrip("/") + "/auth/github/callback"
    return oauth.github.authorize_redirect(redirect_uri)


@app.route("/auth/github/callback")
def github_callback():
    oauth.github.authorize_access_token()
    resp  = oauth.github.get("user")
    profile = resp.json()
    # GitHub may not expose email publicly — fetch it separately
    email = profile.get("email")
    if not email:
        emails_resp = oauth.github.get("user/emails")
        for e in emails_resp.json():
            if e.get("primary") and e.get("verified"):
                email = e["email"]
                break
    if not email:
        return redirect("/login?error=no_email")
    name = profile.get("name") or profile.get("login", email.split("@")[0])
    return _oauth_login_or_create(name, email.lower())


# ── Shared helper ──────────────────────────────────────────────────

def _oauth_login_or_create(name: str, email: str):
    """Find or create user, set auth cookie, redirect to app."""
    user = get_user_by_email(email)
    if not user:
        # Create account with a random unusable password
        import secrets
        user = create_user(name, email, hash_password(secrets.token_hex(32)))
    token = generate_token(user["id"], user["email"])
    res = make_response(redirect("/"))
    res.set_cookie("token", token, httponly=True, max_age=72*3600, samesite="Lax")
    return res


# ── Folders ────────────────────────────────────────────────────────

@app.route("/api/folders", methods=["GET"])
@require_auth
def list_folders(current_user):
    from database import get_user_folders
    folders = get_user_folders(current_user["id"])
    return jsonify({"folders": folders})

@app.route("/api/folders", methods=["POST"])
@require_auth
def create_folder_route(current_user):
    from database import create_folder
    data = request.get_json() or {}
    name  = data.get("name", "").strip()
    color = data.get("color", "#8b5cf6")
    if not name:
        return jsonify({"error": "Folder name required"}), 400
    folder = create_folder(current_user["id"], name, color)
    return jsonify({"folder": folder})

@app.route("/api/folders/<int:folder_id>", methods=["DELETE"])
@require_auth
def delete_folder_route(current_user, folder_id):
    from database import delete_folder
    delete_folder(folder_id, current_user["id"])
    return jsonify({"message": "Deleted"})

@app.route("/api/documents/<int:doc_id>/move", methods=["POST"])
@require_auth
def move_doc(current_user, doc_id):
    from database import move_document_to_folder
    data = request.get_json() or {}
    folder_id = data.get("folder_id")  # None = remove from folder
    move_document_to_folder(doc_id, current_user["id"], folder_id)
    return jsonify({"message": "Moved"})


# ── Document versioning ────────────────────────────────────────────

@app.route("/api/documents/<int:doc_id>/versions", methods=["GET"])
@require_auth
def doc_versions(current_user, doc_id):
    from database import get_document_versions, get_user_documents
    docs = get_user_documents(current_user["id"])
    doc  = next((d for d in docs if d["id"] == doc_id), None)
    if not doc:
        return jsonify({"error": "Not found"}), 404
    from database import get_document_versions
    versions = get_document_versions(doc["orig_name"], current_user["id"])
    return jsonify({"versions": versions})


# ── Document comparison ────────────────────────────────────────────

@app.route("/api/documents/compare", methods=["POST"])
@require_auth
def compare_docs(current_user):
    data  = request.get_json() or {}
    doc_a = data.get("doc_a", "").strip()
    doc_b = data.get("doc_b", "").strip()
    topic = data.get("topic", "general content").strip()
    if not doc_a or not doc_b:
        return jsonify({"error": "Two document names required"}), 400
    result = rag.compare_documents(current_user["id"], doc_a, doc_b, topic)
    return jsonify({"comparison": result})


# ── Full-text document search ──────────────────────────────────────

@app.route("/api/documents/search", methods=["GET"])
@require_auth
def search_docs(current_user):
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})
    from database import search_document_content
    results = search_document_content(current_user["id"], q)
    return jsonify({"results": results})


# ── Document preview (serve file for inline rendering) ────────────

@app.route("/api/documents/<int:doc_id>/preview")
@require_auth
def preview_doc(current_user, doc_id):
    from flask import send_file
    docs = get_user_documents(current_user["id"])
    doc  = next((d for d in docs if d["id"] == doc_id), None)
    if not doc:
        return jsonify({"error": "Not found"}), 404
    fp = os.path.join(app.config["UPLOAD_FOLDER"], doc["filename"])
    if not os.path.exists(fp):
        return jsonify({"error": "File not found on disk"}), 404
    mime = "application/pdf" if doc["file_type"] == "pdf" else "application/octet-stream"
    return send_file(fp, mimetype=mime, as_attachment=False)


# ── Saved Prompts ──────────────────────────────────────────────────

@app.route("/api/prompts", methods=["GET"])
@require_auth
def list_prompts(current_user):
    from database import get_saved_prompts
    return jsonify({"prompts": get_saved_prompts(current_user["id"])})

@app.route("/api/prompts", methods=["POST"])
@require_auth
def save_prompt(current_user):
    from database import create_saved_prompt
    data = request.get_json() or {}
    title  = data.get("title", "").strip()
    prompt = data.get("prompt", "").strip()
    if not title or not prompt:
        return jsonify({"error": "Title and prompt required"}), 400
    row = create_saved_prompt(current_user["id"], title, prompt)
    return jsonify({"prompt": row})

@app.route("/api/prompts/<int:prompt_id>", methods=["DELETE"])
@require_auth
def del_prompt(current_user, prompt_id):
    from database import delete_saved_prompt
    delete_saved_prompt(prompt_id, current_user["id"])
    return jsonify({"message": "Deleted"})


# ── Chat Sharing ───────────────────────────────────────────────────

@app.route("/api/chats/<int:chat_id>/share", methods=["POST"])
@require_auth
def share_chat(current_user, chat_id):
    from database import create_share_token, get_share_by_chat
    # Verify ownership
    chats = get_user_chats(current_user["id"])
    if not any(c["id"] == chat_id for c in chats):
        return jsonify({"error": "Chat not found"}), 404
    row = create_share_token(chat_id, current_user["id"])
    return jsonify({"token": row["token"], "url": f"/share/{row['token']}"})

@app.route("/api/chats/<int:chat_id>/share", methods=["GET"])
@require_auth
def get_share(current_user, chat_id):
    from database import get_share_by_chat
    row = get_share_by_chat(chat_id, current_user["id"])
    if not row:
        return jsonify({"token": None})
    return jsonify({"token": row["token"], "url": f"/share/{row['token']}"})

@app.route("/share/<token>")
def view_shared_chat(token):
    from database import get_share_by_token, get_chat_messages
    share = get_share_by_token(token)
    if not share:
        return "Chat not found or link expired.", 404
    msgs = get_chat_messages(share["chat_id"])
    return render_template("shared_chat.html",
                           title=share["title"],
                           messages=msgs,
                           token=token)


# ── Chat Branching ─────────────────────────────────────────────────

@app.route("/api/chats/<int:chat_id>/branch", methods=["POST"])
@require_auth
def branch_chat(current_user, chat_id):
    from database import create_branch, get_chat_messages, create_chat, add_message
    data = request.get_json() or {}
    msg_id = data.get("message_id")  # branch from this message

    # Get messages up to and including the branch point
    all_msgs = get_chat_messages(chat_id)
    if msg_id:
        msgs_to_copy = []
        for m in all_msgs:
            msgs_to_copy.append(m)
            if m["id"] == msg_id:
                break
    else:
        msgs_to_copy = all_msgs

    # Create new chat
    new_chat = create_chat(current_user["id"], title=f"Branch of chat {chat_id}")
    for m in msgs_to_copy:
        add_message(new_chat["id"], m["role"], m["content"], m.get("sources"))

    create_branch(chat_id, new_chat["id"], msg_id)
    return jsonify({"chat": new_chat})


# ── Answer Regeneration ────────────────────────────────────────────

@app.route("/api/chats/<int:chat_id>/regenerate", methods=["POST"])
@require_auth
def regenerate(current_user, chat_id):
    """Re-ask the last user question and stream a new answer."""
    from database import get_chat_messages
    msgs = get_chat_messages(chat_id)
    # Find last user message
    last_user = next((m for m in reversed(msgs) if m["role"] == "user"), None)
    if not last_user:
        return jsonify({"error": "No question to regenerate"}), 400

    question = last_user["content"]
    user_id  = current_user["id"]

    def generate():
        full_answer = ""
        sources_data = []
        try:
            recent_msgs = [m for m in msgs if m["id"] != last_user["id"]][-6:]
            sources, prompt, confidence = rag.build_prompt_with_history(user_id, question, recent_msgs)
            for token in rag.stream_answer(prompt):
                full_answer += token
                yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"
        finally:
            if full_answer:
                add_message(chat_id, "assistant", full_answer, None, None, None)

    return Response(stream_with_context(generate()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _track_session(user_id, token):
    """Record a new session in the DB."""
    import hashlib
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    device = request.headers.get("User-Agent", "")[:200]
    ip = request.remote_addr or ""
    from database import create_session
    try:
        create_session(user_id, token_hash, device, ip)
    except Exception:
        pass  # non-critical


# ── Email verification ─────────────────────────────────────────────

@app.route("/api/auth/verify-email")
def verify_email_route():
    token = request.args.get("token", "")
    from database import verify_email
    user = verify_email(token)
    if not user:
        return "<h2>Invalid or expired verification link.</h2>", 400
    return redirect("/?verified=1")

@app.route("/api/auth/resend-verification", methods=["POST"])
@require_auth
def resend_verification(current_user):
    if current_user.get("email_verified"):
        return jsonify({"message": "Already verified"})
    import secrets as _sec, threading as _th
    from database import set_verify_token
    vtoken = _sec.token_urlsafe(32)
    set_verify_token(current_user["id"], vtoken)
    _th.Thread(target=send_verification_email, args=(current_user["email"], current_user["name"], vtoken, request.host_url), daemon=True).start()
    return jsonify({"message": "Verification email sent"})


# ── Password reset ─────────────────────────────────────────────────

@app.route("/api/auth/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    user = get_user_by_email(email)
    if user:
        import secrets as _sec, datetime as _dt, threading as _th
        from database import set_reset_token
        token = _sec.token_urlsafe(32)
        expires = _dt.datetime.utcnow() + _dt.timedelta(hours=1)
        set_reset_token(email, token, expires)
        _th.Thread(target=send_reset_email, args=(email, user["name"], token, request.host_url), daemon=True).start()
    # Always return success to prevent email enumeration
    return jsonify({"message": "If that email exists, a reset link has been sent"})

@app.route("/reset-password")
def reset_password_page():
    token = request.args.get("token", "")
    return render_template("reset_password.html", token=token)

@app.route("/api/auth/reset-password", methods=["POST"])
def do_reset_password():
    data = request.get_json() or {}
    token = data.get("token", "")
    new_pwd = data.get("password", "")
    if len(new_pwd) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    from database import get_user_by_reset_token, clear_reset_token
    user = get_user_by_reset_token(token)
    if not user:
        return jsonify({"error": "Invalid or expired reset link"}), 400
    clear_reset_token(user["id"], hash_password(new_pwd))
    return jsonify({"message": "Password reset successfully"})


# ── 2FA / TOTP ─────────────────────────────────────────────────────

@app.route("/api/auth/2fa/setup", methods=["POST"])
@require_auth
def setup_2fa(current_user):
    import pyotp, qrcode, io, base64
    from database import set_totp_secret
    secret = pyotp.random_base32()
    set_totp_secret(current_user["id"], secret)
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=current_user["email"], issuer_name="Lexara AI")
    # Generate QR code as base64 PNG
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    return jsonify({"secret": secret, "qr": f"data:image/png;base64,{qr_b64}", "uri": uri})

@app.route("/api/auth/2fa/verify", methods=["POST"])
@require_auth
def verify_2fa(current_user):
    import pyotp
    from database import enable_totp
    data = request.get_json() or {}
    code = data.get("code", "").strip()
    user = get_user_by_email(current_user["email"])
    if not user or not user.get("totp_secret"):
        return jsonify({"error": "2FA not set up"}), 400
    totp = pyotp.TOTP(user["totp_secret"])
    if not totp.verify(code, valid_window=1):
        return jsonify({"error": "Invalid code"}), 400
    enable_totp(current_user["id"])
    return jsonify({"message": "2FA enabled"})

@app.route("/api/auth/2fa/disable", methods=["POST"])
@require_auth
def disable_2fa(current_user):
    import pyotp
    from database import disable_totp
    data = request.get_json() or {}
    code = data.get("code", "").strip()
    user = get_user_by_email(current_user["email"])
    if user and user.get("totp_enabled"):
        totp = pyotp.TOTP(user["totp_secret"])
        if not totp.verify(code, valid_window=1):
            return jsonify({"error": "Invalid code"}), 400
    disable_totp(current_user["id"])
    return jsonify({"message": "2FA disabled"})


# ── Session management ─────────────────────────────────────────────

@app.route("/api/auth/sessions", methods=["GET"])
@require_auth
def list_sessions(current_user):
    from database import get_user_sessions
    sessions = get_user_sessions(current_user["id"])
    return jsonify({"sessions": sessions})

@app.route("/api/auth/sessions/<int:session_id>", methods=["DELETE"])
@require_auth
def revoke_session_route(current_user, session_id):
    from database import revoke_session
    revoke_session(session_id, current_user["id"])
    return jsonify({"message": "Session revoked"})

@app.route("/api/auth/sessions/revoke-all", methods=["POST"])
@require_auth
def revoke_all_route(current_user):
    import hashlib
    from database import revoke_all_sessions
    token = request.cookies.get("token") or ""
    current_hash = hashlib.sha256(token.encode()).hexdigest() if token else None
    revoke_all_sessions(current_user["id"], except_hash=current_hash)
    return jsonify({"message": "All other sessions revoked"})


# ── Workspaces ─────────────────────────────────────────────────────

@app.route("/api/workspaces", methods=["GET"])
@require_auth
def list_workspaces(current_user):
    from database import get_user_workspaces
    return jsonify({"workspaces": get_user_workspaces(current_user["id"])})

@app.route("/api/workspaces", methods=["POST"])
@require_auth
def create_workspace_route(current_user):
    from database import create_workspace, log_activity
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    desc = data.get("description", "").strip()
    if not name:
        return jsonify({"error": "Name required"}), 400
    ws = create_workspace(current_user["id"], name, desc)
    log_activity(current_user["id"], "created_workspace", "workspace", ws["id"], name)
    return jsonify({"workspace": ws})

@app.route("/api/workspaces/<int:ws_id>", methods=["DELETE"])
@require_auth
def delete_workspace_route(current_user, ws_id):
    from database import delete_workspace, log_activity
    delete_workspace(ws_id, current_user["id"])
    log_activity(current_user["id"], "deleted_workspace", "workspace", ws_id)
    return jsonify({"message": "Deleted"})

@app.route("/api/workspaces/<int:ws_id>", methods=["PATCH"])
@require_auth
def edit_workspace_route(current_user, ws_id):
    from database import update_workspace
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    desc = data.get("description", "").strip()
    if not name:
        return jsonify({"error": "Name required"}), 400
    result = update_workspace(ws_id, current_user["id"], name, desc)
    if not result:
        return jsonify({"error": "Access denied"}), 403
    return jsonify({"workspace": result})

@app.route("/api/workspaces/<int:ws_id>/members", methods=["GET"])
@require_auth
def get_ws_members(current_user, ws_id):
    from database import get_workspace_members, can_access_workspace
    if not can_access_workspace(ws_id, current_user["id"]):
        return jsonify({"error": "Access denied"}), 403
    return jsonify({"members": get_workspace_members(ws_id)})

@app.route("/api/workspaces/<int:ws_id>/members", methods=["POST"])
@require_auth
def invite_ws_member(current_user, ws_id):
    from database import invite_workspace_member, get_workspace, get_workspace_role, log_activity
    from mailer import send_workspace_invite_email
    import threading
    ws = get_workspace(ws_id)
    if not ws:
        return jsonify({"error": "Workspace not found"}), 404
    role_in_ws = get_workspace_role(ws_id, current_user["id"])
    if role_in_ws not in ("owner", "admin"):
        return jsonify({"error": "Only owners and admins can invite members"}), 403
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    role  = data.get("role", "viewer")
    if not email:
        return jsonify({"error": "Email required"}), 400
    if role not in ("admin", "editor", "viewer"):
        return jsonify({"error": "Invalid role"}), 400
    member = invite_workspace_member(ws_id, email, role, current_user["id"])
    if not member:
        return jsonify({"error": "Already a member"}), 409
    # Send email in background — don't block the response
    _token    = member["invite_token"]
    _host_url = request.host_url
    _inviter  = current_user["name"]
    _ws_name  = ws["name"]
    threading.Thread(
        target=send_workspace_invite_email,
        args=(email, _inviter, _ws_name, role, _token, _host_url),
        daemon=True
    ).start()
    log_activity(current_user["id"], "invited_member", "workspace", ws_id, email)
    return jsonify({"member": member})


@app.route("/workspace-invite")
def workspace_invite_page():
    token = request.args.get("token", "")
    return render_template("workspace_invite.html", token=token)


@app.route("/api/workspace-invite/info", methods=["GET"])
def workspace_invite_info():
    from database import get_workspace_invite_by_token
    token = request.args.get("token", "").strip()
    if not token:
        return jsonify({"error": "Invalid token"}), 400
    invite = get_workspace_invite_by_token(token)
    if not invite:
        return jsonify({"error": "Invitation not found or already accepted"}), 404
    # Return safe public info only (no user_id, no internal fields)
    return jsonify({
        "email":          invite["email"],
        "role":           invite["role"],
        "workspace_name": invite["workspace_name"],
        "inviter_name":   invite["inviter_name"],
    })


@app.route("/api/workspace-invite/accept", methods=["POST"])
def accept_workspace_invite():
    from database import get_workspace_invite_by_token, accept_workspace_invite as db_accept
    from auth import verify_token
    data  = request.get_json() or {}
    token = data.get("token", "").strip()
    if not token:
        return jsonify({"error": "Invalid token"}), 400
    invite = get_workspace_invite_by_token(token)
    if not invite:
        return jsonify({"error": "Invitation not found or already accepted"}), 404
    # Require the user to be logged in
    jwt = request.cookies.get("token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    payload = verify_token(jwt) if jwt else None
    if not payload:
        return jsonify({"error": "login_required", "invite_token": token}), 401
    user = get_user_by_email(payload["email"])
    if not user:
        return jsonify({"error": "User not found"}), 404
    if user["email"].lower() != invite["email"].lower():
        return jsonify({"error": "This invitation was sent to a different email address"}), 403
    result = db_accept(token, user["id"], invite["email"])
    if not result:
        return jsonify({"error": "Failed to accept invitation"}), 500
    return jsonify({"message": "Invitation accepted", "workspace_id": invite["workspace_id"], "workspace_name": invite["workspace_name"]})

@app.route("/api/workspaces/<int:ws_id>/members/<int:member_id>", methods=["DELETE"])
@require_auth
def remove_ws_member(current_user, ws_id, member_id):
    from database import remove_workspace_member
    if not remove_workspace_member(ws_id, member_id, current_user["id"]):
        return jsonify({"error": "Access denied"}), 403
    return jsonify({"message": "Removed"})

@app.route("/api/workspaces/<int:ws_id>/members/<int:member_id>", methods=["PATCH"])
@require_auth
def update_ws_member_role(current_user, ws_id, member_id):
    from database import update_member_role
    data = request.get_json() or {}
    role = data.get("role", "viewer")
    if role not in ("admin", "editor", "viewer"):
        return jsonify({"error": "Invalid role"}), 400
    if not update_member_role(ws_id, member_id, role, current_user["id"]):
        return jsonify({"error": "Access denied"}), 403
    return jsonify({"message": "Updated"})

@app.route("/api/workspaces/<int:ws_id>/documents", methods=["GET"])
@require_auth
def get_ws_docs(current_user, ws_id):
    from database import get_workspace_documents, can_access_workspace
    if not can_access_workspace(ws_id, current_user["id"]):
        return jsonify({"error": "Access denied"}), 403
    return jsonify({"documents": get_workspace_documents(ws_id)})

@app.route("/api/workspaces/<int:ws_id>/documents", methods=["POST"])
@require_auth
def add_ws_doc(current_user, ws_id):
    from database import add_doc_to_workspace, can_access_workspace, get_workspace_role, log_activity
    role = get_workspace_role(ws_id, current_user["id"])
    if role not in ("owner", "admin", "editor"):
        return jsonify({"error": "Access denied"}), 403
    data = request.get_json() or {}
    doc_id = data.get("doc_id")
    if not doc_id:
        return jsonify({"error": "doc_id required"}), 400
    # Verify doc belongs to user
    docs = get_user_documents(current_user["id"])
    if not any(d["id"] == doc_id for d in docs):
        return jsonify({"error": "Document not found"}), 404
    add_doc_to_workspace(ws_id, doc_id, current_user["id"])
    log_activity(current_user["id"], "added_document", "document", doc_id, workspace_id=ws_id)
    return jsonify({"message": "Added"})

@app.route("/api/workspaces/<int:ws_id>/documents/<int:doc_id>", methods=["DELETE"])
@require_auth
def remove_ws_doc(current_user, ws_id, doc_id):
    from database import remove_doc_from_workspace, get_workspace_role
    role = get_workspace_role(ws_id, current_user["id"])
    if role not in ("owner", "admin", "editor"):
        return jsonify({"error": "Access denied"}), 403
    remove_doc_from_workspace(ws_id, doc_id)
    return jsonify({"message": "Removed"})


# ── Message Comments ───────────────────────────────────────────────

@app.route("/api/messages/<int:msg_id>/comments", methods=["GET"])
@require_auth
def get_msg_comments(current_user, msg_id):
    from database import get_comments
    return jsonify({"comments": get_comments(msg_id)})

@app.route("/api/messages/<int:msg_id>/comments", methods=["POST"])
@require_auth
def add_msg_comment(current_user, msg_id):
    from database import add_comment
    data = request.get_json() or {}
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "Content required"}), 400
    comment = add_comment(msg_id, current_user["id"], content)
    return jsonify({"comment": comment})

@app.route("/api/comments/<int:comment_id>", methods=["DELETE"])
@require_auth
def delete_msg_comment(current_user, comment_id):
    from database import delete_comment
    delete_comment(comment_id, current_user["id"])
    return jsonify({"message": "Deleted"})


# ── Activity Feed ──────────────────────────────────────────────────

@app.route("/api/activity", methods=["GET"])
@require_auth
def activity_feed(current_user):
    from database import get_activity
    ws_id = request.args.get("workspace_id", type=int)
    items = get_activity(current_user["id"], workspace_id=ws_id, limit=50)
    return jsonify({"activity": items})


# ── Enhanced Analytics ─────────────────────────────────────────────

@app.route("/api/analytics/extended", methods=["GET"])
@require_auth
def analytics_extended(current_user):
    from database import get_analytics_extended
    return jsonify(get_analytics_extended(current_user["id"]))


@app.route("/api/analytics/full", methods=["GET"])
@require_auth
def analytics_full(current_user):
    from database import get_analytics_full
    return jsonify(get_analytics_full(current_user["id"]))


@app.route("/api/analytics/export.csv", methods=["GET"])
@require_auth
def analytics_export_csv(current_user):
    import csv, io
    from database import get_analytics_csv
    data = get_analytics_csv(current_user["id"])

    output = io.StringIO()
    output.write("=== DAILY QUERIES ===\n")
    w = csv.writer(output)
    w.writerow(["Date", "Queries"])
    for row in data["daily"]:
        w.writerow([row["day"], row["queries"]])

    output.write("\n=== DOCUMENTS ===\n")
    w.writerow(["Name", "Type", "Pages", "Chunks", "Size (bytes)", "Uploaded"])
    for row in data["docs"]:
        w.writerow([row["orig_name"], row["file_type"], row["pages"],
                    row["chunks"], row["file_size"], row["created_at"]])

    output.write("\n=== ANSWER FEEDBACK ===\n")
    w.writerow(["Date", "Thumbs Up", "Thumbs Down"])
    for row in data["feedback"]:
        w.writerow([row["day"], row["thumbs_up"], row["thumbs_down"]])

    from flask import Response as FlaskResponse
    return FlaskResponse(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=lexara_analytics.csv"}
    )


# ── API Key auth helper ────────────────────────────────────────────

def require_api_key_or_auth(f):
    """Accepts either cookie/JWT token OR X-API-Key header."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get("X-API-Key", "").strip()
        if api_key:
            from database import get_user_by_api_key
            user = get_user_by_api_key(api_key)
            if not user:
                return jsonify({"error": "Invalid API key"}), 401
            return f(*args, current_user=user, **kwargs)
        # Fall back to normal token auth
        from auth import verify_token
        from database import get_user_by_id
        token = (
            request.cookies.get("token") or
            (request.headers.get("Authorization", "").replace("Bearer ", "") or None)
        )
        if not token:
            return jsonify({"error": "Authentication required"}), 401
        payload = verify_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401
        user = get_user_by_id(payload["uid"])
        if not user:
            return jsonify({"error": "User not found"}), 401
        return f(*args, current_user=user, **kwargs)
    return decorated


def require_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        current_user = kwargs.get("current_user")
        if not current_user or not current_user.get("is_admin"):
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated

# ── User tier info ─────────────────────────────────────────────────

@app.route("/api/billing/tier", methods=["GET"])
@require_auth
def get_my_tier(current_user):
    from database import get_user_tier, get_tier_limits, count_user_queries_today, TIER_LIMITS
    tier = get_user_tier(current_user["id"])
    limits = get_tier_limits(tier)
    queries_today = count_user_queries_today(current_user["id"])
    docs = get_user_documents(current_user["id"])
    return jsonify({
        "tier": tier,
        "limits": limits,
        "usage": {
            "queries_today": queries_today,
            "docs": len(docs),
        },
        "all_tiers": TIER_LIMITS,
    })

@app.route("/api/billing/upgrade", methods=["POST"])
@require_auth
def request_upgrade(current_user):
    """Placeholder — wire Razorpay/Stripe here later."""
    data = request.get_json() or {}
    tier = data.get("tier", "pro")
    if tier not in ("pro", "enterprise"):
        return jsonify({"error": "Invalid tier"}), 400
    # TODO: create payment order here
    return jsonify({
        "message": "Payment gateway coming soon. Contact support@lexara.ai to upgrade.",
        "tier": tier,
        "contact": "support@lexara.ai"
    })


# ── API Key management ─────────────────────────────────────────────

@app.route("/api/keys", methods=["GET"])
@require_auth
def list_api_keys(current_user):
    from database import get_user_api_keys
    return jsonify({"keys": get_user_api_keys(current_user["id"])})

@app.route("/api/keys", methods=["POST"])
@require_auth
def create_key(current_user):
    from database import create_api_key, get_user_tier
    # Only pro/enterprise can use API keys
    tier = get_user_tier(current_user["id"])
    if tier == "free":
        return jsonify({"error": "API key access requires Pro or Enterprise plan"}), 403
    data = request.get_json() or {}
    label = data.get("label", "Default").strip()[:50]
    key = create_api_key(current_user["id"], label)
    return jsonify({"key": key})

@app.route("/api/keys/<int:key_id>", methods=["DELETE"])
@require_auth
def delete_key(current_user, key_id):
    from database import delete_api_key
    delete_api_key(key_id, current_user["id"])
    return jsonify({"message": "Key deleted"})


# ── Public REST API (via API key) ──────────────────────────────────

@app.route("/v1/ask", methods=["POST"])
@require_api_key_or_auth
def public_ask(current_user):
    """Public API endpoint for clients to query via API key."""
    from database import check_tier_limit, get_user_tier
    allowed, limit, _ = check_tier_limit(current_user["id"], "queries")
    if not allowed:
        return jsonify({"error": f"Daily query limit reached ({limit}/day)"}), 429

    data = request.get_json() or {}
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "question required"}), 400

    # Create a temporary chat for this API call
    chat = create_chat(current_user["id"], title=f"API: {question[:40]}")
    add_message(chat["id"], "user", question)

    sources, prompt, confidence = rag.build_prompt_with_history(
        current_user["id"], question, []
    )
    answer = ""
    for token in rag.stream_answer(prompt):
        answer += token

    add_message(chat["id"], "assistant", answer, json.dumps(sources), confidence)
    return jsonify({
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
        "chat_id": chat["id"]
    })

@app.route("/v1/documents", methods=["GET"])
@require_api_key_or_auth
def public_list_docs(current_user):
    docs = get_user_documents(current_user["id"])
    return jsonify({"documents": [{"id": d["id"], "name": d["orig_name"],
                                    "pages": d["pages"], "type": d["file_type"]} for d in docs]})


# ── White-label ────────────────────────────────────────────────────

@app.route("/api/whitelabel", methods=["GET"])
@require_auth
def get_wl(current_user):
    from database import get_white_label, get_user_tier
    tier = get_user_tier(current_user["id"])
    if tier != "enterprise":
        return jsonify({"error": "White-label requires Enterprise plan"}), 403
    wl = get_white_label(current_user["id"]) or {}
    return jsonify({"whitelabel": wl})

@app.route("/api/whitelabel", methods=["POST"])
@require_auth
def save_wl(current_user):
    from database import save_white_label, get_user_tier
    tier = get_user_tier(current_user["id"])
    if tier != "enterprise":
        return jsonify({"error": "White-label requires Enterprise plan"}), 403
    data = request.get_json() or {}
    save_white_label(
        current_user["id"],
        data.get("app_name", "Lexara AI")[:60],
        data.get("logo_url", "")[:300],
        data.get("primary_color", "#8b5cf6")[:20]
    )
    return jsonify({"message": "Saved"})


# ── Admin panel ────────────────────────────────────────────────────

@app.route("/admin")
def admin_page():
    token = request.cookies.get("token")
    if not token:
        return redirect("/login")
    from auth import verify_token
    from database import get_user_by_id
    payload = verify_token(token)
    if not payload:
        return redirect("/login")
    user = get_user_by_id(payload["uid"])
    if not user or not user.get("is_admin"):
        return "Access denied", 403
    return render_template("admin.html")

@app.route("/api/admin/stats", methods=["GET"])
@require_auth
def admin_stats(current_user):
    if not current_user.get("is_admin"):
        return jsonify({"error": "Admin only"}), 403
    from database import get_platform_stats
    return jsonify(get_platform_stats())

@app.route("/api/admin/users", methods=["GET"])
@require_auth
def admin_users(current_user):
    if not current_user.get("is_admin"):
        return jsonify({"error": "Admin only"}), 403
    from database import get_all_users
    limit  = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
    return jsonify({"users": get_all_users(limit, offset)})

@app.route("/api/admin/users/<int:uid>/tier", methods=["POST"])
@require_auth
def admin_set_user_tier(current_user, uid):
    if not current_user.get("is_admin"):
        return jsonify({"error": "Admin only"}), 403
    from database import admin_set_tier
    data = request.get_json() or {}
    tier = data.get("tier", "free")
    if tier not in ("free", "pro", "enterprise"):
        return jsonify({"error": "Invalid tier"}), 400
    admin_set_tier(uid, tier)
    return jsonify({"message": f"User {uid} set to {tier}"})

@app.route("/api/admin/users/<int:uid>", methods=["DELETE"])
@require_auth
def admin_delete_user_route(current_user, uid):
    if not current_user.get("is_admin"):
        return jsonify({"error": "Admin only"}), 403
    if uid == current_user["id"]:
        return jsonify({"error": "Cannot delete yourself"}), 400
    from database import admin_delete_user
    admin_delete_user(uid)
    return jsonify({"message": "User deleted"})


# ── Webhook helpers ────────────────────────────────────────────────

def _fire_webhooks(user_id, event, payload):
    """Fire webhooks for a user event in a background thread."""
    import threading, hmac, hashlib, time
    import requests as _req

    def _send():
        from database import get_active_webhooks
        hooks = get_active_webhooks(user_id, event)
        for hook in (hooks or []):
            try:
                body = json.dumps({"event": event, "timestamp": int(time.time()), "data": payload})
                headers = {"Content-Type": "application/json", "X-Lexara-Event": event}
                if hook.get("secret"):
                    sig = hmac.new(hook["secret"].encode(), body.encode(), hashlib.sha256).hexdigest()
                    headers["X-Lexara-Signature"] = f"sha256={sig}"
                _req.post(hook["url"], data=body, headers=headers, timeout=5)
            except Exception as e:
                print(f"[Webhook] Failed to fire {hook['url']}: {e}")

    threading.Thread(target=_send, daemon=True).start()


# ── Webhook management routes ──────────────────────────────────────

@app.route("/api/webhooks", methods=["GET"])
@require_auth
def list_webhooks(current_user):
    from database import get_user_webhooks
    return jsonify({"webhooks": get_user_webhooks(current_user["id"])})

@app.route("/api/webhooks", methods=["POST"])
@require_auth
def create_webhook_route(current_user):
    from database import create_webhook
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    if not url or not url.startswith("http"):
        return jsonify({"error": "Valid URL required"}), 400
    events = data.get("events", "document_uploaded,query_made")
    secret = data.get("secret", "")
    hook = create_webhook(current_user["id"], url, events, secret)
    return jsonify({"webhook": hook})

@app.route("/api/webhooks/<int:hook_id>", methods=["DELETE"])
@require_auth
def delete_webhook_route(current_user, hook_id):
    from database import delete_webhook
    delete_webhook(hook_id, current_user["id"])
    return jsonify({"message": "Deleted"})

@app.route("/api/webhooks/test/<int:hook_id>", methods=["POST"])
@require_auth
def test_webhook(current_user, hook_id):
    _fire_webhooks(current_user["id"], "test", {"message": "Webhook test from Lexara AI"})
    return jsonify({"message": "Test event fired"})


# ── Notion ingestion ───────────────────────────────────────────────

@app.route("/api/ingest/notion", methods=["POST"])
@require_auth
def ingest_notion(current_user):
    """Ingest a public Notion page by fetching its readable content."""
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    if not url or "notion.so" not in url:
        return jsonify({"error": "Valid Notion URL required"}), 400
    try:
        added, total = rag.ingest_url(current_user["id"], url)
        from database import add_document
        add_document(current_user["id"], url[:100], f"Notion: {url[:60]}", 0, "notion", 1, total)
        _fire_webhooks(current_user["id"], "document_uploaded",
                       {"source": "notion", "url": url, "chunks": added})
        return jsonify({"message": f"Indexed {added} chunks from Notion page", "chunks": added})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True, use_reloader=False)