"""Rate limiting (slowapi). Shared across workers when REDIS_URL is set, in-memory otherwise.

Per-route limits: `@limiter.limit("5/minute")` and add `request: Request` to the route signature.
Behind a proxy (Render), set TRUSTED_PROXY_HOPS so the real client IP is used (see client_ip).
"""

from fastapi import Request
from slowapi import Limiter

from app.core.config import get_settings

_settings = get_settings()


def client_ip(request: Request) -> str:
    """The caller's address for rate limiting, resistant to a forged X-Forwarded-For header."""
    hops: int = getattr(request.app.state, "trusted_proxy_hops", 0)
    if hops > 0:
        forwarded = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",")]
        forwarded = [p for p in forwarded if p]
        if len(forwarded) >= hops:
            return forwarded[-hops]
    return request.client.host if request.client else "unknown"


limiter = Limiter(
    key_func=client_ip,
    default_limits=[_settings.rate_limit_default],
    storage_uri=_settings.redis_url or "memory://",
)
