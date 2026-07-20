import asyncio
import hashlib

from google import genai
from google.genai import types
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.exceptions import RAGException
from app.rag.store import get_store

logger = get_logger(__name__)

# Constants
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_PDF_PAGES = 50
MAX_CHUNKS = 50
SUPPORTED_TYPES = {"application/pdf", "text/plain"}

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
TOP_K = 3
SIMILARITY_THRESHOLD = 0.5

# Lazily initialized on first embed call — not at import time.
# Module-level init fires before lifespan setup and before .env is validated,
# causing opaque crashes if google_api_key is missing.
_genai_client: genai.Client | None = None


def _get_genai_client() -> genai.Client:
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client(api_key=get_settings().google_api_key)
    return _genai_client


# Text splitter — safe to initialize at module level (no config dependency)
_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
)


class IngestResult:
    def __init__(self, filename, sha256, chunk_count, already_existed):
        self.filename = filename
        self.sha256 = sha256
        self.chunk_count = chunk_count
        self.already_existed = already_existed


def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def extract_text_from_pdf(content: bytes, filename: str) -> str:
    import fitz  # PyMuPDF — lazy import, only when PDF needed
    doc = fitz.open(stream=content, filetype="pdf")

    if doc.page_count > MAX_PDF_PAGES:
        raise RAGException(
            f"'{filename}' has {doc.page_count} pages — max allowed is {MAX_PDF_PAGES}.",
            status_code=422,
        )

    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()

    if not text.strip():
        raise RAGException(
            f"'{filename}' appears to be a scanned PDF with no extractable text.",
            status_code=422,
        )

    return text


def extract_text_from_txt(content: bytes, filename: str) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return content.decode("latin-1")
        except Exception as e:
            raise RAGException(f"Failed to decode '{filename}': {str(e)}", status_code=422)


def embed_texts(texts: list[str]) -> list[list[float]]:
    result = _get_genai_client().models.embed_content(
        model="gemini-embedding-001",
        contents=texts,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=768,
        ),
    )
    return [e.values for e in result.embeddings]


def embed_query(text: str) -> list[float]:
    result = _get_genai_client().models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=768,
        ),
    )
    return result.embeddings[0].values


async def ingest_file(
    content: bytes,
    filename: str,
    content_type: str,
    user_id: str,           # scopes dedup check and chunk metadata to this user
) -> IngestResult:
    # 1. Validate size and type
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise RAGException(
            f"'{filename}' exceeds the 10MB limit ({len(content) / 1024 / 1024:.1f}MB uploaded).",
            status_code=422,
        )

    if content_type not in SUPPORTED_TYPES:
        raise RAGException(
            f"'{filename}' has unsupported type '{content_type}'. Only PDF and TXT are allowed.",
            status_code=422,
        )

    # 2. SHA256 dedup — per-user: same file uploaded by two users ingests independently
    sha256 = compute_sha256(content)
    store = get_store()

    if store.has_sha256(sha256, user_id=user_id):
        logger.info(f"Duplicate detected for user {user_id} — skipping: {filename} ({sha256[:8]}...)")
        return IngestResult(
            filename=filename,
            sha256=sha256,
            chunk_count=0,
            already_existed=True,
        )

    # 3. Extract text
    if content_type == "application/pdf":
        text = extract_text_from_pdf(content, filename)
    else:
        text = extract_text_from_txt(content, filename)

    # 4. Chunk
    chunks = _splitter.split_text(text)
    if not chunks:
        raise RAGException(f"'{filename}' produced no text chunks after processing.", status_code=422)

    if len(chunks) > MAX_CHUNKS:
        raise RAGException(
            f"'{filename}' produced {len(chunks)} chunks — max allowed is {MAX_CHUNKS}. "
            f"Try a smaller or less dense file.",
            status_code=422,
        )

    logger.info(f"Chunked '{filename}' into {len(chunks)} chunks — user: {user_id}")

    # 5. Embed — offloaded to thread pool to avoid blocking the async event loop
    embeddings = await asyncio.to_thread(embed_texts, chunks)

    # 6. Write to store — user_id in metadata enables per-user filtering at query time
    chunk_ids = [f"{user_id}_{sha256}_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "sha256": sha256,
            "filename": filename,
            "chunk_index": i,
            "user_id": user_id,     # critical — enables where filter in store.query()
        }
        for i in range(len(chunks))
    ]

    store.add(
        ids=chunk_ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )

    logger.info(f"Indexed '{filename}' — {len(chunks)} chunks written — user: {user_id}")

    return IngestResult(
        filename=filename,
        sha256=sha256,
        chunk_count=len(chunks),
        already_existed=False,
    )