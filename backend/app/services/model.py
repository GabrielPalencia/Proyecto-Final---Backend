import json
import logging
import numpy as np
import pandas as pd
import httpx
import joblib
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import HTTPException
from app.config import settings

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent.parent / "models"

AQI_THRESHOLDS: list[tuple[float, str, str]] = [
    (12.0,   "Buena",                          "#00E400"),
    (35.4,   "Moderada",                       "#FFFF00"),
    (55.4,   "Dañina para grupos sensibles",   "#FF7E00"),
    (150.4,  "Dañina",                         "#FF0000"),
    (250.4,  "Muy dañina",                     "#8F3F97"),
    (float("inf"), "Peligrosa",                "#7E0023"),
]


class ModelService:
    def __init__(self) -> None:
        self.model = None
        self.feature_cols: list[str] | None = None
        self.ica_breakpoints: dict | None = None
        self.metadata: dict | None = None
        self._try_load_artifacts()

    def _try_load_artifacts(self) -> None:
        model_path = MODELS_DIR / "modelo_pm25.joblib"
        features_path = MODELS_DIR / "features.json"
        metadata_path = MODELS_DIR / "metadata.json"
        ica_path = MODELS_DIR / "ica_breakpoints.json"

        if not model_path.exists():
            logger.warning(
                "modelo_pm25.joblib not found in %s. "
                "Export artifacts from Colab and place them in backend/app/models/",
                MODELS_DIR,
            )
            return

        try:
            self.model = joblib.load(model_path)
            with open(features_path) as f:
                self.feature_cols = json.load(f)
            with open(metadata_path) as f:
                self.metadata = json.load(f)
            if ica_path.exists():
                with open(ica_path) as f:
                    self.ica_breakpoints = json.load(f)
            logger.info(
                "Model loaded: %s | %d features",
                self.metadata.get("model_type"),
                len(self.feature_cols),
            )
        except Exception as exc:
            self.model = None
            logger.error("Failed to load model artifacts: %s", exc)

    @property
    def is_ready(self) -> bool:
        return self.model is not None

    def _aqi_category(self, pm25: float) -> tuple[str, str]:
        for threshold, category, color in AQI_THRESHOLDS:
            if pm25 <= threshold:
                return category, color
        return "Peligrosa", "#7E0023"

    def get_model_info(self) -> dict:
        if not self.is_ready:
            raise RuntimeError("Model artifacts not loaded")
        return {
            "model_type": self.metadata.get("model_type", "XGBoostRegressor"),
            "features": self.feature_cols,
            "training_date": self.metadata.get("fecha_entrenamiento", ""),
            "feature_importances": dict(zip(
                self.feature_cols,
                self.model.feature_importances_.tolist(),
            )),
        }

    def _parse_feature(
        self,
        feat: str,
        dt: datetime,
        pm25_series: pd.Series | None,
        current_sensors: dict,
        target_col: str,
    ) -> float:
        # ── Cyclic temporal ──────────────────────────────────────────────────
        if feat == "hora_sin":
            return np.sin(2 * np.pi * dt.hour / 24)
        if feat == "hora_cos":
            return np.cos(2 * np.pi * dt.hour / 24)
        if feat == "dow_sin":
            return np.sin(2 * np.pi * dt.weekday() / 7)
        if feat == "dow_cos":
            return np.cos(2 * np.pi * dt.weekday() / 7)
        if feat == "mes_sin":
            return np.sin(2 * np.pi * (dt.month - 1) / 12)
        if feat == "mes_cos":
            return np.cos(2 * np.pi * (dt.month - 1) / 12)
        if feat == "fin_de_semana":
            return float(dt.weekday() >= 5)

        # ── Lag features: *_lag_Nh ───────────────────────────────────────────
        if "_lag_" in feat:
            lag_h = int(feat.split("_lag_")[1].rstrip("h"))
            if feat.startswith(target_col):
                if pm25_series is not None and len(pm25_series) >= lag_h:
                    return float(pm25_series.iloc[-lag_h])
                return np.nan
            if lag_h == 1:
                sensor_prefix = feat.split("_lag_")[0]
                for key, val in current_sensors.items():
                    if (sensor_prefix == key or sensor_prefix.startswith(key + "_")) and val is not None:
                        return float(val)
            return np.nan

        # ── Rolling features: *_rollW_stat ───────────────────────────────────
        if "_roll" in feat and feat.startswith(target_col):
            roll_part = feat.split("_roll")[1]
            w_str, stat = roll_part.split("_", 1)
            w = int(w_str)
            if pm25_series is not None and len(pm25_series) >= w:
                window = pm25_series.iloc[-w:]
                if stat == "mean":
                    return float(window.mean())
                if stat == "std":
                    return float(window.std())
                if stat == "max":
                    return float(window.max())

        return np.nan

    def _build_feature_vector(
        self,
        dt: datetime,
        pm25_series: pd.Series | None = None,
        current_sensors: dict | None = None,
    ) -> np.ndarray:
        if self.feature_cols is None or self.metadata is None:
            raise RuntimeError("Model artifacts not loaded")
        sensors = current_sensors or {}
        target_col = self.metadata.get("target", "pm25")
        values = [
            self._parse_feature(feat, dt, pm25_series, sensors, target_col)
            for feat in self.feature_cols
        ]
        return np.array(values, dtype=float).reshape(1, -1)

    async def fetch_pm25_history(self, device_id: str, base_url: str) -> pd.Series | None:
        """Fetch 200h of PM2.5 history from Smart Citizen API. Returns None on failure."""
        try:
            now = datetime.now(timezone.utc)
            from_dt = now - timedelta(hours=200)
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{base_url}/devices/{device_id}/readings",
                    params={
                        "sensor_id": 87,
                        "rollup": "1h",
                        "from": from_dt.isoformat(),
                        "to": now.isoformat(),
                        "function": "avg",
                    },
                )
                resp.raise_for_status()
                readings = resp.json().get("readings", [])
            if not readings:
                return None
            timestamps = pd.to_datetime([r[0] for r in readings], utc=True)
            values = [float(r[1]) if r[1] is not None else np.nan for r in readings]
            return pd.Series(values, index=timestamps).sort_index()
        except Exception as exc:
            logger.warning("Could not fetch PM2.5 history: %s", exc)
            return None

    def predict_manual(
        self,
        input_data: dict,
        pm25_series: pd.Series | None = None,
    ) -> dict:
        dt = datetime.now(timezone.utc)
        current_sensors = {k: v for k, v in input_data.items() if v is not None}
        X = self._build_feature_vector(dt, pm25_series=pm25_series, current_sensors=current_sensors)
        pm25_pred = float(self.model.predict(X)[0])
        category, color = self._aqi_category(pm25_pred)
        return {
            "prediction": pm25_pred,
            "category": category,
            "aqi_color": color,
            "timestamp": dt,
            "input_features": input_data,
            "model_version": self.metadata.get("fecha_entrenamiento", "unknown"),
            "data_source": "manual",
        }

    async def predict_current(self, device_id: str, base_url: str) -> dict:
        now = datetime.now(timezone.utc)
        from_dt = now - timedelta(hours=200)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp_hist = await client.get(
                    f"{base_url}/devices/{device_id}/readings",
                    params={
                        "sensor_id": 87,
                        "rollup": "1h",
                        "from": from_dt.isoformat(),
                        "to": now.isoformat(),
                        "function": "avg",
                    },
                )
                resp_hist.raise_for_status()

                resp_curr = await client.get(f"{base_url}/devices/{device_id}")
                resp_curr.raise_for_status()

                hist_data = resp_hist.json()
                curr_data = resp_curr.json()
        except httpx.TransportError as exc:
            raise HTTPException(502, "No se pudo conectar al sensor Smart Citizen") from exc

        readings = hist_data.get("readings", [])
        if not readings:
            raise HTTPException(502, "Smart Citizen API returned no PM2.5 readings")

        timestamps = pd.to_datetime([r[0] for r in readings], utc=True)
        values = [float(r[1]) if r[1] is not None else np.nan for r in readings]
        pm25_series = pd.Series(values, index=timestamps).sort_index()

        # Verificar que los datos sean recientes
        last_ts = pm25_series.index[-1]
        age_hours = (now - last_ts).total_seconds() / 3600
        if age_hours > settings.max_data_age_hours:
            raise HTTPException(
                502,
                f"Datos del sensor desactualizados: última lectura hace "
                f"{int(age_hours)}h (máximo permitido: {settings.max_data_age_hours}h). "
                f"Verificar que el sensor físico esté publicando.",
            )

        sensor_name_map = {
            "Temperature": "temperature",
            "Humidity": "humidity",
            "PM 10": "pm10",
            "PM 1.0": "pm1",
        }
        current_sensors: dict = {}
        for s in curr_data.get("data", {}).get("sensors", []):
            key = sensor_name_map.get(s.get("name", ""))
            if key and s.get("value") is not None:
                current_sensors[key] = s["value"]

        X = self._build_feature_vector(now, pm25_series=pm25_series, current_sensors=current_sensors)
        pm25_pred = float(self.model.predict(X)[0])
        category, color = self._aqi_category(pm25_pred)

        return {
            "prediction": pm25_pred,
            "category": category,
            "aqi_color": color,
            "timestamp": now,
            "input_features": {
                "pm25_latest": float(pm25_series.iloc[-1]) if len(pm25_series) > 0 else None,
                **current_sensors,
            },
            "model_version": self.metadata.get("fecha_entrenamiento", "unknown"),
            "data_source": "smart_citizen_live",
        }


model_service = ModelService()
