# BE-03 — Modelo XGBoost conectado al backend

## Qué es esto

Este backend tiene un modelo de inteligencia artificial (XGBoost) que predice la calidad del aire en Barranquilla. El modelo fue entrenado en Google Colab con datos reales de 2022-2023, y ahora está integrado en el servidor.

Cuando el servidor recibe números del sensor (PM2.5, temperatura, humedad, etc.), responde con:
- Un número de predicción de PM2.5
- Una categoría: Buena / Moderada / Dañina / Peligrosa
- Un color hex para mostrar en el frontend (verde, amarillo, rojo, etc.)

---

## Cómo probarlo

### 1. Instalar la dependencia del sistema (solo Mac, una sola vez)
```bash
brew install libomp
```

### 2. Instalar dependencias Python
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Mac/Linux
# source venv/Scripts/activate  # Windows
pip install -r requirements.txt
```

### 3. Crear el archivo .env
Copia `.env.example` a `.env` y pon tu device ID de Smart Citizen:
```bash
cp .env.example .env
```
Edita `.env`:

```

### 4. Verificar que los archivos del modelo están en su lugar
Estos 4 archivos deben existir en `backend/app/models/`:
- `modelo_pm25.joblib` — el modelo entrenado
- `features.json` — lista de variables que usa el modelo
- `ica_breakpoints.json` — escala de calidad del aire
- `metadata.json` — información del entrenamiento

Si no están, ver sección "Regenerar archivos del modelo" abajo.

### 5. Arrancar el servidor
```bash
cd backend
venv/bin/uvicorn app.main:app --reload
```
Servidor disponible en: http://localhost:8000  
Documentación interactiva: http://localhost:8000/docs

---

## Endpoints disponibles

### POST /api/v1/predictions/predict
Predicción manual. Tú le das los números, él predice.

**Body:**
```json
{
  "pm25": 25.0,
  "pm10": 40.0,
  "temperature": 28.0,
  "humidity": 75.0
}
```

**Respuesta:**
```json
{
  "prediction": 9.74,
  "category": "Buena",
  "aqi_color": "#00E400",
  "timestamp": "2026-05-15T20:13:22Z",
  "data_source": "manual"
}
```

### GET /api/v1/predictions/current
Predicción automática usando datos en vivo del sensor Smart Citizen.
Requiere que el sensor esté publicando datos.

### GET /api/v1/predictions/model-info
Muestra información del modelo: features, fecha de entrenamiento, importancia de variables.

---

## Categorías de calidad del aire (PM2.5 µg/m³)

| Rango | Categoría | Color |
|-------|-----------|-------|
| 0 – 12 | Buena | Verde #00E400 |
| 12.1 – 35.4 | Moderada | Amarillo #FFFF00 |
| 35.5 – 55.4 | Dañina para grupos sensibles | Naranja #FF7E00 |
| 55.5 – 150.4 | Dañina | Rojo #FF0000 |
| 150.5 – 250.4 | Muy dañina | Morado #8F3F97 |
| 250.5+ | Peligrosa | Marrón #7E0023 |

---

## Tests

Para verificar que todo funciona:
```bash
cd backend
venv/bin/pytest tests/test_predictions.py -v
```
Resultado esperado: **41 passed**

---

## Regenerar archivos del modelo (solo si se re-entrena)

Si el modelo se vuelve a entrenar en Google Colab, correr la celda de exportación
(Cell 81 en el notebook `Modelo_PM25_XGBoost.ipynb`) y copiar los 4 archivos
descargados a `backend/app/models/`.

Los archivos del modelo **no cambian** a menos que se re-entrene. No es necesario
volver a Colab para cada despliegue.

---

## Archivos modificados/creados en BE-03

```
backend/
├── app/
│   ├── models/                     ← NUEVO: directorio para archivos del modelo
│   │   ├── modelo_pm25.joblib      ← NUEVO: modelo entrenado
│   │   ├── features.json           ← NUEVO: features del modelo
│   │   ├── ica_breakpoints.json    ← NUEVO: escala AQI
│   │   └── metadata.json           ← NUEVO: metadatos del entrenamiento
│   ├── schemas/
│   │   └── prediction.py           ← IMPLEMENTADO: schemas de entrada/salida
│   ├── services/
│   │   └── model.py                ← IMPLEMENTADO: carga modelo, feature engineering, predicción
│   └── routers/
│       └── predictions.py          ← IMPLEMENTADO: 3 endpoints REST
├── tests/
│   ├── conftest.py                 ← NUEVO: fixtures para tests
│   └── test_predictions.py         ← NUEVO: 41 tests
├── pytest.ini                      ← NUEVO: configuración de tests
└── requirements.txt                ← ACTUALIZADO: pydantic>=2.11 para Python 3.14
```
