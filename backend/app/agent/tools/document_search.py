import asyncio
import concurrent.futures
from langchain_core.tools import tool

from app.rag.ingestor import embed_query, TOP_K, SIMILARITY_THRESHOLD
from app.rag.store import get_store
from app.core.logging import get_logger

logger = get_logger(__name__)


def make_document_search_tool(user_id: str):
    @tool
    def document_search(query: str) -> str:
        """
        Search across user-uploaded documents to find relevant information.
        Only call this tool when the system context confirms documents are uploaded
        and the user is asking about their content.
        Input must be a search query string describing what to look for in the documents.
        Example: 'What are the key findings in the report?', 'summarize the contract terms'
        """
        try:
            store = get_store()

            # embed_query is sync — call it directly, no event loop gymnastics needed.
            # LangGraph calls this tool from a thread pool, so blocking here is fine.
            query_embedding = embed_query(query)

            chunks = store.query(
                embedding=query_embedding,
                user_id=user_id,
                k=TOP_K,
                threshold=SIMILARITY_THRESHOLD,
            )

            if not chunks:
                return "No relevant content found in the uploaded documents for this query."

            parts = []
            for i, chunk in enumerate(chunks):
                filename = chunk["metadata"].get("filename", "unknown")
                chunk_index = chunk["metadata"].get("chunk_index", i)
                text = chunk["document"]
                parts.append(f"[{filename}, chunk {chunk_index}]: {text}")

            return "\n\n".join(parts)

        except Exception as e:
            logger.error(f"document_search failed for user {user_id}: {str(e)}")
            return f"Document search error: {str(e)}"

    return document_search