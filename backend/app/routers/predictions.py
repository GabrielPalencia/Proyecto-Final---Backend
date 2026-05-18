"""
Router: /api/v1/predictions

Endpoints:
  GET /info                 → información del modelo XGBoost
  POST /manual              → predicción manual con features
  POST /current             → predicción actual desde Smart Citizen
"""

import logging

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.schemas.prediction import (
    ModelInfoResponse,
    PredictionInput,
    PredictionOutput,
)
from app.services.model import model_service

logger = logging.getLogger("predictions_router")

router = APIRouter(tags=["Predictions"])


# ---------------------------------------------------------------------------
# GET /info
# ---------------------------------------------------------------------------

@router.get(
    "/info",
    response_model=ModelInfoResponse,
    summary="Información del modelo XGBoost",
    description=(
        "Retorna metadatos del modelo entrenado: tipo, features utilizadas, "
        "fecha de entrenamiento e importancia de features."
    ),
)
async def get_model_info() -> ModelInfoResponse:
    if not model_service.is_ready:
        raise HTTPException(
            status_code=503,
            detail="Modelo no cargado. Verifica los archivos en backend/app/models/",
        )
    return ModelInfoResponse(**model_service.get_model_info())


# ---------------------------------------------------------------------------
# POST /manual
# ---------------------------------------------------------------------------

@router.post(
    "/manual",
    response_model=PredictionOutput,
    summary="Predicción manual de PM2.5",
    description=(
        "Realiza una predicción de PM2.5 basada en valores manuales de sensores. "
        "Obtiene el historial real del sensor para calcular lag features. "
        "Requiere pm25 y pm10 como mínimo. pm1, temperature y humidity son opcionales."
    ),
)
async def predict_manual(input_data: PredictionInput) -> PredictionOutput:
    if not model_service.is_ready:
        raise HTTPException(
            status_code=503,
            detail="Modelo no cargado. Verifica los archivos en backend/app/models/",
        )
    try:
        pm25_series = await model_service.fetch_pm25_history(
            settings.smart_citizen_device_id,
            settings.smart_citizen_base_url,
        )
        result = model_service.predict_manual(input_data.model_dump(), pm25_series=pm25_series)
        return PredictionOutput(**result)
    except Exception as exc:
        logger.error("Error en predicción manual: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error interno al procesar la predicción",
        ) from exc


# ---------------------------------------------------------------------------
# POST /current
# ---------------------------------------------------------------------------

@router.post(
    "/current",
    response_model=PredictionOutput,
    summary="Predicción actual desde Smart Citizen",
    description=(
        "Obtiene lecturas actuales del sensor Smart Citizen y realiza una "
        "predicción de PM2.5 usando el histórico de 200 horas para lag features."
    ),
)
async def predict_current() -> PredictionOutput:
    if not model_service.is_ready:
        raise HTTPException(
            status_code=503,
            detail="Modelo no cargado. Verifica los archivos en backend/app/models/",
        )
    try:
        result = await model_service.predict_current(
            device_id=settings.smart_citizen_device_id,
            base_url=settings.smart_citizen_base_url,
        )
        return PredictionOutput(**result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en predicción actual: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error interno al procesar la predicción",
        ) from exc
