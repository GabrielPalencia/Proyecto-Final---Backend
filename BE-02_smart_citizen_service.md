# BE-02 · Servicio de Integración con Smart Citizen API

## Contexto

La API de Smart Citizen (`https://api.smartcitizen.me/v0/`) es una API REST pública que expone los datos de sensores IoT. Tu dispositivo es un **Smart Citizen Kit (SCK)** registrado en la plataforma con un `DEVICE_ID` numérico.

Los endpoints relevantes que usarás son:

| Endpoint | Descripción |
|---|---|
| `GET /v0/devices/:id` | Retorna el dispositivo completo con las **últimas lecturas** en `data.sensors[].value` |
| `GET /v0/devices/:device_id/readings` | Retorna lecturas **históricas** para un sensor específico con rollup temporal |

### Sensores del SCK que necesitas mapear

Los sensores disponibles en el SCK 2.1 tienen IDs numéricos en la plataforma. Los relevantes para calidad del aire son:

| Sensor Name | ID típico | Unidad | Variable modelo |
|---|---|---|---|
| PM 1.0 | 89 | µg/m³ | `pm1` |
| PM 2.5 | 87 | µg/m³ | `pm25` |
| PM 10 | 88 | µg/m³ | `pm10` |
| Temperature | 55 | ºC | `temperature` |
| Humidity | 56 | % | `humidity` |
| CO2 (si aplica) | 112 | ppm | `co2` |
| NO2 (si aplica) | 43 | ppb | `no2` |

> **Nota:** Los IDs exactos de tus sensores pueden diferir. Para obtenerlos, llama a `GET https://api.smartcitizen.me/v0/devices/{TU_DEVICE_ID}` y revisa el campo `data.sensors[].id` junto a `data.sensors[].name` en la respuesta.

---

## Objetivo de esta tarea

Implementar el servicio `app/services/smart_citizen.py` y el router `app/routers/sensor.py` con todos los endpoints necesarios para que el frontend pueda consultar:

1. Las lecturas actuales del sensor (último valor de cada sensor)
2. El histórico de lecturas de un sensor específico para graficar

---

## Schemas Pydantic a crear en `app/schemas/sensor.py`

### `SensorReading`
Representa la lectura de un sensor individual:
```python
class SensorReading(BaseModel):
    sensor_id: int
    name: str
    description: str
    unit: str
    value: float | None
    recorded_at: datetime | None
```

### `DeviceStatus`
Representa el estado general del dispositivo:
```python
class DeviceStatus(BaseModel):
    device_id: int
    name: str
    state: str              # "has_published" | "never_published" | etc.
    last_reading_at: datetime | None
    latitude: float | None
    longitude: float | None
    city: str | None
    sensors: list[SensorReading]
```

### `HistoricalReading`
Para una lectura en serie de tiempo:
```python
class HistoricalReading(BaseModel):
    timestamp: datetime
    value: float | None
```

### `HistoricalResponse`
```python
class HistoricalResponse(BaseModel):
    device_id: int
    sensor_id: int
    sensor_name: str
    unit: str
    rollup: str
    from_date: datetime
    to_date: datetime
    readings: list[HistoricalReading]
```

---

## Servicio `app/services/smart_citizen.py`

Implementa una clase `SmartCitizenService` usando `httpx.AsyncClient`:

### `__init__`
- Recibe `base_url` y `device_id` desde `settings`
- Crea un `httpx.AsyncClient` con `timeout=10.0` y `base_url`

### Método `async get_device_current_readings() -> dict`

Llama a `GET /v0/devices/{device_id}` y retorna el JSON completo. Maneja los siguientes errores:
- `httpx.TimeoutException` → lanza `HTTPException(504, "Timeout al conectar con Smart Citizen API")`
- `httpx.HTTPStatusError` con status 404 → `HTTPException(404, "Dispositivo no encontrado")`
- Cualquier otro error HTTP → `HTTPException(502, "Error al obtener datos del sensor")`

### Método `async get_historical_readings(sensor_id, rollup, from_date, to_date, function) -> dict`

Llama a `GET /v0/devices/{device_id}/readings` con los query params:
- `sensor_id`: ID del sensor
- `rollup`: agrupación temporal (ej: `1h`, `1d`, `30m`)
- `from`: fecha inicio en formato ISO 8601
- `to`: fecha fin en formato ISO 8601
- `function`: función de agregación (`avg` por defecto)

Retorna el JSON con la estructura:
```json
{
  "device_id": 1234,
  "sensor_id": 87,
  "rollup": "1h",
  "function": "avg",
  "from": "2024-01-01T00:00:00Z",
  "to": "2024-01-07T00:00:00Z",
  "sample_size": 168,
  "readings": [["2024-01-01T00:00:00Z", 12.5], ...]
}
```

