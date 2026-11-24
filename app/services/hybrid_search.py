"""Hybrid Search Engine combining ChromaDB (Dense) and BM25 (Sparse) retrieval

with Reciprocal Rank Fusion (RRF) for technical specification compliance verification.
"""

import os
import re
import hashlib
import threading
from typing import List, Dict, Optional, Tuple, Any
import numpy as np

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from rank_bm25 import BM25Okapi

from app.config import get_settings
from app.models.schemas import DocumentChunk, KnowledgeBaseStats


class DeterministicFeatureEmbeddingFunction(EmbeddingFunction[Documents]):
    """High-performance, offline-safe deterministic dense embedding vectorizer.

    Preserves technical terms, acronyms, and alphanumeric identifiers (e.g., AES-256, IP67, K8s, 40 Gbps)
    into a normalized 384-dimensional dense vector space without requiring external model downloads.
    """

    def __init__(self, dim: int = 384):
        self.dim = dim

    @staticmethod
    def name() -> str:
        return "deterministic_feature_embedding"

    def get_config(self) -> dict:
        return {"dim": self.dim}

    @classmethod
    def build_from_config(cls, config: dict) -> "DeterministicFeatureEmbeddingFunction":
        return cls(dim=config.get("dim", 384))

    def __call__(self, input: Documents) -> Embeddings:
        embeddings: List[List[float]] = []
        for text in input:
            vec = np.zeros(self.dim, dtype=np.float32)
            if not text:
                vec[0] = 1.0
                embeddings.append(vec.tolist())
                continue

            # Tokenize into word and technical tokens (keep dashes, slashes, numbers)
            tokens = re.findall(r"[a-zA-Z0-9çğışöüÇĞİŞÖÜ\-_.]+", text.lower())
            if not tokens:
                vec[0] = 1.0
                embeddings.append(vec.tolist())
                continue

            # Hash unigrams and bigrams to capture technical phrases
            for i, token in enumerate(tokens):
                # Unigram
                h1 = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
                idx1 = h1 % self.dim
                sign1 = 1.0 if (h1 >> 4) % 2 == 0 else -1.0
                vec[idx1] += sign1 * 1.5

                # Bigram
                if i < len(tokens) - 1:
                    bigram = f"{token}_{tokens[i+1]}"
                    h2 = int(hashlib.sha256(bigram.encode("utf-8")).hexdigest(), 16)
                    idx2 = h2 % self.dim
                    sign2 = 1.0 if (h2 >> 4) % 2 == 0 else -1.0
                    vec[idx2] += sign2 * 2.0

            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            else:
                vec[0] = 1.0
            embeddings.append(vec.tolist())
        return embeddings


class OpenAIEmbeddingWrapper(EmbeddingFunction[Documents]):
    """OpenAI embedding function wrapper using text-embedding-3-small."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model

    @staticmethod
    def name() -> str:
        return "openai_embedding_wrapper"

    def get_config(self) -> dict:
        return {"model": self.model}

    def __call__(self, input: Documents) -> Embeddings:
        if not input:
            return []
        cleaned_input = [text if text and text.strip() else " " for text in input]
        response = self.client.embeddings.create(
            input=cleaned_input,
            model=self.model
        )
        return [data.embedding for data in response.data]


class OllamaEmbeddingWrapper(EmbeddingFunction[Documents]):
    """Local Ollama embedding function wrapper using nomic-embed-text or configured model."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "nomic-embed-text:latest", timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        from openai import OpenAI
        self.client = OpenAI(base_url=f"{self.base_url}/v1", api_key="ollama", timeout=timeout)

    @staticmethod
    def name() -> str:
        return "ollama_embedding_wrapper"

    def get_config(self) -> dict:
        return {"model": self.model, "base_url": self.base_url}

    def __call__(self, input: Documents) -> Embeddings:
        if not input:
            return []
        cleaned_input = [text if text and text.strip() else " " for text in input]
        response = self.client.embeddings.create(
            input=cleaned_input,
            model=self.model
        )
        return [data.embedding for data in response.data]


