import logging
import os
import pathlib

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.config import settings

logger = logging.getLogger(__name__)


def _warm_up_rag():
    """后台线程预热 RAG 模型和 FAISS 索引，避免首次请求阻塞。"""
    try:
        from app.rag.retriever import get_model, load_faiss_index

        logger.info("预热 SentenceTransformer 模型...")
        get_model()
        logger.info("SentenceTransformer 模型加载完成")

        logger.info("预热 FAISS 索引...")
        load_faiss_index()
        logger.info("FAISS 索引加载完成")
    except Exception:
        logger.warning("RAG 预热失败（可能索引尚未构建），跳过", exc_info=True)


def custom_generate_unique_id(route: APIRoute) -> str:
    if route.tags:
        return f"{route.tags[0]}-{route.name}"
    return route.name


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    import sentry_sdk

    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.all_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(api_router, prefix=settings.API_V1_STR)


@app.on_event("startup")
def startup_event():
    """应用启动时初始化数据库并预热 RAG 组件。"""
    import threading

    # SQLite: auto-create tables and first superuser
    # (PostgreSQL uses alembic migrations instead)
    if settings.USE_SQLITE:
        from app.core.db import Session, engine, init_db
        from app.models import SQLModel

        SQLModel.metadata.create_all(engine)
        # Create first superuser on fresh databases
        with Session(engine) as session:
            init_db(session)

    thread = threading.Thread(target=_warm_up_rag, daemon=True)
    thread.start()

# =========================
# 2. 报告静态文件
# =========================
BASE_DIR = pathlib.Path(__file__).parent

REPORTS_DIR = (BASE_DIR / "reports").resolve()
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

app.mount(
    "/static/reports",
    StaticFiles(directory=str(REPORTS_DIR)),
    name="reports",
)

UPLOADS_DIR = (BASE_DIR / "uploads").resolve()
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app.mount(
    "/static/uploads",
    StaticFiles(directory=str(UPLOADS_DIR)),
    name="uploads",
)


# =========================
# 3. 前端 dist 静态文件
# =========================
BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent

FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"

logger.debug("Frontend dist directory: %s", FRONTEND_DIST)
logger.debug("Frontend index file: %s", FRONTEND_INDEX)


if FRONTEND_DIST.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_DIST / "assets")),
        name="frontend-assets",
    )


# =========================
# 4. React Router 前端路由兜底
# =========================
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    if FRONTEND_INDEX.exists():
        return FileResponse(str(FRONTEND_INDEX))

    return {
        "detail": "前端 dist/index.html 不存在，请先在 frontend 目录执行 npm run build",
        "expected_path": str(FRONTEND_INDEX),
    }
