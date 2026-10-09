"""FastAPI application factory."""

from fastapi import FastAPI
from uuid import uuid4
from fastapi.middleware.cors import CORSMiddleware

from fashion_search.api.chat import router as chat_router
from fashion_search.api.health import router as health_router
from fashion_search.api.products import router as products_router
from fashion_search.api.observability import router as observability_router
from fashion_search.api.search import router as search_router
from fashion_search.config.settings import get_settings
from fashion_search.core.logging import configure_logging
from fashion_search.observability.context import request_id_var


def create_app() -> FastAPI:
    """Build the API with CORS and route modules."""
    configure_logging()
    settings = get_settings()
    app = FastAPI(
        title="AI Fashion Search",
        version="0.1.0",
        description="Conversational fashion catalog search. Day 1 scaffold.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    @app.middleware("http")
    async def correlation_id(request, call_next):
        identifier = str(uuid4())
        token = request_id_var.set(identifier)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = identifier
            return response
        finally:
            request_id_var.reset(token)
    app.include_router(health_router)
    app.include_router(products_router)
    app.include_router(search_router)
    app.include_router(chat_router)
    app.include_router(observability_router)
    return app


app = create_app()
