import time
from pathlib import Path
from opentelemetry import trace

from app.core.exceptions import RAGException
from app.core.config import get_settings
from app.core.logging import get_logger
import app.telemetry as tel

logger = get_logger(__name__)
_tracer = trace.get_tracer("agentlens.rag")

COLLECTION_NAME = "neurograph_docs"
EMBEDDING_DIMENSION = 768

_store = None


def use_pinecone() -> bool:
    return bool(get_settings().pinecone_api_key)


def get_store():
    if _store is None:
        raise RAGException("Vector store not initialized. Call init_store() on startup.")
    return _store


def init_store() -> None:
    global _store
    settings = get_settings()

    if use_pinecone():
        from pinecone import Pinecone
        pc = Pinecone(api_key=settings.pinecone_api_key)
        index = pc.Index(settings.pinecone_index_name)
        _store = PineconeVectorStore(index)
        logger.info(f"RAG store: Pinecone — index: {settings.pinecone_index_name}")
    else:
        import chromadb
        Path(settings.chroma_path).mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=settings.chroma_path)
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        _store = ChromaVectorStore(collection)
        logger.info(f"RAG store: ChromaDB — path: {settings.chroma_path}")


class ChromaVectorStore:
    def __init__(self, collection):
        self.collection = collection

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def query(
        self,
        embedding: list[float],
        user_id: str,
        k: int = 3,
        threshold: float = 0.5,
    ) -> list[dict]:
        with _tracer.start_as_current_span("agentlens.rag.query") as span:
            span.set_attribute("rag.backend", "chroma")
            span.set_attribute("rag.query_k", k)
            span.set_attribute("rag.threshold", threshold)
            span.set_attribute("rag.user_id", user_id)

            t0 = time.perf_counter()

            count = self.collection.count()
            if count == 0:
                latency_ms = (time.perf_counter() - t0) * 1000
                span.set_attribute("rag.results_returned", 0)
                span.set_attribute("rag.latency_ms", round(latency_ms, 2))
                span.set_attribute("rag.skipped", True)
                return []

            n_results = min(k, count)
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=n_results,
                where={"user_id": {"$eq": user_id}},
                include=["documents", "metadatas", "distances"],
            )

            chunks = []
            for doc, meta, distance in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                similarity = 1 - distance
                if similarity >= threshold:
                    chunks.append({"document": doc, "metadata": meta})

            latency_ms = (time.perf_counter() - t0) * 1000

            span.set_attribute("rag.results_returned", len(chunks))
            span.set_attribute("rag.latency_ms", round(latency_ms, 2))
            span.set_attribute("rag.skipped", False)

            if tel.retrieval_latency_histogram:
                tel.retrieval_latency_histogram.record(
                    latency_ms,
                    {"rag.backend": "chroma"},
                )

            session_id = tel.current_session_id.get()
            tel.record_session_retrieval(session_id, latency_ms)

            logger.info(
                "RAG query chroma — results: %d/%d | latency: %.1fms",
                len(chunks),
                n_results,
                latency_ms,
            )

            return chunks

    def delete_by_sha256(self, sha256: str, user_id: str) -> None:
        self.collection.delete(where={"$and": [
            {"sha256": {"$eq": sha256}},
            {"user_id": {"$eq": user_id}},
        ]})

    def has_sha256(self, sha256: str, user_id: str) -> bool:
        results = self.collection.get(
            where={"$and": [
                {"sha256": {"$eq": sha256}},
                {"user_id": {"$eq": user_id}},
            ]},
            limit=1,
        )
        return len(results["ids"]) > 0


class PineconeVectorStore:
    def __init__(self, index):
        self.index = index

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        vectors = []
        for chunk_id, embedding, doc, meta in zip(ids, embeddings, documents, metadatas):
            pinecone_meta = {**meta, "text": doc}
            vectors.append({"id": chunk_id, "values": embedding, "metadata": pinecone_meta})
        self.index.upsert(vectors=vectors)

    def query(
        self,
        embedding: list[float],
        user_id: str,
        k: int = 3,
        threshold: float = 0.5,
    ) -> list[dict]:
        with _tracer.start_as_current_span("agentlens.rag.query") as span:
            span.set_attribute("rag.backend", "pinecone")
            span.set_attribute("rag.query_k", k)
            span.set_attribute("rag.threshold", threshold)
            span.set_attribute("rag.user_id", user_id)

            t0 = time.perf_counter()

            results = self.index.query(
                vector=embedding,
                top_k=k,
                filter={"user_id": {"$eq": user_id}},
                include_metadata=True,
            )

            chunks = []
            for match in results["matches"]:
                if match["score"] >= threshold:
                    meta = dict(match["metadata"])
                    text = meta.pop("text", "")
                    chunks.append({"document": text, "metadata": meta})

            latency_ms = (time.perf_counter() - t0) * 1000

            span.set_attribute("rag.results_returned", len(chunks))
            span.set_attribute("rag.latency_ms", round(latency_ms, 2))

            if tel.retrieval_latency_histogram:
                tel.retrieval_latency_histogram.record(
                    latency_ms,
                    {"rag.backend": "pinecone"},
                )

            session_id = tel.current_session_id.get()
            tel.record_session_retrieval(session_id, latency_ms)

            logger.info(
                "RAG query pinecone — results: %d | latency: %.1fms",
                len(chunks),
                latency_ms,
            )

            return chunks

    def delete_by_sha256(self, sha256: str, user_id: str) -> None:
        """
        Use Pinecone's list_paginated API to fetch chunk IDs by prefix.
        Chunk IDs are namespaced as {user_id}_{sha256}_{i}, so prefix filter is precise.
        """
        prefix = f"{user_id}_{sha256}_"
        ids_to_delete = []
        for page in self.index.list_paginated(prefix=prefix):
            ids_to_delete.extend([v.id for v in (page.vectors or [])])
        if ids_to_delete:
            self.index.delete(ids=ids_to_delete)

    def has_sha256(self, sha256: str, user_id: str) -> bool:
        """
        Use Pinecone's list_paginated API to check existence by ID prefix.
        Returns True if any chunk with this user+sha256 combination exists.
        """
        prefix = f"{user_id}_{sha256}_"
        for page in self.index.list_paginated(prefix=prefix):
            if page.vectors:
                return True
        return False