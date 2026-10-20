"""FastAPI Entrypoint for Agentic RAG over Live Data and Memory."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.config import settings
from apps.api.routes import chat, memory, traces

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("agentic_rag")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Agentic RAG Services...")
    logger.info(f"DATA_MODE = {settings.DATA_MODE}")
    logger.info(f"LLM_PROVIDER = {settings.LLM_PROVIDER}")
    yield
    logger.info("Shutting down Agentic RAG Services...")


app = FastAPI(
    title="Agentic RAG over Live Data and Memory",
    description="Enterprise Multi-Source Agentic RAG using Model Context Protocol (MCP) with live query decomposition, verification, and short/long-term memory.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for local web development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(chat.router)
app.include_router(memory.router)
app.include_router(traces.router)


@app.get("/api/health")
async def health_check():
    """Health check and active system configuration."""
    return {
        "status": "healthy",
        "data_mode": settings.DATA_MODE,
        "llm_provider": settings.LLM_PROVIDER,
        "mcp_servers": {
            "gmail": "operational",
            "notion": "operational",
            "jira": "operational",
        },
    }
