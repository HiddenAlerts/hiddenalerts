import logging
import sys
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings

# Configure basic logging with timestamp
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Update uvicorn loggers to use the same configuration
for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
    uvicorn_logger = logging.getLogger(logger_name)
    uvicorn_logger.handlers.clear()
    uvicorn_logger.propagate = True

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    if settings.scheduler_enabled:
        from app.scheduler.jobs import scheduler, setup_scheduler
        setup_scheduler()
        scheduler.start()

    yield

    # Shutdown
    if settings.scheduler_enabled:
        from app.scheduler.jobs import scheduler
        if scheduler.running:
            scheduler.shutdown(wait=False)


app = FastAPI(
    title="HiddenAlerts",
    description="AI Fraud Intelligence Monitoring System",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS: lock to the frontend origin when ``FRONTEND_BASE_URL`` is configured,
# else stay open for the MVP public feed. POST is enabled here (not earlier
# slices) because Auth/Payment Phase 1 Slice 3 ships POST billing endpoints.
# Subscriber auth uses Authorization: Bearer (Supabase token); no cookies →
# allow_credentials stays at its False default.
_cors_origins = [settings.frontend_base_url.rstrip("/")] if settings.frontend_base_url else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Static files (dashboard CSS, JS)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Register routers
from app.api.health import router as health_router  # noqa: E402
from app.api.sources import router as sources_router  # noqa: E402
from app.api.raw_items import router as raw_items_router  # noqa: E402
from app.api.alerts import router as alerts_router  # noqa: E402
from app.api.auth import router as auth_router  # noqa: E402
from app.api.client_alerts import router as client_alerts_router  # noqa: E402
from app.api.dashboard import router as dashboard_router  # noqa: E402
from app.api.public_alerts import router as public_alerts_router  # noqa: E402
from app.api.search import router as search_router  # noqa: E402
from app.api.subscriber import router as subscriber_router  # noqa: E402
from app.api.billing import router as billing_router  # noqa: E402

app.include_router(health_router, prefix="/api/v1")
app.include_router(sources_router, prefix="/api/v1")
app.include_router(raw_items_router, prefix="/api/v1")
app.include_router(alerts_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(client_alerts_router, prefix="/api/v1")
app.include_router(subscriber_router, prefix="/api/v1")  # Supabase-authenticated paid feed
app.include_router(billing_router, prefix="/api/v1")  # Stripe checkout / portal / status
app.include_router(dashboard_router)  # No prefix — /login, /dashboard, /logout routes
app.include_router(public_alerts_router)  # No prefix — /api/alerts public feed
app.include_router(search_router)  # No prefix — /api/search/alerts public search
