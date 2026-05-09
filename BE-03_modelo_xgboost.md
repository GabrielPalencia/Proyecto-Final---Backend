# BE-03 · Exportación del Modelo XGBoost y API de Predicciones

## Contexto

Tienes un modelo XGBoost entrenado en Google Colab para predecir la calidad del aire en Barranquilla. Este archivo guía el proceso completo desde exportar el modelo desde Colab hasta exponerlo como endpoint REST.

El modelo predice el **índice AQI** (Air Quality Index) o una categoría de calidad del aire basándose en variables como PM2.5, PM10, temperatura, humedad, entre otras.

---

## Parte A · Exportar el modelo desde Google Colab

### Paso 1: Serializar el modelo y el preprocessor

Ejecuta este bloque en tu notebook de Colab para exportar todo lo necesario:

```python
import joblib
import json
import numpy as np
from datetime import datetime

# ── 1. Guarda el modelo entrenado ──────────────────────────────────────────────
joblib.dump(model, 'xgboost_model.pkl')

# ── 2. Si tienes un scaler/preprocessor, guárdalo también ─────────────────────
# joblib.dump(scaler, 'scaler.pkl')  # descomenta si aplica

# ── 3. Exporta los metadatos del modelo ───────────────────────────────────────
model_metadata = {
    "model_type": "XGBoostRegressor",  # o XGBoostClassifier si predice categorías
    "target": "aqi",                   # nombre de la variable objetivo
    "features": list(X_train.columns), # nombres exactos de las features en orden
    "training_date": datetime.now().isoformat(),
    "n_estimators": model.n_estimators,
    "feature_importances": dict(zip(
        X_train.columns,
        model.feature_importances_.tolist()
    )),
    # Si es clasificación, agrega:
    # "classes": model.classes_.tolist(),
    # "aqi_categories": {
    #     0: "Buena",
    #     1: "Moderada",
    #     2: "Dañina para grupos sensibles",
    #     3: "Dañina",
    #     4: "Muy dañina",
    #     5: "Peligrosa"
    # }
}

with open('model_metadata.json', 'w') as f:
    json.dump(model_metadata, f, indent=2)

print("Features del modelo:", model_metadata["features"])
print("Archivos generados: xgboost_model.pkl, model_metadata.json")
```

### Paso 2: Descargar los archivos desde Colab

```python
from google.colab import files
files.download('xgboost_model.pkl')
files.download('model_metadata.json')
# files.download('scaler.pkl')  # si aplica
```

### Paso 3: Colocar los archivos en el backend

Copia los archivos descargados a:
```
backend/app/models/xgboost_model.pkl
backend/app/models/model_metadata.json
# backend/app/models/scaler.pkl  (si aplica)
```

---

## Parte B · Servicio de predicción `app/services/model.py`

### Descripción

Implementa una clase `ModelService` que:
- Carga el modelo al iniciar la aplicación (una sola vez, no en cada request)
- Expone métodos para hacer predicciones individuales y en batch
- Calcula el índice AQI estándar si el modelo predice PM2.5

### Implementación

```python
# app/services/model.py
import joblib
import json
import numpy as np
import pandas as pd
from pathlib import Path
from app.config import settings

MODELS_DIR = Path(__file__).parent.parent / "models"

class ModelService:
    def __init__(self):
        self.model = None
        self.metadata = None
        self.scaler = None
        self._load_model()

    def _load_model(self):
        """Carga el modelo XGBoost y sus metadatos al iniciar."""
        model_path = MODELS_DIR / "xgboost_model.pkl"
        metadata_path = MODELS_DIR / "model_metadata.json"
        
        if not model_path.exists():
            raise FileNotFoundError(
                f"Modelo no encontrado en {model_path}. "
                "Ejecuta el proceso de exportación desde Colab (ver BE-03 Parte A)."
            )
        
        self.model = joblib.load(model_path)
        
        with open(metadata_path) as f:
            self.metadata = json.load(f)
        
        # Carga scaler opcional
        scaler_path = MODELS_DIR / "scaler.pkl"
        if scaler_path.exists():
            self.scaler = joblib.load(scaler_path)

    @property
    def features(self) -> list[str]:
        """Retorna las features que espera el modelo en orden."""
        return self.metadata["features"]

    def predict(self, input_data: dict) -> dict:
        """
        Realiza una predicción individual.
        
        Args:
            input_data: dict con las features. Claves = nombres de features del modelo.
        
        Returns:
            dict con la predicción y metadatos adicionales.
        """
        # Construir DataFrame con el orden exacto de features
        df = pd.DataFrame([{feat: input_data.get(feat, np.nan) for feat in self.features}])
        
        # Aplicar scaler si existe
        if self.scaler:
            df_scaled = self.scaler.transform(df)
        else:
            df_scaled = df.values
        
        prediction = self.model.predict(df_scaled)[0]
        
        result = {
            "prediction": float(prediction),
            "model_type": self.metadata["model_type"],
        }
        
        # Si el modelo es un clasificador, incluir la categoría
        if "aqi_categories" in self.metadata:
            category_id = int(prediction)
            result["category"] = self.metadata["aqi_categories"].get(
                str(category_id), "Desconocida"
            )
            result["category_id"] = category_id
        else:
            # Si predice valor continuo de AQI, calcular categoría
            result["category"] = self._aqi_to_category(float(prediction))
        
        return result

    def _aqi_to_category(self, aqi: float) -> str:
        """Convierte un valor numérico AQI a categoría según estándar EPA."""
        if aqi <= 50:
            return "Buena"
        elif aqi <= 100:
            return "Moderada"
        elif aqi <= 150:
            return "Dañina para grupos sensibles"
        elif aqi <= 200:
            return "Dañina"
        elif aqi <= 300:
            return "Muy dañina"
        else:
            return "Peligrosa"

    def get_feature_importance(self) -> dict:
        """Retorna la importancia de cada feature."""
        return self.metadata.get("feature_importances", {})

# Singleton - se instancia una sola vez
model_service = ModelService()
```

