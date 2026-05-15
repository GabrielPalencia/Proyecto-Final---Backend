import os

# Set env vars before any app import so pydantic-settings finds them
os.environ.setdefault("SMART_CITIZEN_BASE_URL", "https://api.smartcitizen.me/v0")
os.environ.setdefault("SMART_CITIZEN_DEVICE_ID", "12345")

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.model import model_service

MOCK_FEATURE_COLS = [
    "hora_sin", "hora_cos", "dow_sin", "dow_cos",
    "mes_sin", "mes_cos", "fin_de_semana",
    "pm25_test_lag_1h", "pm25_test_lag_2h", "pm25_test_lag_3h",
    "pm25_test_lag_6h", "pm25_test_lag_12h", "pm25_test_lag_24h",
    "pm25_test_lag_48h", "pm25_test_lag_168h",
    "pm25_test_roll3_mean", "pm25_test_roll3_std", "pm25_test_roll3_max",
    "pm25_test_roll6_mean", "pm25_test_roll6_std", "pm25_test_roll6_max",
    "pm25_test_roll24_mean", "pm25_test_roll24_std", "pm25_test_roll24_max",
    "temperature_test_lag_1h", "humidity_test_lag_1h", "pm10_test_lag_1h",
]

MOCK_METADATA = {
    "model_type": "XGBoostRegressor",
    "fecha_entrenamiento": "2024-01-15T10:30:00Z",
    "target": "pm25_test",
}


@pytest.fixture
def mock_xgb_model():
    m = MagicMock()
    m.predict.return_value = np.array([18.5])
    return m


@pytest.fixture(autouse=True)
def setup_mock_model_service(mock_xgb_model):
    """Inject mock model into singleton before each test, restore after."""
    original = (
        model_service.model,
        model_service.feature_cols,
        model_service.metadata,
        model_service.ica_breakpoints,
    )
    model_service.model = mock_xgb_model
    model_service.feature_cols = MOCK_FEATURE_COLS
    model_service.metadata = MOCK_METADATA
    model_service.ica_breakpoints = {}
    yield
    (
        model_service.model,
        model_service.feature_cols,
        model_service.metadata,
        model_service.ica_breakpoints,
    ) = original


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def pm25_series():
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    dates = [now - timedelta(hours=200 - i) for i in range(200)]
    values = [15.0 + float(i % 10) for i in range(200)]
    return pd.Series(values, index=pd.DatetimeIndex(dates, tz="UTC"))
