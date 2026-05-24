"""Persistencia de lecturas del sensor en Supabase (tabla sensor_readings)."""

import logging
from typing import Optional

from supabase import Client, create_client

from app.config import settings
from app.schemas.sensor import DeviceStatus

logger = logging.getLogger("supabase_db")

_client: Optional[Client] = None


SENSOR_ID_TO_COLUMN: dict[int, str] = {
    10: "battery",
    87: "pm_25",
    88: "pm_10",
    89: "pm_1",
    165: "pn_03",
    166: "pn_05",
    167: "pn_1",
    168: "pn_25",
    169: "pn_5",
    170: "pn_10",
}

NORMALIZED_NAME_TO_COLUMN: dict[str, str] = {
    "battery": "battery",
    "batterysck": "battery",
    "pm1": "pm_1",
    "pm25": "pm_25",
    "pm10": "pm_10",
    "pn03": "pn_03",
    "pn05": "pn_05",
    "pn1": "pn_1",
    "pn25": "pn_25",
    "pn5": "pn_5",
    "pn10": "pn_10",
}


def _normalize_sensor_name(name: str) -> str:
    tokens = name.strip().lower().split()
    cleaned = []
    for tok in tokens:
        if tok.endswith(".0"):
            tok = tok[:-2]
        cleaned.append(tok.replace(".", ""))
    return "".join(cleaned)


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
    return _client


def build_reading_from_device(device: DeviceStatus) -> Optional[dict]:
    recorded_at = next(
        (s.recorded_at for s in device.sensors if s.recorded_at is not None),
        None,
    ) or device.last_reading_at

    if recorded_at is None:
        return None

    row: dict = {"recorded_at": recorded_at.isoformat()}

    for s in device.sensors:
        col = SENSOR_ID_TO_COLUMN.get(s.sensor_id)
        if col is None:
            col = NORMALIZED_NAME_TO_COLUMN.get(_normalize_sensor_name(s.name))
        if col is None or s.value is None:
            continue
        row[col] = int(s.value) if col == "battery" else s.value

    return row


def insert_sensor_reading(reading: dict) -> None:
    # Try/except amplio: la persistencia es side-effect del endpoint /sensor/current.
    # Si Supabase falla (red, auth, rate limit), el frontend debe seguir recibiendo
    # la lectura en vivo. No relanzar la excepción.
    try:
        client = get_client()
        (
            client.table("sensor_readings")
            .upsert(reading, on_conflict="recorded_at", ignore_duplicates=True)
            .execute()
        )
    except Exception as exc:
        logger.warning("Supabase insert falló: %s", exc)