### Inicialización al arrancar la app

En `app/main.py`, agrega un evento de inicio para validar que el modelo carga correctamente:

```python
from contextlib import asynccontextmanager
from app.services.model import model_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"✅ Modelo cargado: {model_service.metadata['model_type']}")
    print(f"✅ Features: {model_service.features}")
    yield
    # Shutdown (si necesitas limpiar recursos)

app = FastAPI(lifespan=lifespan, ...)
```

---

## Parte C · Schemas `app/schemas/prediction.py`

### `PredictionInput`

```python
class PredictionInput(BaseModel):
    pm25: float = Field(..., ge=0, description="PM2.5 en µg/m³")
    pm10: float = Field(..., ge=0, description="PM10 en µg/m³")
    pm1: float | None = Field(None, ge=0, description="PM1.0 en µg/m³")
    temperature: float | None = Field(None, description="Temperatura en °C")
    humidity: float | None = Field(None, ge=0, le=100, description="Humedad relativa en %")
    co2: float | None = Field(None, ge=0, description="CO2 en ppm")
    no2: float | None = Field(None, ge=0, description="NO2 en ppb")
    # Agrega aquí las features adicionales que use tu modelo
```

> **Importante:** Este schema debe reflejar exactamente las features con las que entrenaste tu modelo. Ajusta los campos según `model_metadata.json["features"]`.

### `PredictionOutput`

```python
class PredictionOutput(BaseModel):
    prediction: float
    category: str
    category_id: int | None = None
    aqi_color: str          # color hex para la UI
    timestamp: datetime
    input_features: dict    # echo de los datos de entrada
    model_version: str
```

### `BatchPredictionInput`

```python
class BatchPredictionInput(BaseModel):
    readings: list[PredictionInput] = Field(..., max_length=168)
```

### Helper para color AQI

```python
AQI_COLORS = {
    "Buena": "#00E400",
    "Moderada": "#FFFF00",
    "Dañina para grupos sensibles": "#FF7E00",
    "Dañina": "#FF0000",
    "Muy dañina": "#8F3F97",
    "Peligrosa": "#7E0023",
}
```

---

## Parte D · Router `app/routers/predictions.py`

### `POST /api/v1/predictions/predict`

**Descripción:** Realiza una predicción con los datos de entrada provistos manualmente.

**Body:** `PredictionInput`

**Response:** `PredictionOutput`

**Lógica:**
1. Convierte `PredictionInput` a dict
2. Llama a `model_service.predict(input_dict)`
3. Construye y retorna `PredictionOutput` con el color AQI correspondiente

### `GET /api/v1/predictions/current`

**Descripción:** Obtiene las lecturas actuales del sensor y ejecuta una predicción automáticamente.

**Response:** `PredictionOutput`

**Lógica:**
1. Llama a `smart_citizen_service.get_device_current_readings()` (reutiliza el servicio de BE-02)
2. Extrae los valores de PM2.5, PM10, temperatura, humedad, etc. del array `data.sensors`
3. Construye el input para el modelo mapeando `sensor_name` → `feature_name`
4. Llama a `model_service.predict()` y retorna el resultado

**Mapeo de sensores a features:**
```python
SENSOR_TO_FEATURE_MAP = {
    "PM 2.5": "pm25",
    "PM 10": "pm10",
    "PM 1.0": "pm1",
    "Temperature": "temperature",
    "Humidity": "humidity",
    # Ajusta según los nombres exactos de tus sensores
}
```

### `GET /api/v1/predictions/model-info`

**Descripción:** Retorna información sobre el modelo en producción.

**Response:**
```json
{
  "model_type": "XGBoostRegressor",
  "features": ["pm25", "pm10", "temperature", "humidity"],
  "training_date": "2024-01-15T10:30:00",
  "feature_importances": {
    "pm25": 0.45,
    "pm10": 0.30,
    "temperature": 0.15,
    "humidity": 0.10
  }
}
```

---

## Criterios de aceptación

- [ ] El modelo carga sin errores al iniciar `uvicorn`
- [ ] `POST /api/v1/predictions/predict` con datos válidos retorna una predicción con categoría y color
- [ ] `GET /api/v1/predictions/current` encadena la lectura del sensor con la predicción
- [ ] `GET /api/v1/predictions/model-info` retorna los metadatos del modelo
- [ ] Si `xgboost_model.pkl` no existe, el servidor muestra un error claro en el arranque
- [ ] Los valores `null` en features opcionales no rompen la predicción

---

## Notas técnicas

- Usa `joblib` (no `pickle`) para serializar modelos de sklearn/xgboost ya que es más eficiente con arrays numpy.
- El modelo se carga **una sola vez** en el singleton `model_service`; no lo cargues dentro de los endpoints.
- Si tu modelo fue entrenado con un `ColumnTransformer` o `Pipeline` de sklearn, exporta el pipeline completo: `joblib.dump(pipeline, 'xgboost_model.pkl')`.
- Asegúrate de que el orden de las features en `PredictionInput` coincide exactamente con el orden en que entrenaste el modelo.
