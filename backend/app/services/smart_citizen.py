"""
Servicio de integración con la API pública de Smart Citizen.

Documentación de la API: https://developer.smartcitizen.me/

Endpoints usados:
  GET /v0/devices/:id            → lecturas actuales (data.sensors[].value)
  GET /v0/devices/:id/readings   → histórico con rollup temporal
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import HTTPException

from app.config import settings
from app.schemas.sensor import (
    DeviceLocation,
    DeviceStatus,
    HistoricalReading,
    HistoricalResponse,
    SensorReading,
)

logger = logging.getLogger("smart_citizen")

# ---------------------------------------------------------------------------
# Caché en memoria
# ---------------------------------------------------------------------------
# Estructura: { key: (data, inserted_at) }
_cache: dict = {}


def _get_cached(key: str) -> Optional[object]:
    if key not in _cache:
        return None
    data, inserted_at = _cache[key]
    if datetime.now() - inserted_at < timedelta(seconds=settings.cache_ttl_seconds):
        return data
    del _cache[key]
    return None


def _set_cached(key: str, data: object) -> None:
    _cache[key] = (data, datetime.now())


# ---------------------------------------------------------------------------
# Servicio principal
# ---------------------------------------------------------------------------

class SmartCitizenService:
    """
    Cliente asíncrono para la API de Smart Citizen.
    Rate limit de la plataforma: 90 req/min (rol citizen).
    El caché en memoria reduce las llamadas para /current.
    """

    def __init__(self) -> None:
        self.base_url = settings.smart_citizen_base_url
        # httpx.AsyncClient se crea por request (no como atributo de instancia)
        # para evitar problemas con el event loop en FastAPI.

    @property
    def device_id(self) -> str:
        """Lee device_id del .env cada vez (permite cambios sin reiniciar)."""
        return settings.smart_citizen_device_id

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _make_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(10.0, connect=5.0),
            headers={"Accept": "application/json"},
        )

    def _handle_http_error(self, exc: httpx.HTTPStatusError, context: str) -> None:
        status = exc.response.status_code
        if status == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Dispositivo {self.device_id} no encontrado en Smart Citizen",
            )
        if status == 429:
            raise HTTPException(
                status_code=429,
                detail="Smart Citizen API: límite de peticiones alcanzado. Intenta en un minuto.",
            )
        logger.error("HTTP %s al %s: %s", status, context, exc.response.text[:200])
        raise HTTPException(
            status_code=502,
            detail=f"Error {status} al obtener datos de Smart Citizen ({context})",
        )

    # ------------------------------------------------------------------
    # Lecturas actuales
    # ------------------------------------------------------------------

    async def get_device_current_readings(self) -> dict:
        """
        GET /v0/devices/:id
        Retorna el JSON completo del dispositivo con las últimas lecturas
        en data.sensors[].value y data.sensors[].prev_value.
        Usa caché de settings.cache_ttl_seconds (default: 60 s).
        """
        cache_key = f"device:{self.device_id}:current"
        cached = _get_cached(cache_key)
        if cached is not None:
            logger.debug("Cache hit para %s", cache_key)
            return cached

        logger.info("Obteniendo lecturas actuales del dispositivo %s", self.device_id)
        try:
            async with self._make_client() as client:
                response = await client.get(f"/devices/{self.device_id}")
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            logger.error("Timeout al conectar con Smart Citizen API")
            raise HTTPException(
                status_code=504,
                detail="Timeout al conectar con Smart Citizen API. Verifica tu conexión.",
            )
        except httpx.HTTPStatusError as exc:
            self._handle_http_error(exc, "lecturas actuales")
        except httpx.RequestError as exc:
            logger.error("Error de red: %s", exc)
            raise HTTPException(
                status_code=502,
                detail="No se pudo conectar con Smart Citizen API",
            )

        _set_cached(cache_key, data)
        return data

    def parse_current_readings(self, device_data: dict) -> DeviceStatus:
        """
        Transforma el JSON crudo de GET /v0/devices/:id en DeviceStatus.

        Estructura relevante de la respuesta:
        {
          "id": 16320,
          "name": "...",
          "state": "has_published",
          "last_reading_at": "2024-05-01T14:30:00Z",
          "data": {
            "recorded_at": "2024-05-01T14:30:00Z",
            "location": { "latitude": ..., "longitude": ..., "city": ... },
            "sensors": [
              { "id": 87, "name": "PM 2.5", "description": "...",
                "unit": "µg/m³", "value": 18.4, "prev_value": 17.2 }
            ]
          }
        }
        """
        data_block = device_data.get("data") or {}
        raw_sensors = data_block.get("sensors") or []
        recorded_at_str = data_block.get("recorded_at")

        try:
            recorded_at = datetime.fromisoformat(
                recorded_at_str.replace("Z", "+00:00")
            ) if recorded_at_str else None
        except (ValueError, AttributeError):
            recorded_at = None

        sensors = []
        for s in raw_sensors:
            raw_value = s.get("value")
            raw_prev = s.get("prev_value")
            sensors.append(
                SensorReading(
                    sensor_id=s["id"],
                    name=s.get("name", ""),
                    description=s.get("description", ""),
                    unit=s.get("unit", ""),
                    value=float(raw_value) if raw_value is not None else None,
                    prev_value=float(raw_prev) if raw_prev is not None else None,
                    recorded_at=recorded_at,
                )
            )

        raw_location = data_block.get("location") or {}
        location = DeviceLocation(
            latitude=raw_location.get("latitude"),
            longitude=raw_location.get("longitude"),
            city=raw_location.get("city"),
            country=raw_location.get("country"),
            country_code=raw_location.get("country_code"),
            exposure=raw_location.get("exposure"),
            elevation=raw_location.get("elevation"),
        )

        last_reading_str = device_data.get("last_reading_at")
        try:
            last_reading_at = datetime.fromisoformat(
                last_reading_str.replace("Z", "+00:00")
            ) if last_reading_str else None
        except (ValueError, AttributeError):
            last_reading_at = None

        return DeviceStatus(
            device_id=device_data["id"],
            name=device_data.get("name"),
            description=device_data.get("description"),
            state=device_data.get("state", "unknown"),
            last_reading_at=last_reading_at,
            location=location,
            sensors=sensors,
        )

    # ------------------------------------------------------------------
    # Lecturas históricas
    # ------------------------------------------------------------------

    async def get_historical_readings(
        self,
        sensor_id: int,
        rollup: str,
        from_date: datetime,
        to_date: datetime,
        function: str = "avg",
    ) -> dict:
        """
        GET /v0/devices/:id/readings?sensor_id=&rollup=&from=&to=&function=

        Parámetros de rollup: 30s, 1m, 5m, 10m, 30m, 1h, 4h, 1d, 1w
        Funciones: avg, max, min, sum, count, dev, first, last

        Retorna:
        {
          "device_id": 16320,
          "sensor_id": 87,
          "rollup": "1h",
          "function": "avg",
          "from": "...", "to": "...",
          "sample_size": 168,
          "readings": [["2024-01-01T00:00:00Z", 12.5], ...]
        }
        """
        logger.info(
            "Obteniendo histórico: dispositivo=%s sensor=%s rollup=%s from=%s to=%s",
            self.device_id,
            sensor_id,
            rollup,
            from_date.isoformat(),
            to_date.isoformat(),
        )
        params = {
            "sensor_id": sensor_id,
            "rollup": rollup,
            "from": from_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": to_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "function": function,
        }
        try:
            async with self._make_client() as client:
                response = await client.get(
                    f"/devices/{self.device_id}/readings", params=params
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail="Timeout al obtener histórico de Smart Citizen API",
            )
        except httpx.HTTPStatusError as exc:
            self._handle_http_error(exc, "lecturas históricas")
        except httpx.RequestError as exc:
            logger.error("Error de red (histórico): %s", exc)
            raise HTTPException(
                status_code=502,
                detail="No se pudo conectar con Smart Citizen API",
            )

    def parse_historical_readings(
        self,
        raw: dict,
        sensor_name: Optional[str] = None,
        unit: Optional[str] = None,
    ) -> HistoricalResponse:
        """
        Transforma el JSON crudo del endpoint /readings en HistoricalResponse.
        Las lecturas vienen como array de tuplas [timestamp_str, value].
        """
        readings = []
        for pair in raw.get("readings") or []:
            ts_str, value = pair[0], pair[1] if len(pair) > 1 else None
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
            readings.append(
                HistoricalReading(
                    timestamp=ts,
                    value=float(value) if value is not None else None,
                )
            )

        def _parse_dt(s: Optional[str]) -> Optional[datetime]:
            if not s:
                return None
            try:
                return datetime.fromisoformat(s.replace("Z", "+00:00"))
            except ValueError:
                return None

        return HistoricalResponse(
            device_id=raw.get("device_id", int(self.device_id)),
            sensor_id=raw.get("sensor_id", 0),
            sensor_name=sensor_name,
            unit=unit,
            rollup=raw.get("rollup", ""),
            function=raw.get("function", "avg"),
            from_date=_parse_dt(raw.get("from")) or datetime.utcnow(),
            to_date=_parse_dt(raw.get("to")) or datetime.utcnow(),
            sample_size=raw.get("sample_size", len(readings)),
            readings=readings,
        )


# Singleton — una sola instancia para toda la app
smart_citizen_service = SmartCitizenService()