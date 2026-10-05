"""
FAISS Vector Store
==================
Stores document chunk embeddings and performs fast cosine-similarity search.

Architecture:
    FAISS Vector ID -> metadata_map[id] -> chunk text + document + KB metadata
    This allows the agent to trace every retrieved chunk back to its source file.

Technical details:
    - Index type  : IndexFlatIP (inner product on L2-normalised vectors = cosine similarity)
    - Embedding   : 384-dimensional float32 vectors
    - Persistence : index saved to disk as knowledge_index.faiss,
                    metadata saved as vector_metadata.json
    - KB isolation: each chunk carries a kb_id tag; search() filters by it
                    so agent_A's knowledge cannot leak into agent_B's results.

Dynamic Lifecycle & Rebuild:
    - When a document is deleted, `remove_document_vectors(doc_id)` invalidates
      all associated vectors and metadata from memory and disk.
    - `clear()` resets the index.
    - If FAISS is unavailable, falls back gracefully to pure NumPy inner product.
"""
import json
import logging
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.config import settings

logger = logging.getLogger("vector_store")

# ---------------------------------------------------------------------------
# Try to import FAISS; fall back to NumPy-only mode if unavailable
# ---------------------------------------------------------------------------
try:
    import faiss
    _FAISS_AVAILABLE = True
except ImportError:
    _FAISS_AVAILABLE = False
    logger.warning(
        "faiss-cpu not installed or failed to load. "
        "Falling back to NumPy cosine similarity search."
    )


