import asyncio
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.ai.structured import start_request_budget
from app.auth.router import auth_router, identity_router
from app.cases.router import router as cases_router
from app.clients.router import router as clients_router
from app.body_limit import BodySizeLimitMiddleware
from app.config import Settings
from app.database import create_database_engine, verify_runtime_role
from app.errors import register_exception_handlers
from app.health import router as health_router
from app.lawyer.router import router as lawyer_router
from app.client_portal.router import router as client_portal_router
from app.cases.visibility_router import router as visibility_router
from app.rag.search.router import router as research_router
from app.documents.router import router as documents_router
from app.facts.router import router as facts_router
from app.case_analysis.router import router as analysis_router
from app.strategy_tree.router import router as strategy_tree_router
from app.hearing_updates.router import router as hearing_updates_router
from app.logging_config import configure_logging


async def _startup_sweep(engine, minutes: int, logger) -> None:
    """Mark documents left 'processing' by a crash as failed; never blocks startup."""
    from app.documents.recovery import sweep_stuck_documents

    try:
        swept = await sweep_stuck_documents(engine, minutes)
        logger.info("documents.stuck_sweep", extra={"event": "documents.stuck_sweep", "count": swept})
    except Exception as error:
        logger.warning("documents.stuck_sweep_failed",
                       extra={"event": "documents.stuck_sweep_failed", "error_type": type(error).__name__})


async def _preload_query_embedder(logger) -> None:
    """Build the query embedder once; on failure search answers 503 later, startup goes on."""
    from app.rag.search.providers import get_query_embedder

    try:
        await asyncio.to_thread(get_query_embedder)
        logger.info("query_embedder.preloaded", extra={"event": "query_embedder.preloaded"})
    except Exception as error:  # missing model files, not the pinned build, out of memory
        logger.warning("query_embedder.preload_failed",
                       extra={"event": "query_embedder.preload_failed", "error_type": type(error).__name__})


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings()
    logger = configure_logging(app_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.session_factory = None
        if app_settings.app_env == "production" and not app_settings.mfa_encryption_key:
            raise RuntimeError("MFA_ENCRYPTION_KEY is required in production")
        if app_settings.database_url:
            engine = create_database_engine(app_settings.database_url)
            try:
                await verify_runtime_role(engine)
                if app_settings.sweep_stuck_documents_on_startup:
                    await _startup_sweep(engine, app_settings.stuck_processing_minutes, logger)
                if app_settings.preload_query_embedder:
                    await _preload_query_embedder(logger)
                app.state.session_factory = async_sessionmaker(
                    engine,
                    expire_on_commit=False,
                )
                yield
            finally:
                await engine.dispose()
        else:
            yield

    app = FastAPI(title=app_settings.app_name, debug=False, lifespan=lifespan)
    app.state.settings = app_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(app_settings.app_origin).rstrip("/")],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        incoming_id = request.headers.get("X-Request-ID", "")
        try:
            request_id = str(UUID(incoming_id)) if incoming_id else str(uuid4())
        except ValueError:
            request_id = str(uuid4())
        request.state.request_id = request_id
        start_request_budget()  # LLM calls in this request share one deadline (app.ai.structured)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        route = request.scope.get("route")
        path = getattr(route, "path", "unmatched")
        logger.info(
            "request.completed",
            extra={
                "event": "request.completed",
                "request_id": request_id,
                "method": request.method,
                "path": path,
                "status_code": response.status_code,
            },
        )
        return response

    register_exception_handlers(app)
    # Added last so it is the outermost middleware: body size is enforced before
    # routing, authentication, and multipart parsing.
    app.add_middleware(BodySizeLimitMiddleware)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(identity_router)
    app.include_router(clients_router)
    app.include_router(cases_router)
    app.include_router(lawyer_router)
    app.include_router(client_portal_router)
    app.include_router(visibility_router)
    app.include_router(research_router)
    app.include_router(documents_router)
    app.include_router(facts_router)
    app.include_router(analysis_router)
    app.include_router(strategy_tree_router)
    app.include_router(hearing_updates_router)
    return app


app = create_app()
