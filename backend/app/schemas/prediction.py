from pydantic import BaseModel, Field
from datetime import datetime


class PredictionInput(BaseModel):
    pm25: float = Field(..., ge=0, description="PM2.5 en µg/m³")
    pm10: float = Field(..., ge=0, description="PM10 en µg/m³")
    pm1: float | None = Field(None, ge=0, description="PM1.0 en µg/m³")
    temperature: float | None = Field(None, description="Temperatura en °C")
    humidity: float | None = Field(None, ge=0, le=100, description="Humedad relativa en %")


class PredictionOutput(BaseModel):
    prediction: float
    category: str
    aqi_color: str
    timestamp: datetime
    input_features: dict
    model_version: str
    data_source: str


class ModelInfoResponse(BaseModel):
    model_type: str
    features: list[str]
    training_date: str
    feature_importances: dict
