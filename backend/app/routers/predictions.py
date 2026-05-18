from fastapi import APIRouter, HTTPException

from app.schemas.prediction import ModelInfoResponse, PredictionInput, PredictionOutput
from app.services.model import model_service
from app.config import settings

router = APIRouter()


def _require_model() -> None:
    if not model_service.is_ready:
        raise HTTPException(
            status_code=503,
            detail=(
                "Modelo no disponible. "
                "Coloca los artifacts en backend/app/models/ "
                "(modelo_pm25.joblib, features.json, metadata.json, ica_breakpoints.json)"
            ),
        )


@router.post("/predict", response_model=PredictionOutput)
async def predict_manual(body: PredictionInput):
    _require_model()
    pm25_series = await model_service.fetch_pm25_history(
        settings.smart_citizen_device_id,
        settings.smart_citizen_base_url,
    )
    result = model_service.predict_manual(body.model_dump(), pm25_series=pm25_series)
    return PredictionOutput(**result)


@router.get("/current", response_model=PredictionOutput)
async def predict_current():
    _require_model()
    try:
        result = await model_service.predict_current(
            settings.smart_citizen_device_id,
            settings.smart_citizen_base_url,
        )
        return PredictionOutput(**result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Error al obtener datos del sensor: {exc}") from exc


@router.get("/model-info", response_model=ModelInfoResponse)
async def model_info():
    _require_model()
    return ModelInfoResponse(**model_service.get_model_info())
