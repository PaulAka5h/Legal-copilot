from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.router import auth_router, identity_router
from app.cases.router import router as cases_router
from app.clients.router import router as clients_router
from app.config import Settings
from app.database import create_database_engine, verify_runtime_role
from app.errors import register_exception_handlers
from app.health import router as health_router
from app.integration import include_dev2_case_routers
from app.lawyer.router import router as lawyer_router
from app.client_portal.router import router as client_portal_router
from app.cases.visibility_router import router as visibility_router
from app.logging_config import configure_logging


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
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(identity_router)
    app.include_router(clients_router)
    app.include_router(cases_router)
    app.include_router(lawyer_router)
    app.include_router(client_portal_router)
    app.include_router(visibility_router)
    include_dev2_case_routers(app)
    return app


app = create_app()
