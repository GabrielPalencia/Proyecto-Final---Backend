from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class SensorReading(BaseModel):
    """Lectura de un sensor individual del dispositivo."""
    sensor_id: int
    name: str
    description: str
    unit: str
    value: Optional[float] = None
    prev_value: Optional[float] = None
    recorded_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DeviceLocation(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    exposure: Optional[str] = None
    elevation: Optional[float] = None


class DeviceStatus(BaseModel):
    """Estado completo del dispositivo con sus últimas lecturas."""
    device_id: int
    name: Optional[str] = None
    description: Optional[str] = None
    state: str
    last_reading_at: Optional[datetime] = None
    location: DeviceLocation
    sensors: list[SensorReading]


class HistoricalReading(BaseModel):
    """Un punto en la serie de tiempo de un sensor."""
    timestamp: datetime
    value: Optional[float] = None


class HistoricalResponse(BaseModel):
    """Respuesta completa del histórico de lecturas de un sensor."""
    device_id: int
    sensor_id: int
    sensor_name: Optional[str] = None
    unit: Optional[str] = None
    rollup: str
    function: str
    from_date: datetime
    to_date: datetime
    sample_size: int
    readings: list[HistoricalReading]