# app/main.py
# FastAPI application entry point — wires everything together

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import logging

from app.config import settings
from app.database import engine, Base

from app.routes import auth,users
# LOGGING SETUP

# Configures Python's built-in logger.


logging.basicConfig(
    level=logging.DEBUG if not settings.is_production else logging.WARNING,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)


# APP INSTANCE


app = FastAPI(
    title="OpportuLink API",
    description="Career development infrastructure for Cameroonian students",
    version="2.0.0",
    # Disable Swagger UI in production (security best practice)
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)



# CORS MIDDLEWARE

# CORS = Cross-Origin Resource Sharing


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,   # ["http://localhost:3000"]
    allow_credentials=True,                # Allow cookies and auth headers
    allow_methods=["*"],                   # GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],                   # Authorization, Content-Type, etc.
)


# REQUEST TIMING MIDDLEWARE

# Logs how long each request takes.


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = round((time.time() - start_time) * 1000, 2)  # in ms
    response.headers["X-Process-Time"] = f"{process_time}ms"
    logger.debug(f"{request.method} {request.url.path} — {process_time}ms")
    return response



# GLOBAL EXCEPTION HANDLER

# Catches any unhandled exception and returns a clean JSON error


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "Something went wrong. We're on it.",
        },
    )



# STARTUP EVENT

# Runs once when the server starts.

@app.on_event("startup")
async def startup_event():
    logger.info(f" OpportuLink API starting — environment: {settings.environment}")
    logger.info(f" Database: {settings.database_url[:30]}...")  # Partial URL for security
    logger.info(f" Allowed origins: {settings.origins_list}")



# SHUTDOWN EVENT

# Runs once when the server stops (Ctrl+C or Railway restart).


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("OpportuLink API shutting down...")



# HEALTH CHECK

# A simple endpoint that returns 200 OK.
# Used by Railway/Vercel to check if the app is alive.

@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "ok",
        "environment": settings.environment,
        "version": "2.0.0",
    }



# ROOT


@app.get("/", tags=["System"])
async def root():
    return {
        "message": "Welcome to OpportuLink API",
        "docs": "/docs",
        "health": "/health",
    }


# ROUTES 

app.include_router(
    auth.router,
    prefix="/api/v1/auth",
    tags=["Auth"],
)

app.include_router(
    users.router,
    prefix="/api/v1/users",
    tags=["Users"],
)