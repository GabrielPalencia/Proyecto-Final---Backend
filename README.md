# API Calidad del Aire - Backend

Backend FastAPI para monitoreo de calidad del aire en Barranquilla con Smart Citizen Kit y predicciones XGBoost.

## Instalación y Setup

### 1. Crear entorno virtual

Entrar a la carpeta del backend y crear un entorno virtual:

```bash
py -3.11 -m venv venv
``` 
o

```bash
python -m venv venv
```

### 2. Activar entorno virtual

**Windows:**
```bash
source venv/Scripts/activate
```

**Mac/Linux:**
```bash
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Copia el archivo `.env.example` a `.env` y configura tus variables:

```bash
cp .env.example .env
```

Edita `.env` y reemplaza `TU_DEVICE_ID_AQUI` con tu ID de dispositivo Smart Citizen.

## Ejecutar en desarrollo

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

El servidor estará disponible en `http://localhost:8000`

La documentación Swagger está en `http://localhost:8000/docs`

## Estructura del Proyecto

```
backend/
├── app/
│   ├── main.py                  # Entry point FastAPI
│   ├── config.py                # Configuración y variables de entorno
│   ├── routers/                 # Rutas de la API
│   │   ├── sensor.py            # Endpoints del sensor Smart Citizen
│   │   └── predictions.py       # Endpoints de predicciones XGBoost
│   ├── services/                # Lógica de negocio
│   │   ├── smart_citizen.py     # Cliente HTTP para Smart Citizen API
│   │   └── model.py             # Carga y predicción del modelo XGBoost
│   ├── schemas/                 # Pydantic models para validación
│   │   ├── sensor.py            # Schemas del sensor
│   │   └── prediction.py        # Schemas de predicciones
│   └── models/                  # Modelos entrenados
│       └── xgboost_model.pkl    # Modelo serializado
├── tests/                       # Tests unitarios
├── .env                         # Variables de entorno (NO commitar)
├── .env.example                 # Template de variables de entorno
├── requirements.txt             # Dependencias Python
└── README.md                    # Este archivo
```

## Variables de Entorno

- `SMART_CITIZEN_BASE_URL`: URL de la API de Smart Citizen
- `SMART_CITIZEN_DEVICE_ID`: ID de tu dispositivo en Smart Citizen
- `APP_ENV`: Ambiente (development/production)
- `APP_HOST`: Host del servidor (default: 0.0.0.0)
- `APP_PORT`: Puerto del servidor (default: 8000)
- `CORS_ORIGINS`: Orígenes permitidos para CORS (usar formato JSON array)
- `CACHE_TTL_SECONDS`: TTL del caché en segundos
