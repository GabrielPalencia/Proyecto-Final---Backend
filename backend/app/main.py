from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import sensor, predictions

app = FastAPI(
    title="API Calidad del Aire - Barranquilla",
    version="1.0.0",
    description=(
        "Backend para monitoreo de calidad del aire "
        "con sensor Smart Citizen Kit y predicciones XGBoost"
    ),
)

# Configuración CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoint raíz
@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "API Calidad del Aire Barranquilla",
    }


# Endpoint de salud
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "environment": settings.app_env,
    }


# Routers
app.include_router(
    sensor.router,
    prefix="/api/v1/sensor",
    tags=["Sensor"],
)

app.include_router(
    predictions.router,
    prefix="/api/v1/predictions",
    tags=["Predictions"],
)