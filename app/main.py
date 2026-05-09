from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import time
import logging

from app.config import settings
from app.database import engine, Base
from app.core.limiter import limiter
from app.routes import auth, users, opportunities, applications, documents, ai_coach

logging.basicConfig(
    level=logging.DEBUG if not settings.is_production else logging.WARNING,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="OpportuLink API",
    description="Career development infrastructure for Cameroonian students",
    version="2.0.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# Rate limiter state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = round((time.time() - start_time) * 1000, 2)
    response.headers["X-Process-Time"] = f"{process_time}ms"
    logger.debug(f"{request.method} {request.url.path} — {process_time}ms")
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "message": "Something went wrong."},
    )

@app.on_event("startup")
async def startup_event():
    logger.info(f"OpportuLink API starting — {settings.environment}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("OpportuLink API shutting down...")

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "environment": settings.environment, "version": "2.0.0"}

@app.get("/", tags=["System"])
async def root():
    return {"message": "Welcome to OpportuLink API", "docs": "/docs"}

app.include_router(auth.router,          prefix="/api/v1/auth",          tags=["Auth"])
app.include_router(users.router,         prefix="/api/v1/users",         tags=["Users"])
app.include_router(opportunities.router, prefix="/api/v1/opportunities", tags=["Opportunities"])
app.include_router(applications.router,  prefix="/api/v1/applications",  tags=["Applications"])
app.include_router(documents.router,     prefix="/api/v1/documents",     tags=["Documents"])
app.include_router(ai_coach.router,      prefix="/api/v1/ai",            tags=["AI Coach"])
