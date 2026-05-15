import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.model import model_service


# ── AQI category mapping ──────────────────────────────────────────────────────

class TestAQICategory:
    def test_good(self):
        cat, color = model_service._aqi_category(10.0)
        assert cat == "Buena"
        assert color == "#00E400"

    def test_moderate(self):
        cat, color = model_service._aqi_category(20.0)
        assert cat == "Moderada"
        assert color == "#FFFF00"

    def test_sensitive_groups(self):
        cat, color = model_service._aqi_category(40.0)
        assert cat == "Dañina para grupos sensibles"
        assert color == "#FF7E00"

    def test_unhealthy(self):
        cat, color = model_service._aqi_category(100.0)
        assert cat == "Dañina"
        assert color == "#FF0000"

    def test_very_unhealthy(self):
        cat, color = model_service._aqi_category(200.0)
        assert cat == "Muy dañina"
        assert color == "#8F3F97"

    def test_hazardous(self):
        cat, color = model_service._aqi_category(300.0)
        assert cat == "Peligrosa"
        assert color == "#7E0023"

    def test_boundary_good_to_moderate(self):
        cat, _ = model_service._aqi_category(12.0)
        assert cat == "Buena"
        cat, _ = model_service._aqi_category(12.1)
        assert cat == "Moderada"


# ── Cyclic feature parsing ────────────────────────────────────────────────────

class TestCyclicFeatures:
    def test_midnight_hora_sin_is_zero(self):
        dt = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
        val = model_service._parse_feature("hora_sin", dt, None, {}, "pm25_test")
        assert abs(val) < 1e-10

    def test_noon_hora_cos_is_negative_one(self):
        dt = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        val = model_service._parse_feature("hora_cos", dt, None, {}, "pm25_test")
        assert abs(val + 1.0) < 1e-10

    def test_saturday_is_weekend(self):
        dt = datetime(2024, 1, 6, 10, 0, tzinfo=timezone.utc)  # Saturday
        val = model_service._parse_feature("fin_de_semana", dt, None, {}, "pm25_test")
        assert val == 1.0

    def test_monday_is_not_weekend(self):
        dt = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)  # Monday
        val = model_service._parse_feature("fin_de_semana", dt, None, {}, "pm25_test")
        assert val == 0.0

    def test_dow_sin_monday_is_zero(self):
        dt = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)  # Monday
        val = model_service._parse_feature("dow_sin", dt, None, {}, "pm25_test")
        assert abs(val) < 1e-10

    def test_mes_sin_january_is_zero(self):
        dt = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
        val = model_service._parse_feature("mes_sin", dt, None, {}, "pm25_test")
        assert abs(val) < 1e-10


# ── Lag feature parsing ───────────────────────────────────────────────────────

class TestLagFeatures:
    def test_lag_1h_returns_last_value(self, pm25_series):
        dt = datetime.now(timezone.utc)
        val = model_service._parse_feature(
            "pm25_test_lag_1h", dt, pm25_series, {}, "pm25_test"
        )
        assert val == float(pm25_series.iloc[-1])

    def test_lag_24h_returns_correct_position(self, pm25_series):
        dt = datetime.now(timezone.utc)
        val = model_service._parse_feature(
            "pm25_test_lag_24h", dt, pm25_series, {}, "pm25_test"
        )
        assert val == float(pm25_series.iloc[-24])

    def test_lag_168h_returns_oldest_available(self, pm25_series):
        dt = datetime.now(timezone.utc)
        val = model_service._parse_feature(
            "pm25_test_lag_168h", dt, pm25_series, {}, "pm25_test"
        )
        assert val == float(pm25_series.iloc[-168])

    def test_target_lag_without_series_returns_nan(self):
        dt = datetime.now(timezone.utc)
        val = model_service._parse_feature(
            "pm25_test_lag_1h", dt, None, {}, "pm25_test"
        )
        assert np.isnan(val)

    def test_exog_lag_1h_from_current_sensors(self):
        dt = datetime.now(timezone.utc)
        val = model_service._parse_feature(
            "temperature_test_lag_1h", dt, None, {"temperature": 28.5}, "pm25_test"
        )
        assert val == 28.5

    def test_exog_lag_1h_none_sensor_returns_nan(self):
        dt = datetime.now(timezone.utc)
        val = model_service._parse_feature(
            "temperature_test_lag_1h", dt, None, {"temperature": None}, "pm25_test"
        )
        assert np.isnan(val)

    def test_exog_lag_2h_returns_nan(self):
        dt = datetime.now(timezone.utc)
        val = model_service._parse_feature(
            "temperature_test_lag_2h", dt, None, {"temperature": 28.5}, "pm25_test"
        )
        assert np.isnan(val)


