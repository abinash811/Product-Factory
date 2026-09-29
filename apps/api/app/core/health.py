"""Liveness (is the process up?) and readiness (can it serve traffic?) endpoints.

Later build steps register dependency checks, e.g. `register_readiness_check("database", check_db)`.
"""

import asyncio
from collections.abc import Awaitable, Callable

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.rate_limit import limiter

log = structlog.get_logger(__name__)

ReadinessCheck = Callable[[], Awaitable[bool]]
readiness_checks: dict[str, ReadinessCheck] = {}
CHECK_TIMEOUT_SECONDS = 3

router = APIRouter(prefix="/health", tags=["health"])


def register_readiness_check(name: str, check: ReadinessCheck) -> None:
    readiness_checks[name] = check


async def _run(name: str, check: ReadinessCheck) -> bool:
    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SECONDS):
            return await check()
    except Exception:
        log.warning("readiness_check_failed", check=name, exc_info=True)
        return False


@router.get("/live")
async def live(request: Request) -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    names = list(readiness_checks)
    results = await asyncio.gather(*(_run(n, readiness_checks[n]) for n in names))
    checks = {name: ("ok" if ok else "fail") for name, ok in zip(names, results, strict=True)}
    healthy = all(results)
    return JSONResponse(
        {"status": "ok" if healthy else "unavailable", "checks": checks},
        status_code=200 if healthy else 503,
    )


# Probes must never be rate limited. slowapi ships no type hints, hence the ignore.
for _probe in (live, ready):
    limiter.exempt(_probe)  # type: ignore[no-untyped-call]
