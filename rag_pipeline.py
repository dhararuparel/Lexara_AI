"""
RAG Pipeline � per-user FAISS stores + Gemini streaming + smart features.
"""

import os
import re
import pickle
import numpy as np
from typing import List, Dict, Any, Optional, Tuple

# Heavy imports deferred to first use for fast server startup
_faiss = None
_genai = None
_embed_texts = None
_embed_query = None

def _get_faiss():
    global _faiss
    if _faiss is None:
        import faiss as _f
        _faiss = _f
    return _faiss

def _get_genai():
    global _genai
    if _genai is None:
        from google import genai as _g
        _genai = _g
    return _genai

def embed_texts(texts, normalize=True):
    global _embed_texts
    if _embed_texts is None:
        from embeddings import embed_texts as _et
        _embed_texts = _et
    return _embed_texts(texts, normalize)

def embed_query(query, normalize=True):
    global _embed_query
    if _embed_query is None:
        from embeddings import embed_query as _eq
        _embed_query = _eq
    return _embed_query(query, normalize)

VECTOR_STORE_DIR = "vector_store"
os.makedirs(VECTOR_STORE_DIR, exist_ok=True)

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

# Use HNSW index for faster approximate search (better for large datasets)
USE_HNSW = True
HNSW_M = 32  # number of connections per layer
HNSW_EF_CONSTRUCTION = 200  # quality of index construction
HNSW_EF_SEARCH = 64  # quality of search


def _index_path(user_id: int):
    return os.path.join(VECTOR_STORE_DIR, f"user_{user_id}.faiss")

def _meta_path(user_id: int):
    return os.path.join(VECTOR_STORE_DIR, f"user_{user_id}.pkl")


