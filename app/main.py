from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import time
import logging

from app.config import settings
from app.core.limiter import limiter
from app.routes import auth, users, opportunities, applications, documents, ai_coach, organizations

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
async def security_and_timing(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    ms = round((time.time() - start) * 1000, 2)
    response.headers["X-Process-Time"]          = f"{ms}ms"
    response.headers["X-Content-Type-Options"]  = "nosniff"
    response.headers["X-Frame-Options"]         = "DENY"
    response.headers["Referrer-Policy"]         = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]      = "geolocation=(), microphone=(), camera=()"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
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
    logger.info(f"OpportuLink API v2.0.0 — {settings.environment}")

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "environment": settings.environment, "version": "2.0.0"}

@app.get("/", tags=["System"])
async def root():
    return {"message": "OpportuLink API v2.0.0", "docs": "/docs"}

app.include_router(auth.router,          prefix="/api/v1/auth",          tags=["Auth"])
app.include_router(users.router,         prefix="/api/v1/users",         tags=["Users"])
app.include_router(opportunities.router, prefix="/api/v1/opportunities", tags=["Opportunities"])
app.include_router(applications.router,  prefix="/api/v1/applications",  tags=["Applications"])
app.include_router(documents.router,     prefix="/api/v1/documents",     tags=["Documents"])
app.include_router(ai_coach.router,      prefix="/api/v1/ai",            tags=["AI Coach"])
app.include_router(organizations.router, prefix="/api/v1/org",           tags=["Organizations"])


# TEMPORARY MIGRATION ENDPOINT — DELETE AFTER USE
@app.post("/admin/run-migration", tags=["Admin"])
async def run_migration(request: Request):
    secret = request.headers.get("X-Migration-Secret")
    if secret != "opportulink-migrate-2026":
        return JSONResponse(status_code=403, content={"error": "forbidden"})
    
    from app.database import engine
    from sqlalchemy import text
    results = []
    
    statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS target_countries VARCHAR[]",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_types VARCHAR[]",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS objective TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS availability VARCHAR",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS experiences JSONB DEFAULT '[]'::jsonb",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS certifications JSONB DEFAULT '[]'::jsonb",
    ]
    
    with engine.connect() as conn:
        conn.execute(text("SET statement_timeout = 0"))
        for sql in statements:
            conn.execute(text(sql))
            results.append(f"OK: {sql[:50]}")
        conn.commit()
    
    return {"status": "done", "results": results}
