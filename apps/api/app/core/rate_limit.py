"""Rate limiting (slowapi). Shared across workers when REDIS_URL is set, in-memory otherwise.

Per-route limits: `@limiter.limit("5/minute")` and add `request: Request` to the route signature.
Behind a proxy (Render), run uvicorn with --proxy-headers so the real client IP is used.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

_settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[_settings.rate_limit_default],
    storage_uri=_settings.redis_url or "memory://",
)
