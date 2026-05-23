"""
Router: /api/v1/sensor

Endpoints:
  GET /current               → lecturas actuales del dispositivo SCK
  GET /sensors               → lista de sensores disponibles
  GET /historical/{sensor_id} → histórico de un sensor con rollup temporal
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.sensor import DeviceStatus, HistoricalResponse, SensorReading
from app.services.smart_citizen import smart_citizen_service
from app.services.supabase_db import build_reading_from_device, insert_sensor_reading

logger = logging.getLogger("sensor_router")

router = APIRouter(tags=["Sensor"])


# ---------------------------------------------------------------------------
# GET /current
# ---------------------------------------------------------------------------

@router.get(
    "/current",
    response_model=DeviceStatus,
    summary="Lecturas actuales del sensor",
    description=(
        "Retorna el estado del dispositivo y las lecturas más recientes de todos "
        "sus sensores. La respuesta se cachea 60 segundos para respetar el rate "
        "limit de Smart Citizen API (90 req/min)."
    ),
)
async def get_current_readings() -> DeviceStatus:
    raw = await smart_citizen_service.get_device_current_readings()
    device = smart_citizen_service.parse_current_readings(raw)

    try:
        row = build_reading_from_device(device)
        if row is not None:
            insert_sensor_reading(row)
    except Exception as exc:
        logger.warning("Persistencia de lectura falló: %s", exc)

    return device


# ---------------------------------------------------------------------------
# GET /sensors
# ---------------------------------------------------------------------------

@router.get(
    "/sensors",
    response_model=list[SensorReading],
    summary="Sensores disponibles en el dispositivo",
    description=(
        "Retorna la lista de sensores del dispositivo con sus IDs y metadatos. "
        "Útil para construir selectores en el frontend. Los valores actuales "
        "también se incluyen."
    ),
)
async def get_sensors() -> list[SensorReading]:
    raw = await smart_citizen_service.get_device_current_readings()
    device = smart_citizen_service.parse_current_readings(raw)
    return device.sensors


# ---------------------------------------------------------------------------
# GET /historical/{sensor_id}
# ---------------------------------------------------------------------------

VALID_ROLLUPS = {
    "30s", "1m", "5m", "10m", "30m",
    "1h", "2h", "4h", "8h",
    "1d", "1w",
}

VALID_FUNCTIONS = {"avg", "max", "min", "sum", "count", "dev", "first", "last"}


@router.get(
    "/historical/{sensor_id}",
    response_model=HistoricalResponse,
    summary="Histórico de lecturas de un sensor",
    description=(
        "Retorna la serie de tiempo de un sensor específico dentro del rango "
        "indicado. El rango máximo es 30 días. "
        "Rollup válidos: 30s, 1m, 5m, 10m, 30m, 1h, 2h, 4h, 8h, 1d, 1w. "
        "Funciones válidas: avg, max, min, sum, count, dev, first, last."
    ),
)
async def get_historical_readings(
    sensor_id: int,
    rollup: str = Query(
        default="1h",
        description="Agrupación temporal (ej: 30m, 1h, 4h, 1d)",
    ),
    from_date: Optional[datetime] = Query(
        default=None,
        description="Inicio del rango (ISO 8601). Por defecto: hace 24 horas.",
    ),
    to_date: Optional[datetime] = Query(
        default=None,
        description="Fin del rango (ISO 8601). Por defecto: ahora.",
    ),
    function: str = Query(
        default="avg",
        description="Función de agregación: avg, max, min, sum, count, dev, first, last",
    ),
) -> HistoricalResponse:
    # --- Defaults ---
    now = datetime.now(tz=timezone.utc)
    if to_date is None:
        to_date = now
    if from_date is None:
        from_date = now - timedelta(hours=24)

    # Asegurar timezone UTC para comparaciones
    if from_date.tzinfo is None:
        from_date = from_date.replace(tzinfo=timezone.utc)
    if to_date.tzinfo is None:
        to_date = to_date.replace(tzinfo=timezone.utc)

    # --- Validaciones ---
    if to_date <= from_date:
        raise HTTPException(
            status_code=400,
            detail="'to_date' debe ser posterior a 'from_date'.",
        )

    max_range = timedelta(days=30)
    if to_date - from_date > max_range:
        raise HTTPException(
            status_code=400,
            detail="El rango máximo permitido es 30 días.",
        )

    if rollup not in VALID_ROLLUPS:
        raise HTTPException(
            status_code=400,
            detail=f"Rollup '{rollup}' no válido. Usa uno de: {', '.join(sorted(VALID_ROLLUPS))}",
        )

    if function not in VALID_FUNCTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Función '{function}' no válida. Usa una de: {', '.join(sorted(VALID_FUNCTIONS))}",
        )

    # --- Obtener nombre y unidad del sensor desde las lecturas actuales ---
    # (para incluirlos en la respuesta sin un endpoint extra)
    sensor_name: Optional[str] = None
    unit: Optional[str] = None
    try:
        raw_device = await smart_citizen_service.get_device_current_readings()
        device = smart_citizen_service.parse_current_readings(raw_device)
        matched = next((s for s in device.sensors if s.sensor_id == sensor_id), None)
        if matched:
            sensor_name = matched.name
            unit = matched.unit
        else:
            logger.warning(
                "Sensor %s no encontrado en el dispositivo. Se continúa sin metadata.",
                sensor_id,
            )
    except HTTPException:
        # No bloqueamos el histórico si falla la metadata
        pass

    # --- Llamar al histórico ---
    raw_historical = await smart_citizen_service.get_historical_readings(
        sensor_id=sensor_id,
        rollup=rollup,
        from_date=from_date,
        to_date=to_date,
        function=function,
    )

    return smart_citizen_service.parse_historical_readings(
        raw=raw_historical,
        sensor_name=sensor_name,
        unit=unit,
    )