### Método `parse_current_readings(device_data: dict) -> DeviceStatus`

Transforma la respuesta cruda de la API en el schema `DeviceStatus`. Los sensores vienen en `device_data["data"]["sensors"]`. Mapea:
- `id` → `sensor_id`
- `name` → `name`
- `description` → `description`
- `unit` → `unit`
- `value` → `value`
- Usa `device_data["data"]["recorded_at"]` como `recorded_at` para todos los sensores

### Método `parse_historical_readings(raw: dict, sensor_name: str, unit: str) -> HistoricalResponse`

Transforma el array de tuplas `[timestamp, value]` en una lista de `HistoricalReading`. Cada elemento del array `readings` tiene la forma `["2015-07-29T20:00:35Z", 65.78]`.

---

## Router `app/routers/sensor.py`

Implementa los siguientes endpoints:

### `GET /api/v1/sensor/current`

**Descripción:** Retorna las lecturas más recientes de todos los sensores del dispositivo.

**Response:** `DeviceStatus`

**Lógica:**
1. Llama a `smart_citizen_service.get_device_current_readings()`
2. Parsea con `parse_current_readings()`
3. Retorna el resultado

**Ejemplo de respuesta:**
```json
{
  "device_id": 12345,
  "name": "Sensor Barranquilla Norte",
  "state": "has_published",
  "last_reading_at": "2024-05-01T14:30:00Z",
  "latitude": 10.9878,
  "longitude": -74.7889,
  "city": "Barranquilla",
  "sensors": [
    {
      "sensor_id": 87,
      "name": "PM 2.5",
      "description": "Particulate matter < 2.5µm",
      "unit": "µg/m³",
      "value": 18.4,
      "recorded_at": "2024-05-01T14:30:00Z"
    }
  ]
}
```

### `GET /api/v1/sensor/historical/{sensor_id}`

**Descripción:** Retorna el histórico de lecturas de un sensor para graficar.

**Path params:** `sensor_id: int`

**Query params:**
- `rollup: str = "1h"` — agrupación (ej: `30m`, `1h`, `4h`, `1d`)
- `from_date: datetime` — fecha inicio (requerido)
- `to_date: datetime` — fecha fin (requerido)
- `function: str = "avg"` — función de agregación

**Response:** `HistoricalResponse`

**Validaciones:**
- Si `to_date <= from_date`, retornar `400 Bad Request`
- Si el rango supera 30 días, retornar `400 Bad Request` con mensaje "El rango máximo es 30 días"

### `GET /api/v1/sensor/sensors`

**Descripción:** Retorna la lista de sensores disponibles en el dispositivo con sus IDs (útil para construir selectores en el frontend).

**Response:** `list[SensorReading]`

**Lógica:** Llama a `get_device_current_readings()` y retorna solo el array de sensores sin los valores.

---

## Caché simple con diccionario en memoria

Para no sobrepasar el rate limit de Smart Citizen (90 req/min para ciudadanos), implementa un caché simple para `GET /api/v1/sensor/current`:

```python
from datetime import datetime, timedelta

_cache = {}

def get_cached(key: str, ttl_seconds: int):
    if key in _cache:
        data, timestamp = _cache[key]
        if datetime.now() - timestamp < timedelta(seconds=ttl_seconds):
            return data
    return None

def set_cached(key: str, data):
    _cache[key] = (data, datetime.now())
```

Usa `settings.cache_ttl_seconds` (60s por defecto) como TTL para las lecturas actuales.

---

## Criterios de aceptación

- [ ] `GET /api/v1/sensor/current` retorna las lecturas actuales del dispositivo en formato `DeviceStatus`
- [ ] `GET /api/v1/sensor/historical/87?rollup=1h&from_date=2024-01-01&to_date=2024-01-07` retorna datos históricos correctamente
- [ ] `GET /api/v1/sensor/sensors` retorna la lista de sensores disponibles
- [ ] Las peticiones a Smart Citizen usan `httpx.AsyncClient` (no `requests` síncrono)
- [ ] Errores de red se traducen a HTTPExceptions apropiadas
- [ ] El caché evita llamar a la API más de una vez por minuto para lecturas actuales

---

## Notas técnicas

- La API de Smart Citizen no requiere autenticación para leer datos de dispositivos públicos.
- El campo `value` puede ser `null` si el sensor no ha reportado recientemente; maneja este caso en el schema con `float | None`.
- Los timestamps en la API vienen en UTC formato ISO 8601: `"2015-07-16T08:53:16Z"`.
- Para el rollup de lecturas históricas, los valores válidos son combinaciones como: `30s`, `1m`, `5m`, `1h`, `4h`, `1d`, `1w`.