class FAISSVectorStore:
    """
    Manages persistent FAISS (or NumPy) vector indexing, metadata mapping,
    and cosine-similarity search across knowledge base partitions.
    """

    def __init__(self, storage_dir: Optional[Path] = None, dim: int = 384):
        self.storage_dir = storage_dir or settings.VECTOR_STORE_DIR
        self.dim = dim
        self.index_path = self.storage_dir / "knowledge_index.faiss"
        self.metadata_path = self.storage_dir / "vector_metadata.json"

        # Metadata map: vector_id (int) -> chunk metadata dict
        self.metadata_map: Dict[int, Dict[str, Any]] = {}

        # In-memory vectors array (kept to allow vector rebuild & NumPy fallback)
        self._all_vectors: Optional[np.ndarray] = None

        # FAISS index (None when in NumPy fallback mode)
        self._index = None

        if _FAISS_AVAILABLE:
            self._index = faiss.IndexFlatIP(self.dim)

        self._load()

    # ------------------------------------------------------------------
    # Public Properties
    # ------------------------------------------------------------------

    @property
    def total_vectors(self) -> int:
        """Number of active vectors currently indexed."""
        return len(self.metadata_map)

    # ------------------------------------------------------------------
    # Vector Ingestion
    # ------------------------------------------------------------------

    def add_vectors(
        self, vectors: np.ndarray, metadata_list: List[Dict[str, Any]]
    ) -> List[int]:
        """
        Add a batch of L2-normalised vectors and their metadata to the index.
        Returns the list of assigned vector IDs.
        """
        if len(vectors) == 0:
            return []

        vectors = vectors.astype(np.float32)
        start_id = 0 if not self.metadata_map else max(self.metadata_map.keys()) + 1

        if self._all_vectors is None or len(self._all_vectors) == 0:
            self._all_vectors = vectors
        else:
            self._all_vectors = np.vstack([self._all_vectors, vectors])

        if _FAISS_AVAILABLE and self._index is not None:
            self._index.add(vectors)

        assigned_ids = []
        for i, meta in enumerate(metadata_list):
            vid = start_id + i
            self.metadata_map[vid] = meta
            assigned_ids.append(vid)

        self._save()
        return assigned_ids

    # ------------------------------------------------------------------
    # Vector Search
    # ------------------------------------------------------------------

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 4,
        kb_id: Optional[str] = None,
        min_score: float = 0.05,
    ) -> List[Dict[str, Any]]:
        """
        Find the most semantically similar chunks to the query vector.
        """
        if self.total_vectors == 0:
            return []

        query_vector = query_vector.reshape(1, -1).astype(np.float32)
        search_k = min(self.total_vectors, max(top_k * 4, 20))

        if _FAISS_AVAILABLE and self._index is not None and self._index.ntotal == len(self.metadata_map):
            scores_arr, indices_arr = self._index.search(query_vector, search_k)
            candidates = list(zip(scores_arr[0], indices_arr[0]))
        else:
            # High-precision fallback via in-memory vector matrix
            if self._all_vectors is None or len(self._all_vectors) == 0:
                return []
            sims = (self._all_vectors @ query_vector.T).flatten()
            valid_keys = list(self.metadata_map.keys())
            if len(valid_keys) != len(sims):
                # Align if count mismatch
                sims = sims[:len(valid_keys)]
            top_indices = np.argsort(sims)[::-1][:search_k]
            candidates = [(float(sims[idx]), valid_keys[idx]) for idx in top_indices if idx < len(valid_keys)]

        results = []
        for score, vid in candidates:
            vid = int(vid)
            if vid < 0 or vid not in self.metadata_map:
                continue
            if float(score) < min_score:
                continue

            meta = self.metadata_map[vid]
            if kb_id and meta.get("kb_id") != kb_id:
                continue

            results.append(
                {
                    "vector_id": vid,
                    "score": round(float(score), 4),
                    "chunk_id": meta.get("chunk_id"),
                    "document_id": meta.get("document_id"),
                    "kb_id": meta.get("kb_id"),
                    "filename": meta.get("filename"),
                    "chunk_index": meta.get("chunk_index"),
                    "content": meta.get("content"),
                }
            )

            if len(results) >= top_k:
                break

        return results

    # ------------------------------------------------------------------
    # Dynamic Lifecycle: Remove Document Vectors (Anti-Stale Cache)
    # ------------------------------------------------------------------

    def remove_document_vectors(self, document_id: int) -> int:
        """
        Purge all chunks and vectors belonging to a specific document.
        Ensures deleted documents can NEVER be retrieved again (Zero Stale Cache rule).
        Returns number of vectors removed.
        """
        vids_to_remove = [
            vid for vid, meta in self.metadata_map.items()
            if meta.get("document_id") == document_id
        ]

        if not vids_to_remove:
            return 0

        # Rebuild both metadata and vector rows together. FAISS returns row
        # positions, so leaving holes in metadata causes stale/wrong citations.
        remaining = [
            (vid, meta)
            for vid, meta in sorted(self.metadata_map.items())
            if vid not in vids_to_remove
        ]
        if remaining and self._all_vectors is not None:
            valid_remaining = [
                (vid, meta) for vid, meta in remaining if vid < len(self._all_vectors)
            ]
            rows = [self._all_vectors[vid] for vid, _ in valid_remaining]
            remaining = valid_remaining
            self._all_vectors = np.vstack(rows).astype(np.float32) if rows else None
        else:
            self._all_vectors = None

        self.metadata_map = {
            new_vid: meta for new_vid, (_, meta) in enumerate(remaining)
        }
        self._recompact_index()
        self._save()

        logger.info(f"Purged {len(vids_to_remove)} vectors for document_id={document_id}")
        return len(vids_to_remove)

    def _recompact_index(self):
        """Rebuild index from the remaining vectors in memory."""
        remaining_count = len(self.metadata_map)
        if _FAISS_AVAILABLE:
            self._index = faiss.IndexFlatIP(self.dim)

        if remaining_count == 0:
            self._all_vectors = None
            return

        if self._all_vectors is not None:
            if _FAISS_AVAILABLE and self._index is not None:
                self._index.add(self._all_vectors.astype(np.float32))

    # ------------------------------------------------------------------
    # Inspection & Debugging
    # ------------------------------------------------------------------

    def inspect_chunks(
        self, document_id: Optional[int] = None, kb_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return chunk metadata list for UI knowledge inspection."""
        items = []
        for vid, meta in self.metadata_map.items():
            if document_id is not None and meta.get("document_id") != document_id:
                continue
            if kb_id is not None and meta.get("kb_id") != kb_id:
                continue
            items.append({
                "vector_id": vid,
                "chunk_id": meta.get("chunk_id"),
                "document_id": meta.get("document_id"),
                "kb_id": meta.get("kb_id"),
                "filename": meta.get("filename"),
                "chunk_index": meta.get("chunk_index"),
                "snippet": meta.get("content", "")[:200] + "..." if len(meta.get("content", "")) > 200 else meta.get("content", "")
            })
        return items

    def clear(self):
        """Reset the entire index and metadata store to empty state."""
        self.metadata_map = {}
        self._all_vectors = None
        if _FAISS_AVAILABLE:
            self._index = faiss.IndexFlatIP(self.dim)
        self._save()
        logger.info("Cleared FAISS vector store.")

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self):
        """Persist index and metadata to disk."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        if _FAISS_AVAILABLE and self._index is not None:
            try:
                faiss.write_index(self._index, str(self.index_path))
            except Exception as e:
                logger.warning(f"Could not write FAISS index: {e}")

        npy_path = self.storage_dir / "knowledge_index.npy"
        if self._all_vectors is not None:
            try:
                np.save(str(npy_path), self._all_vectors)
            except Exception as e:
                logger.warning(f"Could not save numpy vectors: {e}")
        elif npy_path.exists():
            try:
                npy_path.unlink()
            except Exception as e:
                logger.warning(f"Could not remove stale numpy vectors: {e}")

        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in self.metadata_map.items()}, f, indent=2)

    def _load(self):
        """Load existing index and metadata from disk (if present)."""
        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.metadata_map = {int(k): v for k, v in data.items()}
            except Exception as e:
                logger.warning(f"Could not load vector metadata: {e}")
                self.metadata_map = {}

        npy_path = self.storage_dir / "knowledge_index.npy"
        if npy_path.exists():
            try:
                self._all_vectors = np.load(str(npy_path))
            except Exception:
                self._all_vectors = None

        # An empty metadata map must never revive stale vector rows on the
        # next upload after a clear/rebuild operation.
        if not self.metadata_map:
            self._all_vectors = None

        if _FAISS_AVAILABLE and self._index is not None:
            if self.index_path.exists():
                try:
                    self._index = faiss.read_index(str(self.index_path))
                except Exception as e:
                    logger.warning(f"Could not load FAISS index: {e}")
                    self._index = faiss.IndexFlatIP(self.dim)

            # Repair mismatched persisted state instead of silently falling
            # back to rows that no longer correspond to metadata IDs.
            if self._all_vectors is not None and self._index.ntotal != len(self.metadata_map):
                self._index = faiss.IndexFlatIP(self.dim)
                if len(self._all_vectors):
                    self._index.add(self._all_vectors.astype(np.float32))


# Global singleton instance
vector_store = FAISSVectorStore()
