import logging
import sys
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
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

app.include_router(health_router, prefix="/api/v1")
app.include_router(sources_router, prefix="/api/v1")
app.include_router(raw_items_router, prefix="/api/v1")
app.include_router(alerts_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(client_alerts_router, prefix="/api/v1")
app.include_router(dashboard_router)  # No prefix — /login, /dashboard, /logout routes
app.include_router(public_alerts_router)  # No prefix — /api/alerts public feed
