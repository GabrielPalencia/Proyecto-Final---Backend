# BE-01 · Configuración del Proyecto Backend (FastAPI)

## Contexto

Estás construyendo el backend de un sistema de monitoreo de calidad del aire para Barranquilla, Colombia. El backend consiste en una API REST hecha con **FastAPI** (Python) que cumple dos funciones:

1. **Proxy/adaptador** hacia la API pública de Smart Citizen (`https://api.smartcitizen.me/v0/`) para obtener las mediciones del sensor físico desplegado.
2. **API de predicción** que sirve un modelo XGBoost entrenado para predecir el índice de calidad del aire (AQI) con base en las lecturas del sensor.

Este archivo cubre únicamente la **configuración inicial del proyecto**: estructura de carpetas, dependencias, variables de entorno y servidor base.

---

## Objetivo de esta tarea

Crear la estructura base del proyecto backend con FastAPI lista para desarrollo, con:
- Entorno virtual y dependencias instaladas
- Estructura de carpetas modular
- Variables de entorno gestionadas con `python-dotenv`
- Servidor corriendo con recarga en caliente (hot reload)
- CORS configurado para permitir peticiones desde el frontend React (localhost:5173)

---

## Estructura de carpetas esperada

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # Entry point FastAPI
│   ├── config.py                # Configuración y variables de entorno
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── sensor.py            # Rutas relacionadas con el sensor SCK
│   │   └── predictions.py       # Rutas del modelo XGBoost
│   ├── services/
│   │   ├── __init__.py
│   │   ├── smart_citizen.py     # Cliente HTTP para la API de Smart Citizen
│   │   └── model.py             # Lógica de carga y predicción del modelo
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── sensor.py            # Pydantic models para respuestas del sensor
│   │   └── prediction.py        # Pydantic models para predicciones
│   └── models/
│       └── xgboost_model.pkl    # Modelo serializado (se añade en BE-03)
├── tests/
│   └── __init__.py
├── .env
├── .env.example
├── requirements.txt
└── README.md
```

---

## Instrucciones paso a paso

### 1. Inicializar el entorno virtual e instalar dependencias

Crea un entorno virtual Python 3.11+ e instala las siguientes dependencias. Genera el archivo `requirements.txt` con estas versiones exactas:

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
httpx==0.27.0
python-dotenv==1.0.1
pydantic==2.7.1
pydantic-settings==2.2.1
xgboost==2.0.3
scikit-learn==1.4.2
numpy==1.26.4
pandas==2.2.2
joblib==1.4.2
pytest==8.2.0
pytest-asyncio==0.23.6
httpx==0.27.0
```

### 2. Crear el archivo `.env`

```env
# Smart Citizen API
SMART_CITIZEN_BASE_URL=https://api.smartcitizen.me/v0
SMART_CITIZEN_DEVICE_ID=TU_DEVICE_ID_AQUI

# App settings
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Caché TTL en segundos
CACHE_TTL_SECONDS=60
```

> **Importante:** El `SMART_CITIZEN_DEVICE_ID` es el ID numérico de tu dispositivo en la plataforma Smart Citizen. Puedes encontrarlo en la URL cuando accedes a tu dispositivo en `smartcitizen.me/devices/{id}`.

Crea también `.env.example` con los mismos campos pero sin valores reales.

### 3. Crear `app/config.py`

Implementa una clase `Settings` usando `pydantic-settings` que lea las variables de `.env`:

```python
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    smart_citizen_base_url: str
    smart_citizen_device_id: str
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: List[str] = ["http://localhost:5173"]
    cache_ttl_seconds: int = 60

    class Config:
        env_file = ".env"

settings = Settings()
```

### 4. Crear `app/main.py`

Implementa la aplicación FastAPI con:

- Título: `"API Calidad del Aire - Barranquilla"`
- Versión: `"1.0.0"`
- Descripción: `"Backend para monitoreo de calidad del aire con sensor Smart Citizen Kit y predicciones XGBoost"`
- Middleware CORS configurado con los orígenes de `settings.cors_origins`, permitiendo todos los métodos y headers
- Un endpoint raíz `GET /` que retorne `{"status": "ok", "message": "API Calidad del Aire Barranquilla"}` 
- Un endpoint de salud `GET /health` que retorne `{"status": "healthy", "environment": settings.app_env}`
- Los routers de `sensor` y `predictions` incluidos con prefijos `/api/v1/sensor` y `/api/v1/predictions` respectivamente (los routers estarán vacíos por ahora, se implementan en tareas siguientes)

### 5. Crear los archivos `__init__.py` y placeholders

Crea todos los archivos `__init__.py` vacíos necesarios. En `routers/sensor.py` y `routers/predictions.py` crea un router vacío con un comentario `# TODO: implementar en BE-02 y BE-03`.

### 6. Script de arranque

En el `README.md` incluye instrucciones para:

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Windows: source venv/Scripts/activate

# Instalar dependencias
pip install -r requirements.txt

# Correr en desarrollo
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Criterios de aceptación

- [ ] `uvicorn app.main:app --reload` inicia sin errores
- [ ] `GET http://localhost:8000/` retorna `{"status": "ok", ...}`
- [ ] `GET http://localhost:8000/health` retorna `{"status": "healthy", ...}`
- [ ] `GET http://localhost:8000/docs` muestra la documentación Swagger generada automáticamente
- [ ] El servidor responde con los headers CORS correctos a peticiones desde `http://localhost:5173`
- [ ] Las variables de entorno se cargan correctamente desde `.env`

---

## Notas técnicas

- Usa Python 3.11.
- FastAPI genera automáticamente documentación en `/docs` (Swagger) y `/redoc`.
- `pydantic-settings` es la forma recomendada en Pydantic v2 para gestionar configuración.
- No hardcodees ningún valor sensible en el código; todo debe venir de `.env`.
