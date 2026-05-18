"""
AirWatch Barranquilla — Backend API
Punto de entrada de la aplicación FastAPI.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.config import settings
from app.routers import sensor, predictions
from app.services.model import model_service


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 AirWatch Barranquilla iniciando...")
    logger.info("📡 Dispositivo Smart Citizen: %s", settings.smart_citizen_device_id)
    logger.info("🌐 Smart Citizen API: %s", settings.smart_citizen_base_url)

    yield
    logger.info("🛑 API detenida.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="API Calidad del Aire — Barranquilla",
    version="1.0.0",
    description=(
        "Backend para monitoreo de calidad del aire con sensor Smart Citizen Kit "
        "y predicciones XGBoost. Datos en tiempo real de Barranquilla, Colombia."
    ),
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": f"HTTP_{exc.status_code}",
            "message": exc.detail,
            "detail": str(request.url),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Los datos de entrada no son válidos",
            "detail": [
                f"Campo '{'.'.join(str(loc) for loc in e['loc'])}': {e['msg']}"
                for e in errors
            ],
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error("Error no controlado en %s: %s", request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "Error interno del servidor",
            "detail": None,
        },
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(sensor.router, prefix="/api/v1/sensor")
app.include_router(predictions.router, prefix="/api/v1/predictions")


# ---------------------------------------------------------------------------
# Root endpoints
# ---------------------------------------------------------------------------
@app.get("/", tags=["General"])
async def root():
    return {
        "status": "ok",
        "message": "API Calidad del Aire Barranquilla",
        "docs": "/docs",
        "version": "1.0.0",
    }


@app.get("/health", tags=["General"])
async def health():
    return {
        "status": "healthy",
        "environment": settings.app_env,
        "device_id": settings.smart_citizen_device_id,
    }