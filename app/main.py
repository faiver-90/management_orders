"""FastAPI application entrypoint."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.orders import router as orders_router
from app.core.config import settings
from app.middleware.rate_limit import RateLimitMiddleware

app = FastAPI(title=settings.app_name)

# Security: CORS protection
allowed_origins = [o.strip() for o in settings.api_cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security: rate limiting
app.add_middleware(RateLimitMiddleware)

app.include_router(auth_router)
app.include_router(orders_router)


@app.get("/healthz", tags=["meta"])
async def healthcheck() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "ok"}
