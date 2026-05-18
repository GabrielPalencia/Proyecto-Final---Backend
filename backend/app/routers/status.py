"""
Router: /api/v1/status

Endpoint de diagnóstico — muestra el estado real del sistema en tiempo real.
Útil para monitoreo, debugging y verificar que todos los servicios están activos.
"""

from datetime import datetime, timezone

import httpx
from fastapi import APIRouter

from app.config import settings
from app.services.model import model_service

router = APIRouter(tags=["Status"])

# Se asigna desde main.py en el lifespan (startup)
app_start_time: datetime | None = None


@router.get(
    "/status",
    summary="Diagnóstico completo del sistema",
    description=(
        "Verifica conectividad con Smart Citizen API y estado del modelo XGBoost. "
        "Úsalo para confirmar que el backend está sano antes de usar el frontend."
    ),
)
async def get_status() -> dict:
    now = datetime.now(timezone.utc)

    # ── Verificar conectividad Smart Citizen ─────────────────────────────────
    sc_reachable = False
    sc_last_check = now.isoformat()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.smart_citizen_base_url}/devices/{settings.smart_citizen_device_id}"
            )
            sc_reachable = resp.status_code == 200
    except Exception:
        sc_reachable = False

    # ── Uptime ───────────────────────────────────────────────────────────────
    uptime_seconds = (
        int((now - app_start_time).total_seconds())
        if app_start_time
        else 0
    )

    return {
        "status": "ok",
        "environment": settings.app_env,
        "services": {
            "smart_citizen_api": {
                "reachable": sc_reachable,
                "device_id": settings.smart_citizen_device_id,
                "last_check": sc_last_check,
            },
            "model": {
                "loaded": model_service.is_ready,
                "model_type": (
                    model_service.metadata.get("model_type", "XGBoostRegressor")
                    if model_service.is_ready
                    else None
                ),
                "features_count": (
                    len(model_service.feature_cols)
                    if model_service.is_ready
                    else 0
                ),
            },
        },
        "uptime_seconds": uptime_seconds,
    }
