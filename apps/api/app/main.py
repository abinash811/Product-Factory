from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.db.session import build_engine, build_session_factory, check_database
from app.core.errors import register_error_handlers
from app.core.health import register_readiness_check
from app.core.health import router as health_router
from app.core.logging import configure_logging
from app.core.rate_limit import limiter
from app.core.request_context import REQUEST_ID_HEADER, RequestContextMiddleware
from app.core.security_headers import SecurityHeadersMiddleware


def _unique_id(route: APIRoute) -> str:
    """Stable operation ids ("users-list_users") give the generated frontend client clean names."""
    return f"{route.tags[0]}-{route.name}" if route.tags else route.name


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json_logs=settings.json_logs)

    engine = build_engine(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        await engine.dispose()  # close pooled connections cleanly on shutdown

    docs = settings.docs_on
    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json" if docs else None,
        docs_url="/docs" if docs else None,
        redoc_url=None,
        generate_unique_id_function=_unique_id,
        lifespan=lifespan,
    )
    app.state.limiter = limiter
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine)
    register_readiness_check("database", lambda: check_database(engine))

    # add_middleware wraps: the LAST one added is the OUTERMOST. Order, outside to inside:
    # request context → security headers → CORS → rate limit → app.
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
        max_age=600,
    )
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.is_production)
    app.add_middleware(RequestContextMiddleware)

    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