# ── Rolling feature parsing ───────────────────────────────────────────────────

class TestRollingFeatures:
    def test_roll3_mean_matches_last_3(self, pm25_series):
        dt = datetime.now(timezone.utc)
        val = model_service._parse_feature(
            "pm25_test_roll3_mean", dt, pm25_series, {}, "pm25_test"
        )
        assert abs(val - float(pm25_series.iloc[-3:].mean())) < 1e-10

    def test_roll6_std_matches_last_6(self, pm25_series):
        dt = datetime.now(timezone.utc)
        val = model_service._parse_feature(
            "pm25_test_roll6_std", dt, pm25_series, {}, "pm25_test"
        )
        assert abs(val - float(pm25_series.iloc[-6:].std())) < 1e-10

    def test_roll24_max_matches_last_24(self, pm25_series):
        dt = datetime.now(timezone.utc)
        val = model_service._parse_feature(
            "pm25_test_roll24_max", dt, pm25_series, {}, "pm25_test"
        )
        assert abs(val - float(pm25_series.iloc[-24:].max())) < 1e-10

    def test_rolling_without_series_returns_nan(self):
        dt = datetime.now(timezone.utc)
        val = model_service._parse_feature(
            "pm25_test_roll3_mean", dt, None, {}, "pm25_test"
        )
        assert np.isnan(val)


# ── Feature vector shape ──────────────────────────────────────────────────────

class TestBuildFeatureVector:
    def test_output_shape_matches_feature_cols(self, pm25_series):
        dt = datetime.now(timezone.utc)
        X = model_service._build_feature_vector(
            dt, pm25_series=pm25_series, current_sensors={"temperature": 28.5}
        )
        assert X.shape == (1, len(model_service.feature_cols))

    def test_unknown_feature_returns_nan(self, pm25_series):
        dt = datetime.now(timezone.utc)
        val = model_service._parse_feature(
            "totally_unknown_feature_xyz", dt, pm25_series, {}, "pm25_test"
        )
        assert np.isnan(val)


# ── predict_manual endpoint ───────────────────────────────────────────────────

class TestPredictManual:
    def test_returns_200_with_valid_input(self, client):
        resp = client.post(
            "/api/v1/predictions/predict",
            json={"pm25": 25.0, "pm10": 40.0},
        )
        assert resp.status_code == 200

    def test_response_has_required_fields(self, client):
        resp = client.post(
            "/api/v1/predictions/predict",
            json={"pm25": 25.0, "pm10": 40.0},
        )
        data = resp.json()
        assert "prediction" in data
        assert "category" in data
        assert "aqi_color" in data
        assert "timestamp" in data
        assert "data_source" in data
        assert "model_version" in data
        assert "input_features" in data

    def test_data_source_is_manual(self, client):
        resp = client.post(
            "/api/v1/predictions/predict",
            json={"pm25": 25.0, "pm10": 40.0},
        )
        assert resp.json()["data_source"] == "manual"

    def test_prediction_is_float(self, client):
        resp = client.post(
            "/api/v1/predictions/predict",
            json={"pm25": 25.0, "pm10": 40.0},
        )
        assert isinstance(resp.json()["prediction"], float)

    def test_negative_pm25_returns_422(self, client):
        resp = client.post(
            "/api/v1/predictions/predict",
            json={"pm25": -5.0, "pm10": 40.0},
        )
        assert resp.status_code == 422

    def test_missing_required_field_returns_422(self, client):
        resp = client.post(
            "/api/v1/predictions/predict",
            json={"pm25": 25.0},  # pm10 missing
        )
        assert resp.status_code == 422

    def test_503_when_model_not_ready(self, client):
        model_service.model = None
        resp = client.post(
            "/api/v1/predictions/predict",
            json={"pm25": 25.0, "pm10": 40.0},
        )
        assert resp.status_code == 503
        assert "Modelo no disponible" in resp.json()["detail"]