class RAGPipeline:
    def __init__(self, gemini_api_key: str):
        self._gemini_api_key = gemini_api_key
        self._client = None
        # Cache: user_id -> {index, metadata}
        self._cache: Dict[int, Dict] = {}

    @property
    def client(self):
        if self._client is None:
            self._client = _get_genai().Client(api_key=self._gemini_api_key)
        return self._client

    # -- Per-user store ---------------------------------------------

    def _load(self, user_id: int) -> Dict:
        if user_id in self._cache:
            return self._cache[user_id]
        store = {"index": None, "metadata": []}
        ip, mp = _index_path(user_id), _meta_path(user_id)

        if os.path.exists(ip) and os.path.exists(mp):
            try:
                index = _get_faiss().read_index(ip)
                with open(mp, "rb") as f:
                    metadata = pickle.load(f)

                # Dimension guard � re-embed if model changed
                from embeddings import get_model, get_embedding_dimension
                expected_dim = get_embedding_dimension()
                if index.d != expected_dim and metadata:
                    print(f"[RAG] Dim mismatch user {user_id}: {index.d}?{expected_dim}, re-embedding�")
                    from embeddings import embed_batch
                    vectors = embed_batch([c["text"] for c in metadata])
                    index = self._new_index(expected_dim)
                    index.add(vectors)

                store["index"] = index
                store["metadata"] = metadata
                self._cache[user_id] = store
                return store
            except Exception as e:
                print(f"[RAG] FAISS load failed for user {user_id}: {e}, restoring from DB�")

        # FAISS files missing or corrupt � rebuild from DB chunk store
        try:
            from database import load_chunks
            metadata = load_chunks(user_id)
            if metadata:
                print(f"[RAG] Rebuilding index for user {user_id} from {len(metadata)} DB chunks�")
                from embeddings import embed_batch, get_model
                vectors = embed_batch([c["text"] for c in metadata])
                dim = get_model().get_embedding_dimension()
                index = self._new_index(dim)
                index.add(vectors)
                store["index"] = index
                store["metadata"] = metadata
                self._cache[user_id] = store
                self._save(user_id)
                print(f"[RAG] Rebuild complete for user {user_id}.")
                return store
        except Exception as e:
            print(f"[RAG] DB restore failed for user {user_id}: {e}")

        self._cache[user_id] = store
        return store

    def _new_index(self, dim: int):
        if USE_HNSW:
            idx = _get_faiss().IndexHNSWFlat(dim, HNSW_M)
            idx.hnsw.efConstruction = HNSW_EF_CONSTRUCTION
            idx.hnsw.efSearch = HNSW_EF_SEARCH
        else:
            idx = _get_faiss().IndexFlatIP(dim)
        return idx

    def _save(self, user_id: int):
        store = self._cache.get(user_id)
        if not store or store["index"] is None:
            return
        _get_faiss().write_index(store["index"], _index_path(user_id))
        with open(_meta_path(user_id), "wb") as f:
            pickle.dump(store["metadata"], f)

    def add_chunks(self, user_id: int, chunks: List[Dict]) -> int:
        if not chunks:
            return 0
        store = self._load(user_id)
        from embeddings import embed_batch
        vectors = embed_batch([c["text"] for c in chunks])
        dim = vectors.shape[1]
        if store["index"] is None:
            store["index"] = self._new_index(dim)
        store["index"].add(vectors)
        store["metadata"].extend(chunks)
        self._save(user_id)
        # Persist to DB for restart recovery
        try:
            from database import save_chunks
            save_chunks(user_id, chunks)
        except Exception as e:
            print(f"[RAG] DB chunk save failed: {e}")
        return len(chunks)

    def purge_stale_vectors(self, user_id: int):
        """Remove vectors for documents no longer in the user's DB document list."""
        try:
            from database import get_user_documents
            valid_names = {d["orig_name"] for d in get_user_documents(user_id)}
        except Exception as e:
            print(f"[RAG] purge_stale_vectors: DB error {e}")
            return
        store = self._load(user_id)
        if not store["metadata"]:
            return
        stale = {c["source"] for c in store["metadata"] if c["source"] not in valid_names}
        if not stale:
            return
        print(f"[RAG] Purging stale sources for user {user_id}: {stale}")
        for name in stale:
            self.remove_document(user_id, name)

    def remove_document(self, user_id: int, filename: str):
        """Remove all chunks for a specific document and rebuild index."""
        store = self._load(user_id)
        remaining = [c for c in store["metadata"] if c["source"] != filename]
        store["index"] = None
        store["metadata"] = []
        if remaining:
            from embeddings import embed_batch
            vectors = embed_batch([c["text"] for c in remaining])
            dim = vectors.shape[1]
            if USE_HNSW:
                index = _get_faiss().IndexHNSWFlat(dim, HNSW_M)
                index.hnsw.efConstruction = HNSW_EF_CONSTRUCTION
                index.hnsw.efSearch = HNSW_EF_SEARCH
            else:
                index = _get_faiss().IndexFlatIP(dim)
            index.add(vectors)
            store["index"] = index
            store["metadata"] = remaining
        self._save(user_id)
        # Remove from DB chunk store too
        try:
            from database import delete_chunks
            delete_chunks(user_id, filename)
        except Exception as e:
            print(f"[RAG] DB chunk delete failed: {e}")

    def clear_user(self, user_id: int):
        store = self._load(user_id)
        store["index"] = None
        store["metadata"] = []
        for p in [_index_path(user_id), _meta_path(user_id)]:
            if os.path.exists(p):
                os.remove(p)
        self._cache.pop(user_id, None)
        # Clear DB chunk store
        try:
            from database import delete_chunks
            delete_chunks(user_id)
        except Exception as e:
            print(f"[RAG] DB chunk clear failed: {e}")

    def similarity_search(self, user_id: int, query: str, k: int = 6) -> List[Dict]:
        store = self._load(user_id)
        if store["index"] is None or store["index"].ntotal == 0:
            return []
        q_vec = embed_query(query)
        k_actual = min(k, store["index"].ntotal)
        distances, indices = store["index"].search(q_vec, k_actual)
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            chunk = dict(store["metadata"][idx])
            chunk["score"] = float(dist)
            results.append(chunk)
        return results

    def clear_user(self, user_id: int):
        store = self._load(user_id)
        store["index"] = None
        store["metadata"] = []
        for p in [_index_path(user_id), _meta_path(user_id)]:
            if os.path.exists(p):
                os.remove(p)
        self._cache.pop(user_id, None)

    def get_user_stats(self, user_id: int) -> Dict:
        store = self._load(user_id)
        if not store["metadata"]:
            return {"total_chunks": 0, "documents": []}
        doc_pages: Dict[str, set] = {}
        for c in store["metadata"]:
            doc_pages.setdefault(c["source"], set()).add(c["page"])
        return {
            "total_chunks": len(store["metadata"]),
            "documents": [{"name": n, "pages": len(p)} for n, p in doc_pages.items()]
        }

    # -- Prompt / RAG -----------------------------------------------

    def build_prompt(self, user_id: int, question: str, k: int = 6) -> Tuple[Optional[List], Optional[str]]:
        chunks = self.similarity_search(user_id, question, k=k)
        if not chunks:
            return None, None

        context = "\n\n".join(
            f"[{i+1}] (Source: {c['source']}, Page {c['page']})\n{c['text']}"
            for i, c in enumerate(chunks)
        )

        prompt = f"""You are Lexara AI, a professional document intelligence assistant.

Answer the question thoroughly using ONLY the provided context. Format with markdown:
- Use **bold** for key terms and important concepts
- Use bullet points or numbered lists for multiple items
- Use ## headings for multi-section answers
- Cite sources inline as 
- If information is not in the context, clearly state that

Context from documents:
{context}

Question: {question}

Answer:"""

        seen = set()
        sources = []
        try:
            from database import get_user_documents
            user_docs = {d["orig_name"] for d in get_user_documents(user_id)}
        except Exception:
            user_docs = None
        for c in chunks:
            if user_docs is not None and c["source"] not in user_docs:
                continue
            key = (c["source"], c["page"])
            if key not in seen:
                seen.add(key)
                sources.append({"file": c["source"], "page": c["page"]})

        return sources, prompt

    def _generate(self, prompt: str) -> str:
        """Non-streaming generate with model fallback and 429 handling."""
        import time, re as _re
        # Deduplicated model list — try lite first (highest quota), then flash
        seen = set()
        models_to_try = []
        for m in [MODEL, "gemini-2.5-flash-lite", "gemini-2.5-flash"]:
            if m not in seen:
                seen.add(m)
                models_to_try.append(m)
        for model in models_to_try:
            for attempt in range(2):
                try:
                    resp = self.client.models.generate_content(model=model, contents=prompt)
                    return resp.text.strip()
                except Exception as e:
                    err = str(e)
                    if "429" in err or "RESOURCE_EXHAUSTED" in err:
                        delay_match = _re.search(r'retry in (\d+)', err)
                        wait = int(delay_match.group(1)) if delay_match else 5
                        if attempt == 0 and wait <= 30:
                            time.sleep(wait)
                            continue
                        break
                    if "503" in err or "UNAVAILABLE" in err or "overloaded" in err.lower():
                        if attempt == 0:
                            time.sleep(3)
                            continue
                        break
                    raise
        raise RuntimeError("All Gemini models are rate-limited. Please wait a moment and try again.")

    def stream_answer(self, prompt: str):
        import time, re as _re
        seen = set()
        models_to_try = []
        for m in [MODEL, "gemini-2.5-flash-lite", "gemini-2.5-flash"]:
            if m not in seen:
                seen.add(m)
                models_to_try.append(m)
        for model in models_to_try:
            for attempt in range(2):
                try:
                    for chunk in self.client.models.generate_content_stream(
                        model=model, contents=prompt
                    ):
                        if chunk.text:
                            yield chunk.text
                    return
                except Exception as e:
                    err = str(e)
                    if "429" in err or "RESOURCE_EXHAUSTED" in err:
                        delay_match = _re.search(r'retry in (\d+)', err)
                        wait = int(delay_match.group(1)) if delay_match else 5
                        if attempt == 0 and wait <= 30:
                            time.sleep(wait)
                            continue
                        break
                    if "503" in err or "UNAVAILABLE" in err or "overloaded" in err.lower():
                        if attempt == 0:
                            time.sleep(3)
                            continue
                        break
                    raise
        yield "\n\nAll Gemini models are currently rate-limited. You have exceeded your free tier quota for today. Please wait a few minutes and try again, or upgrade your plan at https://ai.google.dev"

    # -- Smart Features ---------------------------------------------

    def summarize_document(self, user_id: int, filename: str) -> str:
        store = self._load(user_id)
        chunks = [c for c in store["metadata"] if c["source"] == filename]
        if not chunks:
            return "Document not found in knowledge base."

        # Take first ~3000 words for summary
        text = " ".join(c["text"] for c in chunks[:20])[:12000]

        prompt = f"""Summarize this document in a structured way using markdown:

## ?? Document Summary

Provide:
1. **Overview** (2-3 sentences)
2. **Key Topics** (bullet list)
3. **Main Points** (5-7 bullet points)
4. **Key Takeaways** (2-3 sentences)

Document content:
{text}"""

        response = self._generate(prompt)
        return response

    def suggest_questions(self, user_id: int, filename: str = None) -> List[str]:
        store = self._load(user_id)
        if not store["metadata"]:
            return []

        chunks = store["metadata"]
        if filename:
            chunks = [c for c in chunks if c["source"] == filename]

        sample = " ".join(c["text"] for c in chunks[:10])[:6000]

        prompt = f"""Based on this document content, generate exactly 6 insightful questions a user might ask.
Return ONLY a JSON array of strings, no other text.
Example: ["Question 1?", "Question 2?"]

Content:
{sample}"""

        try:
            response = self._generate(prompt)
            text = response
            import json, re
            match = re.search(r'\[.*?\]', text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
        return []

    def suggest_questions_from_docs(self, user_id: int, doc_names: list) -> List[str]:
        """Generate suggestions ONLY from the provided current document names."""
        store = self._load(user_id)
        if not store["metadata"]:
            return []

        # Strictly filter to only current documents
        chunks = [c for c in store["metadata"] if c["source"] in doc_names]
        if not chunks:
            return []

        # Sample evenly across documents
        import random
        per_doc = max(1, 8 // len(doc_names))
        sampled = []
        for name in doc_names:
            doc_chunks = [c for c in chunks if c["source"] == name]
            sampled.extend(doc_chunks[:per_doc])

        sample = " ".join(c["text"] for c in sampled)[:6000]
        doc_list = ", ".join(doc_names)

        prompt = f"""You are helping a user explore their documents: {doc_list}

Based on the content below, generate exactly 4 specific, interesting questions the user could ask about these documents.
Questions should be directly answerable from the content.
Return ONLY a JSON array of 4 strings, nothing else.

Content:
{sample}"""

        try:
            response = self._generate(prompt)
            import json, re
            match = re.search(r'\[.*?\]', response, re.DOTALL)
            if match:
                questions = json.loads(match.group())
                return questions[:4]
        except Exception:
            pass
        return []

    def extract_key_topics(self, user_id: int, filename: str) -> str:
        store = self._load(user_id)
        chunks = [c for c in store["metadata"] if c["source"] == filename]
        if not chunks:
            return "Document not found."

        text = " ".join(c["text"] for c in chunks[:15])[:8000]

        prompt = f"""Extract and explain the key topics from this document using markdown.

## ??? Key Topics

For each topic provide a brief explanation. Format as:
**Topic Name**: Brief explanation (1-2 sentences)

Document:
{text}"""

        response = self._generate(prompt)
        return response

    # -- Query Expansion --------------------------------------------

    def expand_query(self, question: str) -> List[str]:
        """
        Generate multiple query variations to improve recall.
        Returns original + 2 paraphrases + 1 HyDE (hypothetical answer).
        """
        prompt = f"""Given this question, generate:
1. Two alternative phrasings of the same question
2. One hypothetical short answer (1-2 sentences) that would answer it

Return ONLY a JSON object with keys "paraphrases" (array of 2 strings) and "hyde" (string).

Question: {question}"""
        try:
            import json, re
            resp = self._generate(prompt)
            match = re.search(r'\{.*?\}', resp, re.DOTALL)
            if match:
                data = json.loads(match.group())
                queries = [question]
                queries.extend(data.get("paraphrases", [])[:2])
                hyde = data.get("hyde", "")
                if hyde:
                    queries.append(hyde)
                return queries
        except Exception:
            pass
        return [question]

    # -- Maximal Marginal Relevance ---------------------------------

    def mmr_select(self, query_vec: np.ndarray, chunks: List[Dict],
                   k: int = 8, lambda_mult: float = 0.6) -> List[Dict]:
        """
        MMR: balance relevance vs diversity.
        lambda_mult=1.0 ? pure relevance, 0.0 ? pure diversity.
        """
        if not chunks or len(chunks) <= k:
            return chunks

        # Get embeddings for all candidate chunks
        texts = [c["text"] for c in chunks]
        chunk_vecs = embed_texts(texts)  # already normalized

        # Compute relevance scores (cosine similarity with query)
        relevance = np.dot(chunk_vecs, query_vec.T).flatten()

        selected_indices = []
        remaining = list(range(len(chunks)))

        for _ in range(min(k, len(chunks))):
            if not remaining:
                break
            if not selected_indices:
                # First: pick most relevant
                best = max(remaining, key=lambda i: relevance[i])
            else:
                # MMR score = ? * relevance - (1-?) * max_similarity_to_selected
                sel_vecs = chunk_vecs[selected_indices]
                scores = []
                for i in remaining:
                    sim_to_selected = np.max(np.dot(sel_vecs, chunk_vecs[i]))
                    mmr_score = lambda_mult * relevance[i] - (1 - lambda_mult) * sim_to_selected
                    scores.append((i, mmr_score))
                best = max(scores, key=lambda x: x[1])[0]

            selected_indices.append(best)
            remaining.remove(best)

        return [chunks[i] for i in selected_indices]

    # -- Contextual Compression -------------------------------------

    def compress_chunks(self, question: str, chunks: List[Dict]) -> List[Dict]:
        """
        Extract only the relevant sentences from each chunk.
        Reduces noise and focuses context on what matters.
        """
        if not chunks:
            return chunks

        texts = "\n---\n".join(
            f"[{i}] {c['text'][:600]}" for i, c in enumerate(chunks)
        )
        prompt = f"""For each passage below, extract ONLY the sentences directly relevant to the question.
If a passage has no relevant content, return an empty string for it.
Return ONLY a JSON array of strings (one per passage, same order).

Question: {question}

Passages:
{texts}"""
        try:
            import json, re
            resp = self._generate(prompt)
            match = re.search(r'\[.*?\]', resp, re.DOTALL)
            if match:
                compressed = json.loads(match.group())
                result = []
                for i, c in enumerate(chunks):
                    if i < len(compressed) and compressed[i].strip():
                        new_chunk = dict(c)
                        new_chunk["text"] = compressed[i].strip()
                        result.append(new_chunk)
                    elif c.get("score", 0) > 0.3:  # keep high-relevance chunks as-is
                        result.append(c)
                return result if result else chunks
        except Exception:
            pass
        return chunks

    # -- Hybrid Search (upgraded) -----------------------------------

    def hybrid_search(self, user_id: int, query: str, k: int = 8) -> List[Dict]:
        """
        Multi-query hybrid search:
        1. Expand query into multiple variations
        2. Semantic search for each variation
        3. BM25-style keyword scoring
        4. Reciprocal Rank Fusion to merge results
        5. MMR for diversity
        """
        import re as _re

        # Step 1: Query expansion
        queries = self.expand_query(query)

        # Step 2: Semantic search for each query variation
        all_results: Dict[int, Dict] = {}  # chunk_index -> chunk
        rank_lists: List[List[int]] = []

        store = self._load(user_id)
        if store["index"] is None or store["index"].ntotal == 0:
            return []

        for q in queries:
            q_vec = embed_query(q)
            k_fetch = min(k * 3, store["index"].ntotal)
            distances, indices = store["index"].search(q_vec, k_fetch)
            rank_list = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx == -1:
                    continue
                if idx not in all_results:
                    chunk = dict(store["metadata"][idx])
                    chunk["score"] = float(dist)
                    all_results[idx] = chunk
                rank_list.append(idx)
            rank_lists.append(rank_list)

        # Step 3: BM25-style keyword boost
        query_words = set(_re.findall(r'\w+', query.lower()))
        for idx, chunk in all_results.items():
            words = set(_re.findall(r'\w+', chunk["text"].lower()))
            overlap = len(query_words & words)
            chunk["keyword_score"] = overlap

        # Step 4: Reciprocal Rank Fusion (RRF)
        rrf_k = 60
        rrf_scores: Dict[int, float] = {}
        for rank_list in rank_lists:
            for rank, idx in enumerate(rank_list):
                rrf_scores[idx] = rrf_scores.get(idx, 0) + 1.0 / (rrf_k + rank + 1)

        # Combine RRF + keyword score
        for idx in all_results:
            all_results[idx]["combined_score"] = (
                rrf_scores.get(idx, 0) * 10 +
                all_results[idx].get("keyword_score", 0) * 0.1
            )

        # Sort by combined score (higher = better)
        candidates = sorted(all_results.values(), key=lambda x: x["combined_score"], reverse=True)
        candidates = candidates[:k * 2]

        # Step 5: MMR for diversity
        q_vec = embed_query(query)
        diverse = self.mmr_select(q_vec, candidates, k=k)
        return diverse

    # -- Conversation Memory ----------------------------------------

    # -- URL Ingestion ----------------------------------------------

    def ingest_url(self, user_id: int, url: str) -> Tuple[int, int]:
        """Fetch a web page, strip HTML, chunk and index the text."""
        import urllib.request
        import html
        import re

        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode('utf-8', errors='ignore')

        # Strip scripts, styles, then all tags
        text = re.sub(r'<script[^>]*>.*?</script>', '', raw, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()[:50000]

        from pdf_processor import _chunk_text
        source_name = url[:60]
        chunks = _chunk_text(text, source_name, 1)
        added = self.add_chunks(user_id, chunks)
        return added, len(chunks)

    # -- YouTube Transcript Ingestion -------------------------------

    def ingest_youtube(self, user_id: int, url: str) -> Tuple[int, str]:
        """Fetch YouTube transcript using youtube-transcript-api and index it."""
        import re

        match = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', url)
        if not match:
            raise ValueError("Invalid YouTube URL")
        vid_id = match.group(1)

        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            api = YouTubeTranscriptApi()
            transcript_list = api.fetch(vid_id)
            segments = list(transcript_list)
            if not segments:
                raise ValueError("No transcript segments returned")
            transcript = ' '.join(s.text for s in segments)
        except ImportError:
            raise ValueError("youtube-transcript-api not installed. Run: pip install youtube-transcript-api")
        except Exception as e:
            raise ValueError(f"Could not fetch transcript: {e}")

        if not transcript.strip():
            raise ValueError("Transcript is empty � video may not have captions")

        # Get video title from YouTube page
        try:
            import urllib.request
            req = urllib.request.Request(
                f"https://www.youtube.com/watch?v={vid_id}",
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
            title_m = re.search(r'"title":"([^"]+)"', html)
            title = title_m.group(1) if title_m else vid_id
        except Exception:
            title = vid_id

        from pdf_processor import _chunk_text
        source_name = f"YouTube: {title[:50]}"
        chunks = _chunk_text(transcript, source_name, 1)
        added = self.add_chunks(user_id, chunks)
        return added, source_name


    # -- Reranker ---------------------------------------------------

    def rerank(self, query: str, chunks: List[Dict], top_k: int = 6) -> List[Dict]:
        """
        Second-pass reranker using Gemini to score relevance of each chunk.
        Falls back to hybrid score if Gemini call fails.
        """
        if not chunks:
            return chunks
        # Build a compact scoring prompt
        items = "\n".join(
            f"[{i}] {c['text'][:300]}" for i, c in enumerate(chunks[:12])
        )
        prompt = f"""Rate each passage's relevance to the query on a scale 0-10.
Return ONLY a JSON array of numbers in the same order, e.g. [8,3,7,...].

Query: {query}

Passages:
{items}"""
        try:
            import json
            resp = self._generate(prompt)
            import re
            match = re.search(r'\[[\d,\s\.]+\]', resp)
            if match:
                scores = json.loads(match.group())
                for i, c in enumerate(chunks[:len(scores)]):
                    c['rerank_score'] = scores[i]
                chunks.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)
        except Exception:
            pass  # fall back to original order
        return chunks[:top_k]

    # -- Confidence score -------------------------------------------

    def compute_confidence(self, chunks: List[Dict]) -> float:
        """
        Estimate answer confidence (0-1) from retrieval scores.
        With normalized embeddings + IP index: score is cosine similarity (0-1).
        With HNSW: score is also cosine similarity.
        """
        if not chunks:
            return 0.0
        # Take top-3 scores; cosine similarity: 1.0 = perfect, 0.0 = unrelated
        scores = [c.get("score", 0.0) for c in chunks[:3]]
        # HNSW returns inner product (= cosine for normalized vecs), range ~0-1
        avg = sum(scores) / len(scores)
        # Clamp to [0, 1]
        confidence = max(0.0, min(1.0, float(avg)))
        return round(confidence, 2)

    # -- Follow-up question suggestions ----------------------------

    def suggest_followups(self, question: str, answer: str) -> List[str]:
        """Generate 3 follow-up questions based on the Q&A exchange."""
        prompt = f"""Based on this question and answer, suggest exactly 3 concise follow-up questions the user might ask next.
Return ONLY a JSON array of 3 strings.

Question: {question}
Answer: {answer[:800]}"""
        try:
            import json, re
            resp = self._generate(prompt)
            match = re.search(r'\[.*?\]', resp, re.DOTALL)
            if match:
                qs = json.loads(match.group())
                return [q for q in qs if isinstance(q, str)][:3]
        except Exception:
            pass
        return []

    # -- Multi-document cross-referencing --------------------------

    def build_prompt_with_history(self, user_id: int, question: str,
                                   history: List[Dict], k: int = 8,
                                   mention_doc: str = None) -> Tuple[Optional[List], Optional[str], float]:
        """
        Fast, reliable RAG pipeline:
        1. Hybrid search (semantic + keyword + RRF) � no extra API calls
        2. Parent-child context expansion
        3. Cross-doc awareness
        4. Rich conversational prompt
        """
        import re as _re

        store = self._load(user_id)
        has_docs = store["index"] is not None and store["index"].ntotal > 0


        # -- Retrieval ----------------------------------------------
        chunks = []
        if has_docs:
            # Fast hybrid: semantic search + keyword boost + RRF (no Gemini calls)
            q_vec = embed_query(question)
            k_fetch = min(k * 3, store["index"].ntotal)
            distances, indices = store["index"].search(q_vec, k_fetch)

            query_words = set(_re.findall(r'\w+', question.lower()))
            candidates = {}
            for rank, (dist, idx) in enumerate(zip(distances[0], indices[0])):
                if idx == -1:
                    continue
                chunk = dict(store["metadata"][idx])
                # @mention scoping: only include chunks from the mentioned doc
                if mention_doc and chunk.get("source", "") != mention_doc:
                    continue
                chunk["score"] = float(dist)
                # Keyword boost
                words = set(_re.findall(r'\w+', chunk["text"].lower()))
                overlap = len(query_words & words)
                # RRF score (higher = better)
                chunk["rrf"] = 1.0 / (60 + rank + 1) + overlap * 0.02
                candidates[idx] = chunk

            # Sort by combined score
            sorted_chunks = sorted(candidates.values(), key=lambda x: x["rrf"], reverse=True)

            # MMR for diversity (fast, no API call)
            if len(sorted_chunks) > k:
                sorted_chunks = self.mmr_select(q_vec, sorted_chunks, k=k)
            else:
                sorted_chunks = sorted_chunks[:k]

            chunks = sorted_chunks

        # -- Parent-child expansion ---------------------------------
        expanded = []
        for c in chunks:
            ec = dict(c)
            pt = ec.get("parent_text", "")
            ec["display_text"] = pt if pt and len(pt) > len(ec["text"]) else ec["text"]
            expanded.append(ec)

        # -- Build context ------------------------------------------
        sources_seen: Dict[str, int] = {}
        for c in expanded:
            sources_seen[c["source"]] = sources_seen.get(c["source"], 0) + 1

        multi_doc = len(sources_seen) > 1
        cross_note = ""
        if multi_doc:
            cross_note = (
                f"\nThis answer may draw from multiple sources: "
                + ", ".join(sources_seen.keys()) + ".\n"
            )

        context_block = "\n\n".join(
            f"[{i+1}] Source: {c['source']} | Page {c['page']}\n{c['display_text']}"
            for i, c in enumerate(expanded)
        ) if expanded else ""

        # -- Conversation history -----------------------------------
        history_block = ""
        if history:
            recent = [m for m in history[-8:] if m["role"] in ("user", "assistant")]
            if recent:
                lines = []
                for m in recent:
                    role = "User" if m["role"] == "user" else "Assistant"
                    # Use more context — 1500 chars per message
                    lines.append(f"{role}: {m['content'][:1500]}")
                history_block = "\n\n## Conversation so far\n" + "\n\n".join(lines)


        # -- Prompt ------------------------------------------------
        if context_block:
            prompt = f"""You are Lexara AI — an AI-powered document intelligence assistant that helps users get answers from their uploaded documents.
{history_block}

## Document Context
{context_block}
{cross_note}
## Instructions
1. IMPORTANT: If the question is about Lexara AI itself (what it does, how to use it, its features, how it works), answer from your own knowledge about yourself — do NOT say "not covered in documents".
2. If this is a follow-up, use conversation history for context.
3. Use document context as primary source for questions about the uploaded documents.
4. If context is irrelevant to the question, answer from general knowledge.
5. Format clearly: paragraphs, bullet points, **bold** key terms.
6. Be direct. No filler phrases.

## Question
{question}

## Answer"""
        else:
            prompt = f"""You are Lexara AI — an AI-powered document intelligence assistant that helps users get answers from their uploaded documents.
{history_block}

## Instructions
1. IMPORTANT: If the question is about Lexara AI itself (what it does, how to use it, its features), answer from your own knowledge about yourself.
2. If this is a follow-up, use conversation history for context.
3. For general questions, answer from your knowledge.
4. Format clearly: paragraphs, bullet points, **bold** key terms.
5. Be direct.

## About Lexara AI (use this when asked about the app)
Lexara AI lets users upload documents (PDF, DOCX, TXT) and ask questions about them. Key features: document upload & indexing, AI-powered Q&A, web/YouTube ingestion, document summarization, chat export as PDF, chat sharing, team workspaces, activity feed, analytics dashboard, 2FA security, API keys for developers.

## Question
{question}

## Answer"""
        # Get the user's actual current documents to filter out stale sources
        try:
            from database import get_user_documents
            user_docs = {d["orig_name"] for d in get_user_documents(user_id)}
        except Exception:
            user_docs = None  # if DB unavailable, don't filter

        seen = set()
        sources = []
        for c in expanded:
            # Skip sources from deleted/non-existent documents
            if user_docs is not None and c["source"] not in user_docs:
                continue
            key = (c["source"], c["page"])
            if key not in seen:
                seen.add(key)
                sources.append({"file": c["source"], "page": c["page"]})

        confidence = self.compute_confidence(expanded) if expanded else 0.0
        return sources if sources else [], prompt, confidence

    # -- Document comparison ----------------------------------------

    def compare_documents(self, user_id: int, doc_a: str, doc_b: str, topic: str) -> str:
        """Compare two documents on a specific topic."""
        store = self._load(user_id)

        chunks_a = [c for c in store["metadata"] if c["source"] == doc_a][:15]
        chunks_b = [c for c in store["metadata"] if c["source"] == doc_b][:15]

        if not chunks_a:
            return f"Document '{doc_a}' not found in knowledge base."
        if not chunks_b:
            return f"Document '{doc_b}' not found in knowledge base."

        text_a = " ".join(c["text"] for c in chunks_a)[:6000]
        text_b = " ".join(c["text"] for c in chunks_b)[:6000]

        prompt = f"""Compare these two documents on the topic: "{topic}"

## ?? Document Comparison

**Document A:** {doc_a}
**Document B:** {doc_b}
**Topic:** {topic}

Provide a structured comparison with:
1. **Similarities** � what both documents agree on
2. **Differences** � where they diverge
3. **Document A's perspective** � key points from doc A
4. **Document B's perspective** � key points from doc B
5. **Summary verdict** � which is more comprehensive on this topic and why

---
Document A content:
{text_a}

---
Document B content:
{text_b}"""

        response = self._generate(prompt)
        return response
