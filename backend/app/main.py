"""
Local AI Chat — FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.telemetry.otel import setup_telemetry, instrument_fastapi
from app.db.mongodb import connect_mongodb, disconnect_mongodb
from app.db.redis_client import connect_redis, disconnect_redis
from app.mcp.base import adapter_registry
from app.mcp.kb_adapter import KnowledgeBaseAdapter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info("Starting %s v%s ...", settings.APP_NAME, settings.APP_VERSION)

    if settings.OTEL_ENABLED:
        setup_telemetry(
            service_name=settings.OTEL_SERVICE_NAME,
            service_version=settings.APP_VERSION,
            otlp_endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
        )

    await connect_mongodb()
    await connect_redis()

    # Ensure knowledge base directory exists
    Path(settings.KNOWLEDGE_BASE_DIR).mkdir(exist_ok=True)

    # Register MCP adapters
    adapter_registry.register(KnowledgeBaseAdapter())
    logger.info("MCP adapters: %s", adapter_registry.list_adapters())

    logger.info("%s ready ✓", settings.APP_NAME)
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    await disconnect_mongodb()
    await disconnect_redis()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Local AI chat with RAG knowledge base, ReAct agent, and streaming responses",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",   # invoice platform dev
        "http://localhost:3002",   # chatbot Docker
        "http://localhost:5173",   # invoice platform vite dev
        "http://localhost:5174",   # chatbot vite dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.OTEL_ENABLED:
    instrument_fastapi(app)

# ── Routers ───────────────────────────────────────────────────────────────────
from app.api.routes import auth, threads, context, knowledge_base, users
from app.api.websocket import router as ws_router

P = settings.API_PREFIX

app.include_router(auth.router,            prefix=f"{P}/auth",            tags=["Authentication"])
app.include_router(users.router,           prefix=f"{P}/users",           tags=["Users"])
app.include_router(threads.router,         prefix=f"{P}/threads",         tags=["Threads"])
app.include_router(context.router,         prefix=f"{P}",                 tags=["Context"])
app.include_router(knowledge_base.router,  prefix=f"{P}/knowledge-base",  tags=["Knowledge Base"])
app.include_router(ws_router,              prefix="/ws",                   tags=["WebSocket"])


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy", "version": settings.APP_VERSION, "service": settings.APP_NAME}


@app.get("/", tags=["Root"])
async def root():
    return JSONResponse({
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/api/docs",
        "health": "/health",
    })