# ── model-info endpoint ───────────────────────────────────────────────────────

class TestModelInfo:
    def test_returns_200(self, client):
        resp = client.get("/api/v1/predictions/model-info")
        assert resp.status_code == 200

    def test_response_has_required_fields(self, client):
        data = client.get("/api/v1/predictions/model-info").json()
        assert data["model_type"] == "XGBoostRegressor"
        assert isinstance(data["features"], list)
        assert data["training_date"] == "2024-01-15T10:30:00Z"
        assert isinstance(data["feature_importances"], dict)

    def test_503_when_model_not_ready(self, client):
        model_service.model = None
        resp = client.get("/api/v1/predictions/model-info")
        assert resp.status_code == 503


# ── predict_current endpoint ──────────────────────────────────────────────────

class TestPredictCurrent:
    def _sc_history_payload(self, n: int = 200) -> dict:
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        readings = [
            [
                (now - timedelta(hours=n - i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                15.0 + float(i % 10),
            ]
            for i in range(n)
        ]
        return {"readings": readings}

    def _sc_device_payload(self) -> dict:
        return {
            "data": {
                "recorded_at": "2025-05-13T10:00:00Z",
                "sensors": [
                    {"id": 87, "name": "PM 2.5", "value": 18.4},
                    {"id": 55, "name": "Temperature", "value": 28.5},
                    {"id": 56, "name": "Humidity", "value": 75.0},
                    {"id": 88, "name": "PM 10", "value": 35.0},
                ],
            }
        }

    def _make_mock_client(self, history_payload: dict, device_payload: dict):
        history_resp = MagicMock()
        history_resp.json.return_value = history_payload
        history_resp.raise_for_status = MagicMock()

        device_resp = MagicMock()
        device_resp.json.return_value = device_payload
        device_resp.raise_for_status = MagicMock()

        mock_async_client = AsyncMock()
        mock_async_client.__aenter__.return_value.get = AsyncMock(
            side_effect=[history_resp, device_resp]
        )
        return mock_async_client

    def test_returns_200_with_mocked_sc_api(self, client):
        mock_client = self._make_mock_client(
            self._sc_history_payload(), self._sc_device_payload()
        )
        with patch("app.services.model.httpx.AsyncClient", return_value=mock_client):
            resp = client.get("/api/v1/predictions/current")
        assert resp.status_code == 200

    def test_data_source_is_smart_citizen_live(self, client):
        mock_client = self._make_mock_client(
            self._sc_history_payload(), self._sc_device_payload()
        )
        with patch("app.services.model.httpx.AsyncClient", return_value=mock_client):
            resp = client.get("/api/v1/predictions/current")
        assert resp.json()["data_source"] == "smart_citizen_live"

    def test_response_has_required_fields(self, client):
        mock_client = self._make_mock_client(
            self._sc_history_payload(), self._sc_device_payload()
        )
        with patch("app.services.model.httpx.AsyncClient", return_value=mock_client):
            resp = client.get("/api/v1/predictions/current")
        data = resp.json()
        assert "prediction" in data
        assert "category" in data
        assert "aqi_color" in data
        assert "timestamp" in data

    def test_503_when_model_not_ready(self, client):
        model_service.model = None
        resp = client.get("/api/v1/predictions/current")
        assert resp.status_code == 503

    def test_502_when_sc_api_returns_empty_readings(self, client):
        empty_history = MagicMock()
        empty_history.json.return_value = {"readings": []}
        empty_history.raise_for_status = MagicMock()

        device_resp = MagicMock()
        device_resp.json.return_value = self._sc_device_payload()
        device_resp.raise_for_status = MagicMock()

        mock_async_client = AsyncMock()
        mock_async_client.__aenter__.return_value.get = AsyncMock(
            side_effect=[empty_history, device_resp]
        )
        with patch("app.services.model.httpx.AsyncClient", return_value=mock_async_client):
            resp = client.get("/api/v1/predictions/current")
        assert resp.status_code == 502
