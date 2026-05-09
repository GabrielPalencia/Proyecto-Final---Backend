# BE-04 · Manejo de Errores, Logging y Preparación para Despliegue

## Contexto

Con los servicios de sensor (BE-02) y predicción (BE-03) ya implementados, esta tarea consolida la API con manejo de errores consistente, logging y configuración lista para producción.

---

## Objetivo de esta tarea

1. Centralizar el manejo de errores HTTP con respuestas uniformes
2. Agregar logging estructurado para depuración
3. Agregar endpoint de diagnóstico `/api/v1/status`
4. Crear `docker-compose.yml` para correr el backend en contenedor

---

## 1. Manejo de errores centralizado

### Schema de error uniforme en `app/schemas/error.py`

```python
from pydantic import BaseModel

class ErrorResponse(BaseModel):
    error: str
    message: str
    detail: str | None = None
```

### Exception handlers en `app/main.py`

Agrega estos handlers globales a la aplicación FastAPI para que todos los errores retornen JSON consistente:

```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": f"HTTP_{exc.status_code}",
            "message": exc.detail,
            "detail": str(request.url)
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    # Log el error completo internamente
    import logging
    logging.error(f"Error no controlado: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "Error interno del servidor",
            "detail": None  # nunca exponer el traceback en producción
        }
    )
```

### Validación de errores Pydantic

FastAPI maneja `RequestValidationError` automáticamente, pero puedes personalizarlo:

```python
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Los datos de entrada no son válidos",
            "detail": [
                f"Campo '{'.'.join(str(loc) for loc in e['loc'])}': {e['msg']}"
                for e in errors
            ]
        }
    )
```

---

## 2. Logging estructurado

### Configuración en `app/config.py`

Agrega a `Settings`:
```python
log_level: str = "INFO"
```

### Módulo `app/logger.py`

```python
import logging
import sys
from app.config import settings

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(settings.log_level.upper())
    
    return logger
```

### Uso en los servicios

En `app/services/smart_citizen.py`:
```python
from app.logger import get_logger
logger = get_logger("smart_citizen")

# Dentro de get_device_current_readings:
logger.info(f"Obteniendo lecturas del dispositivo {self.device_id}")
logger.error(f"Timeout al conectar con Smart Citizen API: {exc}")
```

En `app/services/model.py`:
```python
from app.logger import get_logger
logger = get_logger("model")

# En _load_model:
logger.info(f"Modelo cargado: {self.metadata['model_type']}")
logger.info(f"Features ({len(self.features)}): {self.features}")
```

---

## 3. Endpoint de diagnóstico

### `GET /api/v1/status`

Agrega este endpoint en un nuevo router `app/routers/status.py` con prefijo `/api/v1`:

**Response:**
```json
{
  "status": "ok",
  "environment": "development",
  "services": {
    "smart_citizen_api": {
      "reachable": true,
      "device_id": "12345",
      "last_check": "2024-05-01T14:30:00Z"
    },
    "model": {
      "loaded": true,
      "model_type": "XGBoostRegressor",
      "features_count": 7
    }
  },
  "uptime_seconds": 3600
}
```

**Lógica:**
1. Intenta llamar a `GET https://api.smartcitizen.me/v0/devices/{device_id}` con timeout de 5s para verificar conectividad
2. Verifica que `model_service.model is not None`
3. Calcula el uptime desde el inicio de la aplicación (guarda `start_time = datetime.now()` en el lifespan)

---

## 4. Dockerización

### `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema para XGBoost
RUN apt-get update && apt-get install -y \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### `docker-compose.yml`

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file:
      - ./backend/.env
    volumes:
      - ./backend/app/models:/app/app/models:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  frontend:
    build: ./frontend
    ports:
      - "5173:80"
    depends_on:
      - backend
    restart: unless-stopped
```

### `.dockerignore`

```
__pycache__/
*.pyc
*.pyo
.env
venv/
.git/
tests/
*.md
```

---

## 5. Resumen de todos los endpoints de la API

Una vez implementados BE-01 a BE-04, la API expone:

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/` | Raíz de la API |
| `GET` | `/health` | Health check básico |
| `GET` | `/docs` | Documentación Swagger |
| `GET` | `/api/v1/status` | Diagnóstico completo |
| `GET` | `/api/v1/sensor/current` | Lecturas actuales del sensor |
| `GET` | `/api/v1/sensor/historical/{sensor_id}` | Histórico de lecturas |
| `GET` | `/api/v1/sensor/sensors` | Lista de sensores disponibles |
| `POST` | `/api/v1/predictions/predict` | Predicción manual |
| `GET` | `/api/v1/predictions/current` | Predicción con lectura actual |
| `GET` | `/api/v1/predictions/model-info` | Info del modelo en producción |

---

## Criterios de aceptación

- [ ] Todos los errores HTTP retornan el formato `{"error": ..., "message": ..., "detail": ...}`
- [ ] Los errores de validación Pydantic retornan mensajes legibles en español
- [ ] El servidor nunca expone trazas de stack en respuestas de error (en producción)
- [ ] `GET /api/v1/status` retorna el estado real de conectividad con Smart Citizen y del modelo
- [ ] `docker-compose up` levanta el backend correctamente
- [ ] Los logs muestran timestamps, nivel y origen del mensaje

---

## Notas técnicas

- En producción, configura `APP_ENV=production` en `.env` y filtra los logs sensibles.
- `libgomp1` es necesaria en el contenedor Docker para que XGBoost funcione en Linux.
- El volumen `:ro` en docker-compose monta el directorio de modelos en modo solo lectura por seguridad.
