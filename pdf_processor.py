"""
Document Processor — supports PDF, DOCX, TXT, MD.
Implements semantic chunking with parent-child hierarchy.
Returns (chunks, page_count, chunk_count).
"""

import os
import re
from typing import List, Dict, Tuple
import fitz  # PyMuPDF


def _clean(text: str) -> str:
    """Clean extracted text — normalize whitespace, remove non-printable chars."""
    text = re.sub(r'\r\n|\r', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)          # collapse excessive blank lines
    text = re.sub(r'[ \t]{2,}', ' ', text)           # collapse horizontal whitespace
    text = re.sub(r'[^\x20-\x7E\n]', '', text)       # strip non-ASCII
    return text.strip()


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences using simple regex."""
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    return [s.strip() for s in sentences if s.strip()]


def _semantic_chunk(text: str, source: str, page: int,
                    target_size: int = 400, overlap_sentences: int = 2) -> List[Dict]:
    """
    Sentence-aware chunking: groups sentences until target_size words,
    then overlaps by overlap_sentences for context continuity.
    Also stores a 'parent' field with a larger context window.
    """
    sentences = _split_sentences(text)
    if not sentences:
        return []

    chunks = []
    current_sents: List[str] = []
    current_words = 0

    for sent in sentences:
        word_count = len(sent.split())
        if current_words + word_count > target_size and current_sents:
            chunk_text = " ".join(current_sents)
            chunks.append({
                "text": chunk_text,
                "source": source,
                "page": page,
                "chunk_index": len(chunks),
            })
            # Overlap: keep last N sentences
            current_sents = current_sents[-overlap_sentences:]
            current_words = sum(len(s.split()) for s in current_sents)

        current_sents.append(sent)
        current_words += word_count

    if current_sents:
        chunks.append({
            "text": " ".join(current_sents),
            "source": source,
            "page": page,
            "chunk_index": len(chunks),
        })

    # Add parent context: each chunk gets a larger surrounding window
    for i, chunk in enumerate(chunks):
        start = max(0, i - 1)
        end   = min(len(chunks), i + 2)
        chunk["parent_text"] = " ".join(c["text"] for c in chunks[start:end])

    return chunks


def _chunk_text(text: str, source: str, page: int,
                chunk_size: int = 400, overlap: int = 50) -> List[Dict]:
    """
    Fallback word-based chunking (used by URL/YouTube ingestion).
    """
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        chunk_words = words[start:start + chunk_size]
        chunk_text  = " ".join(chunk_words)
        chunks.append({
            "text": chunk_text,
            "source": source,
            "page": page,
            "chunk_index": len(chunks),
            "parent_text": chunk_text,
        })
        start += chunk_size - overlap
    return chunks


def _process_pdf(filepath: str, orig_name: str) -> Tuple[List[Dict], int]:
    doc = fitz.open(filepath)
    all_chunks: List[Dict] = []

    for i, page in enumerate(doc):
        # Try text extraction first
        text = _clean(page.get_text("text"))

        # Fallback to OCR for scanned pages
        if not text or len(text) < 50:
            try:
                import pytesseract
                from PIL import Image
                import io
                pix = page.get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                text = _clean(pytesseract.image_to_string(img))
            except Exception:
                pass

        if text:
            all_chunks.extend(_semantic_chunk(text, orig_name, i + 1))

    page_count = len(doc)
    doc.close()
    return all_chunks, page_count


def _process_txt(filepath: str, orig_name: str) -> Tuple[List[Dict], int]:
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        text = _clean(f.read())
    chunks = _semantic_chunk(text, orig_name, 1)
    return chunks, 1


def _process_docx(filepath: str, orig_name: str) -> Tuple[List[Dict], int]:
    try:
        from docx import Document
        doc = Document(filepath)
        # Preserve paragraph structure
        paragraphs = [_clean(p.text) for p in doc.paragraphs if p.text.strip()]
        text = "\n\n".join(paragraphs)
        chunks = _semantic_chunk(text, orig_name, 1)
        return chunks, 1
    except ImportError:
        raise ImportError("Install python-docx: pip install python-docx")


def process_document(filepath: str, orig_name: str) -> Tuple[List[Dict], int, int]:
    """
    Returns (chunks, page_count, chunk_count).
    Each chunk has: text, source, page, chunk_index, parent_text
    """
    ext = os.path.splitext(orig_name)[1].lower()

    if ext == ".pdf":
        chunks, pages = _process_pdf(filepath, orig_name)
    elif ext in (".txt", ".md"):
        chunks, pages = _process_txt(filepath, orig_name)
    elif ext == ".docx":
        chunks, pages = _process_docx(filepath, orig_name)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    return chunks, pages, len(chunks)
