"""HTTP routers."""

from fashion_search.api.chat import router as chat_router
from fashion_search.api.health import router as health_router
from fashion_search.api.search import router as search_router

__all__ = ["chat_router", "health_router", "search_router"]
