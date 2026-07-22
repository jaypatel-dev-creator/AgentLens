from pathlib import Path
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.core.exceptions import (
    NeuroGraphException,
    neurograph_exception_handler,
    generic_exception_handler,
)

from app.api.routes import chat, threads, memory, health, documents, metrics
from app.api.routes import auth
from app.db.base import engine
from app.db import models  # noqa: F401

from app.agent.graph import compile_graph
from app.rag.store import init_store
from app.telemetry import setup_telemetry, shutdown_telemetry

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    settings = get_settings()

    setup_logging(settings.app_env)
    logger.info("Starting AgentLens...")

    # SigNoz — OpenTelemetry
    setup_telemetry(
        service_name=settings.otel_service_name,
        service_version="1.0.0",
        otlp_endpoint=settings.otlp_endpoint,
        otlp_headers={"signoz-ingestion-key": settings.signoz_ingestion_key},
    )
    logger.info(f"SigNoz telemetry active — endpoint: {settings.otlp_endpoint}")

    # Tavily
    os.environ["TAVILY_API_KEY"] = settings.tavily_api_key
    logger.info("Tavily API key set.")

    # Data directories
    if not settings.database_url:
        Path(settings.sqlite_db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(settings.checkpoint_db_path).parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"SQLite mode — db: {settings.sqlite_db_path}")
        logger.info(f"Checkpoint db: {settings.checkpoint_db_path}")
    else:
        logger.info("Postgres mode — using DATABASE_URL")

    # Schema is managed by Alembic — run `alembic upgrade head` before starting.
    logger.info("Schema managed by Alembic migrations.")

    # Agent graph compilation
    compile_graph()

    # Setup LangGraph postgres checkpointer tables
    if settings.database_url:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        conn_string = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        async with AsyncPostgresSaver.from_conn_string(conn_string) as checkpointer:
            await checkpointer.setup()
        logger.info("LangGraph postgres checkpointer tables ready.")

    # RAG vector store initialization — ChromaDB local, Pinecone prod (env-driven)
    init_store()

    logger.info("AgentLens is ready.")
    yield

    # --- Shutdown ---
    await engine.dispose()
    shutdown_telemetry()
    logger.info("Shutting down AgentLens...")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="AgentLens",
        description="Observable agentic RAG — every agent decision traced in SigNoz",
        version="1.0.0",
        docs_url="/docs" if settings.app_env == "development" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    allowed_origins = [settings.frontend_url, "https://agent-lens.vercel.app"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    app.add_exception_handler(NeuroGraphException, neurograph_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Routers — auth first, then protected routes
    app.include_router(auth.router, prefix="/auth", tags=["Auth"])
    app.include_router(chat.router, prefix="/chat", tags=["Chat"])
    app.include_router(threads.router, prefix="/threads", tags=["Threads"])
    app.include_router(memory.router, prefix="/memory", tags=["Memory"])
    app.include_router(documents.router, prefix="/documents", tags=["Documents"])
    app.include_router(metrics.router, prefix="/metrics", tags=["Metrics"])
    app.include_router(health.router)

    return app


app = create_app()