class HybridSearchEngine:
    """Combines ChromaDB dense vector search and BM25 sparse keyword search

    using Reciprocal Rank Fusion (RRF) and weighted linear normalization.
    """

    COLLECTION_NAME = "specmatrix_knowledge_base"

    def __init__(self):
        self.settings = get_settings()

        # Ensure vector store directory exists
        self.vector_store_dir = self.settings.VECTOR_STORE_DIR
        self.vector_store_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Embedding Function based on settings
        emb_provider = self.settings.EMBEDDING_PROVIDER.lower().strip()
        if emb_provider == "ollama":
            try:
                self.embedding_fn = OllamaEmbeddingWrapper(
                    base_url=self.settings.OLLAMA_BASE_URL,
                    model=self.settings.OLLAMA_EMBEDDING_MODEL,
                    timeout=self.settings.OLLAMA_TIMEOUT
                )
            except Exception:
                self.embedding_fn = DeterministicFeatureEmbeddingFunction()
        elif emb_provider == "openai" and self.settings.has_openai_key:
            try:
                self.embedding_fn = OpenAIEmbeddingWrapper(
                    api_key=self.settings.OPENAI_API_KEY,
                    model=self.settings.OPENAI_EMBEDDING_MODEL
                )
            except Exception:
                self.embedding_fn = DeterministicFeatureEmbeddingFunction()
        else:
            self.embedding_fn = DeterministicFeatureEmbeddingFunction()

        # Initialize ChromaDB Persistent Client
        self.chroma_client = chromadb.PersistentClient(path=str(self.vector_store_dir))
        self._collection = None

        # In-memory chunk repository for BM25 and exact retrieval
        self._lock = threading.RLock()
        self.chunks_map: Dict[str, DocumentChunk] = {}
        self.bm25: Optional[BM25Okapi] = None
        self.bm25_chunk_ids: List[str] = []

        # Load existing collection records into memory
        self._load_existing_chunks()

    @property
    def collection_name(self) -> str:
        """Dynamic collection name namespaced by embedding function to prevent dimension mismatch."""
        fn_name = getattr(self.embedding_fn, "name", lambda: "default")()
        return f"{self.COLLECTION_NAME}_{fn_name}"

    @property
    def collection(self):
        """Ensure active and valid collection reference."""
        try:
            if self._collection is not None:
                # Test if collection exists by getting count/name
                _ = self._collection.name
                return self._collection
        except Exception:
            pass

        self._collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )
        return self._collection

    TURKISH_STOPWORDS = {
        "ve", "veya", "ile", "bir", "bu", "da", "de", "ta", "te", "ki", "en", "az", "cok", "çok",
        "icin", "için", "gibi", "kadar", "daha", "olan", "olarak", "ise", "hem", "her", "tüm",
        "göre", "tarafından", "şekilde", "üzere"
    }

    TURKISH_SUFFIX_PATTERNS = [
        re.compile(r"(?:abilmektedir|ebilmektedir|maktadır|mektedir)$"),
        re.compile(r"(?:malıdırlar|melidirler|malıdır|melidir)$"),
        re.compile(r"(?:larındaki|lerindeki)$"),
        re.compile(r"(?:larında|lerinde|larını|lerini|lardan|lerden|lara|lere|ların|lerin)$"),
        re.compile(r"(?:sında|sinde|sını|sini|sından|sinden)$"),
        re.compile(r"(?:abilir|ebilir|acaktır|ecektir|mıştır|miştir)$"),
        re.compile(r"(?:lığı|liği|luğu|lüğü|lık|lik|luk|lük)$"),
        re.compile(r"(?:sal|sel)$"),
        re.compile(r"(?:dan|den|tan|ten)$"),
        re.compile(r"(?:da|de|ta|te)$"),
        re.compile(r"(?:nın|nin|nun|nün|ın|in|un|ün)$"),
        re.compile(r"(?:yı|yi|yu|yü|ı|i|u|ü)$"),
        re.compile(r"(?:ya|ye|a|e)$"),
        re.compile(r"(?:lar|ler)$"),
        re.compile(r"(?:ma|me|mak|mek)$"),
    ]

    @classmethod
    def _light_stem_tr(cls, token: str) -> str:
        w = token.lower()
        if w.endswith("ğ") or w.endswith("ğı") or w.endswith("ği") or w.endswith("ğu") or w.endswith("ğü"):
            w = re.sub(r"ğ[ıiuü]?$", "k", w)

        for pat in cls.TURKISH_SUFFIX_PATTERNS:
            if len(w) > 4 and pat.search(w):
                sub = pat.sub("", w)
                if len(sub) >= 3:
                    w = sub
                    if w.endswith("ğ"):
                        w = w[:-1] + "k"
                    break
        return w

    def _tokenize_text(self, text: str) -> List[str]:
        """Custom technical tokenizer with Turkish morphological normalization and stopword removal."""
        clean = text.lower()
        # Keep alphanumeric, hyphenated terms, and dotted numbers
        raw_tokens = re.findall(r"[a-z0-9çğışöü]+(?:[\-_./][a-z0-9çğışöü]+)*", clean)
        tokens: List[str] = []

        for t in raw_tokens:
            if t in self.TURKISH_STOPWORDS:
                continue
            if len(t) <= 1 and not t.isdigit():
                continue

            tokens.append(t)
            stem = self._light_stem_tr(t)
            if stem != t:
                tokens.append(stem)

        return tokens

    def _load_existing_chunks(self):
        """Restore BM25 corpus and chunks_map from the persistent ChromaDB collection."""
        try:
            records = self.collection.get(include=["metadatas", "documents"])
            if records and records["ids"]:
                ids = records["ids"]
                documents = records["documents"]
                metadatas = records["metadatas"]

                corpus_tokens = []
                self.bm25_chunk_ids = []
                self.chunks_map = {}

                for cid, doc, meta in zip(ids, documents, metadatas):
                    chunk = DocumentChunk(
                        chunk_id=cid,
                        doc_name=meta.get("doc_name", "Bilinmeyen"),
                        page_number=int(meta.get("page_number", 1)),
                        section_title=meta.get("section_title", ""),
                        text=doc
                    )
                    self.chunks_map[cid] = chunk
                    self.bm25_chunk_ids.append(cid)
                    corpus_tokens.append(self._tokenize_text(doc))

                if corpus_tokens:
                    self.bm25 = BM25Okapi(corpus_tokens)
        except Exception as e:
            # If collection read fails or is empty, start fresh
            self.chunks_map = {}
            self.bm25 = None
            self.bm25_chunk_ids = []

    def add_documents(self, chunks: List[DocumentChunk]):
        """Index a list of DocumentChunks into both ChromaDB and the BM25 sparse index."""
        if not chunks:
            return

        with self._lock:
            ids = [c.chunk_id for c in chunks]
            documents = [c.text for c in chunks]
            metadatas = [
                {
                    "doc_name": c.doc_name,
                    "page_number": c.page_number,
                    "section_title": c.section_title
                }
                for c in chunks
            ]

            # Upsert into ChromaDB
            self.collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )

            # Update in-memory mapping
            for chunk in chunks:
                self.chunks_map[chunk.chunk_id] = chunk

            # Rebuild BM25 index with all chunks
            self._rebuild_bm25()

    def delete_document(self, doc_name: str) -> int:
        """Delete all chunks belonging to a specific document from ChromaDB and BM25."""
        with self._lock:
            target_ids = [cid for cid, c in self.chunks_map.items() if c.doc_name == doc_name]
            if not target_ids:
                return 0
            try:
                self.collection.delete(ids=target_ids)
            except Exception:
                pass
            for cid in target_ids:
                self.chunks_map.pop(cid, None)
            self._rebuild_bm25()
            return len(target_ids)

    def _rebuild_bm25(self):
        """Reconstruct BM25 model from current in-memory chunks."""
        self.bm25_chunk_ids = list(self.chunks_map.keys())
        corpus = [self._tokenize_text(self.chunks_map[cid].text) for cid in self.bm25_chunk_ids]
        if corpus:
            self.bm25 = BM25Okapi(corpus)
        else:
            self.bm25 = None

    def clear_index(self):
        """Clear all indexed documents from ChromaDB and BM25 index."""
        with self._lock:
            try:
                records = self.collection.get()
                if records and records.get("ids"):
                    self.collection.delete(ids=records["ids"])
            except Exception:
                try:
                    self.chroma_client.delete_collection(self.collection_name)
                except Exception:
                    pass
                self._collection = None

            self.chunks_map.clear()
            self.bm25 = None
            self.bm25_chunk_ids = []

    def get_stats(self) -> KnowledgeBaseStats:
        """Get summary statistics of the indexed knowledge base."""
        with self._lock:
            total_chunks = len(self.chunks_map)
            doc_names = sorted(list({c.doc_name for c in self.chunks_map.values()}))
            return KnowledgeBaseStats(
                total_documents=len(doc_names),
                total_chunks=total_chunks,
                documents=doc_names
            )

    def search_dense(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Retrieve top chunks via ChromaDB dense cosine similarity."""
        if not self.chunks_map:
            return []

        n_results = min(top_k, len(self.chunks_map))
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                include=["distances"]
            )
        except Exception:
            return []

        dense_ranked: List[Tuple[str, float]] = []
        if results and results["ids"] and len(results["ids"][0]) > 0:
            ids = results["ids"][0]
            distances = results["distances"][0] if "distances" in results else [0.5] * len(ids)
            for cid, dist in zip(ids, distances):
                # Cosine distance in Chroma: smaller is better. Normalized score:
                score = 1.0 / (1.0 + max(0.0, float(dist)))
                dense_ranked.append((cid, score))

        return dense_ranked

    def search_sparse(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Retrieve top chunks via BM25 sparse keyword ranking."""
        if not self.bm25 or not self.bm25_chunk_ids:
            return []

        tokens = self._tokenize_text(query)
        if not tokens:
            return []

        raw_scores = self.bm25.get_scores(tokens)
        max_score = max(raw_scores) if len(raw_scores) > 0 else 0.0
        if max_score <= 0.0:
            return []

        scored_pairs = list(zip(self.bm25_chunk_ids, raw_scores))
        scored_pairs = [p for p in scored_pairs if p[1] > 0.0]
        scored_pairs.sort(key=lambda x: x[1], reverse=True)

        sparse_ranked: List[Tuple[str, float]] = []
        for cid, score in scored_pairs[:top_k]:
            norm_score = float(score) / (max_score + 1e-6) if max_score > 0 else 0.0
            sparse_ranked.append((cid, norm_score))

        return sparse_ranked

    def search(self, query: str, top_k: Optional[int] = None) -> List[DocumentChunk]:
        """Perform Hybrid Search combining Dense (ChromaDB) and Sparse (BM25)
        using Reciprocal Rank Fusion (RRF) and linear score combination.
        """
        k = top_k or self.settings.TOP_K_CHUNKS
        if not self.chunks_map:
            return []

        # Specification requirement: query top 5 dense and top 5 BM25
        dense_results = self.search_dense(query, top_k=5)
        sparse_results = self.search_sparse(query, top_k=5)

        # Reciprocal Rank Fusion (RRF) with constant 60
        RRF_K = 60.0
        w_dense = self.settings.HYBRID_VECTOR_WEIGHT
        w_sparse = self.settings.HYBRID_BM25_WEIGHT

        rrf_scores: Dict[str, float] = {}

        # Dense rank contributions
        for rank, (cid, score) in enumerate(dense_results, start=1):
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (w_dense / (RRF_K + rank)) + (score * 0.1)

        # Sparse rank contributions
        for rank, (cid, score) in enumerate(sparse_results, start=1):
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (w_sparse / (RRF_K + rank)) + (score * 0.1)

        # Sort candidate chunks by combined RRF score
        sorted_cids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        final_chunks: List[DocumentChunk] = []
        for cid, fused_score in sorted_cids[:k]:
            if cid in self.chunks_map:
                base_chunk = self.chunks_map[cid]
                # Return a copy with the calculated relevance score
                final_chunks.append(DocumentChunk(
                    chunk_id=base_chunk.chunk_id,
                    doc_name=base_chunk.doc_name,
                    page_number=base_chunk.page_number,
                    section_title=base_chunk.section_title,
                    text=base_chunk.text,
                    score=round(fused_score, 4)
                ))

        return final_chunks
