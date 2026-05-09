# 📋 AirWatch Barranquilla — Índice de Tareas de Desarrollo

Sistema de monitoreo de calidad del aire para Barranquilla. Sensor Smart Citizen Kit + modelo XGBoost + dashboard React.

---

## Arquitectura del sistema

```
┌─────────────────────────────────────────────────────────┐
│                  REACT FRONTEND (Vite)                   │
│           Dashboard │ Predicciones                       │
│         localhost:5173                                    │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP / REST
┌────────────────────▼────────────────────────────────────┐
│                FASTAPI BACKEND (Python)                  │
│           localhost:8000                                  │
│  ┌─────────────────┐    ┌──────────────────────────┐    │
│  │ /api/v1/sensor  │    │ /api/v1/predictions       │    │
│  └────────┬────────┘    └──────────┬───────────────┘    │
│           │                        │                      │
│  Smart Citizen API          XGBoost Model                │
│  (proxy/adaptador)          (xgboost_model.pkl)          │
└──────────────────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│         SMART CITIZEN API (Externa)                      │
│         api.smartcitizen.me/v0/devices/{id}              │
└─────────────────────────────────────────────────────────┘
```

---

## Mapa de tareas

### 🔧 Backend

| Archivo | Tarea | Descripción |
|---|---|---|
| `BE-01_setup_proyecto.md` | Setup inicial | Estructura de carpetas, FastAPI, dependencias, CORS |
| `BE-02_smart_citizen_service.md` | Integración Smart Citizen | Servicio HTTP, endpoints de sensor, caché |
| `BE-03_modelo_xgboost.md` | Modelo XGBoost | Exportación desde Colab, servicio de predicción, endpoints |
| `BE-04_errores_logging_deploy.md` | Errores y despliegue | Error handling, logging, Docker |

### 🎨 Frontend

| Archivo | Tarea | Descripción |
|---|---|---|
| `FE-01_setup_frontend.md` | Setup inicial | Vite, TanStack Query, Axios, Tailwind, routing |
| `FE-02_dashboard_sensores.md` | Dashboard principal | Grid de métricas, AQI gauge, gráfica histórica |
| `FE-03_predicciones.md` | Sección predicciones | Predicción automática, formulario manual, info del modelo |
| `FE-04_layout_ui.md` | Layout y UI base | Navbar, Layout, LoadingSpinner, ErrorBanner |

---

## Orden de implementación recomendado

```
BE-01 → BE-02 → BE-03 → BE-04
                 ↓
FE-01 → FE-04 → FE-02 → FE-03
```

Puedes trabajar BE y FE en paralelo una vez que BE-01 y FE-01 estén listos, usando datos mock en el frontend.

---

## Endpoints del backend (resumen)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/status` | Estado de todos los servicios |
| `GET` | `/api/v1/sensor/current` | Lecturas actuales del SCK |
| `GET` | `/api/v1/sensor/historical/{id}` | Histórico con rollup temporal |
| `GET` | `/api/v1/sensor/sensors` | Lista de sensores disponibles |
| `POST` | `/api/v1/predictions/predict` | Predicción manual |
| `GET` | `/api/v1/predictions/current` | Predicción con datos del sensor |
| `GET` | `/api/v1/predictions/model-info` | Metadatos del modelo |

---

## Rutas del frontend

| Ruta | Página | Descripción |
|---|---|---|
| `/dashboard` | `Dashboard.jsx` | Lecturas en tiempo real |
| `/predictions` | `Predictions.jsx` | Predicciones AQI |

---

## Checklist final de integración

- [ ] Backend levanta sin errores: `uvicorn app.main:app --reload`
- [ ] `GET /api/v1/sensor/current` retorna datos reales del dispositivo SCK
- [ ] `GET /api/v1/predictions/current` retorna predicción encadenada con lectura del sensor
- [ ] Frontend levanta sin errores: `npm run dev`
- [ ] Dashboard muestra lecturas reales actualizándose cada minuto
- [ ] Sección predicciones muestra categoría AQI y recomendaciones
- [ ] No hay errores CORS en consola del navegador
- [ ] `docker-compose up` levanta toda la aplicación
