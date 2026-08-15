# Roda Credit API

API REST para simular y registrar solicitudes de crédito de bicicletas y motos eléctricas.

Prueba técnica — vacante Full Stack Developer (Roda).

El cliente web vive en un repositorio aparte:
[PruebaTecnicaRodaFrontend](https://github.com/Chrispin12/PruebaTecnicaRodaFrontend).

Esta API es la **única fuente de verdad financiera**. Calcula cuota, intereses, valor
financiado, totales y tabla de amortización. El frontend solo captura datos, llama a estos
endpoints y muestra la respuesta.

---

## Qué resuelve

Una persona indica tipo de vehículo, valor, cuota inicial y plazo. Recibe un plan de pagos.
Si decide continuar, registra nombre, apellido, correo, teléfono y ciudad. Esa solicitud queda
persistida en PostgreSQL junto con las condiciones y el resultado financiero **recalculado en
el servidor** (nunca se confía en cifras enviadas por el cliente).

Cumple el enunciado:

| Requisito | Cómo |
| --- | --- |
| RF-01 Formulario de simulación | `POST /api/v1/simulations` |
| RF-02 Cálculo en backend | Motor en `app/domain` |
| RF-03 / RF-04 Resumen y amortización | Respuesta de simulación + `schedule` |
| RF-05 Solicitud persistida | `POST /api/v1/credit-applications` + tabla `credit_applications` |
| Validaciones | Pydantic (estructura) + dominio (negocio) + CHECK en PostgreSQL |

---

## Stack

| Pieza | Uso |
| --- | --- |
| Python 3.12 | Runtime (`requires-python >= 3.11`) |
| FastAPI | HTTP, OpenAPI en `/docs` |
| Pydantic v2 + pydantic-settings | Contratos y configuración por entorno |
| SQLAlchemy 2.x | ORM |
| Alembic | Migraciones versionadas |
| PostgreSQL 16 | Persistencia (`NUMERIC`, no float) |
| psycopg 3 | Driver |
| Uvicorn | Servidor ASGI |
| pytest + ruff | Tests y calidad |
| Docker / Compose | Local y producción (Cloud Run) |

---

## Arquitectura

Monolito modular. Una petición recorre capas con una responsabilidad cada una:

```
HTTP
  → Route (delgado)
    → Schema Pydantic (estructura)
      → Service (caso de uso)
        → Credit Engine / reglas (dominio puro)
        → Repository → PostgreSQL   (solo al persistir)
      → Response
```

```
app/
├── api/            Rutas, dependencias, traducción de excepciones a HTTP
├── core/           Configuración, excepciones de aplicación, logging
├── db/             Engine, sesión, tipos monetarios, base declarativa
├── domain/         Motor financiero y reglas. Sin FastAPI, SQLAlchemy ni PostgreSQL
├── models/         Modelos SQLAlchemy (no se usan como JSON)
├── repositories/   Único lugar que usa la sesión de SQLAlchemy
├── schemas/        Contratos de entrada y salida
└── services/       Casos de uso
```

Decisiones que sostienen esto:

- **El dominio no conoce infraestructura.** `tests/test_domain_purity.py` falla si alguien
  importa FastAPI o SQLAlchemy desde `app/domain`.
- **Los modelos ORM no son el contrato HTTP.** Tabla y API cambian por razones distintas.
- **Cada regla tiene un dueño.** Umbrales en `app/domain/rules.py`; Pydantic valida tipos y
  obligatoriedad; los `CHECK` de PostgreSQL protegen la tabla aunque se escriba a mano.
- **Simular no persiste.** Evita guardar simulaciones abandonadas. Solicitar sí inserta.

---

## Cómo ejecutar

Requisitos: Docker Desktop (recomendado) o Python 3.12 + PostgreSQL 16.

### Docker Compose (recomendado)

```bash
cp .env.example .env
docker compose up --build --wait
```

| Recurso | URL |
| --- | --- |
| API | http://localhost:8000 |
| OpenAPI | http://localhost:8000/docs |
| Health | http://localhost:8000/health |

Compose levanta PostgreSQL 16 (volumen persistente + healthcheck) y la API. Aplica
`alembic upgrade head` al arrancar **porque en local hay una sola instancia**.

Si el puerto 5432 ya está ocupado en el host:

```
POSTGRES_PORT=5433
```

en `.env`, y ajusta `DATABASE_URL` / `TEST_DATABASE_URL` al mismo puerto. Dentro de la red de
Compose la API habla con el servicio `db` en el 5432 interno; Compose pisa `DATABASE_URL`.

### Sin Docker

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

PostgreSQL debe estar accesible con las URLs de `.env`.

---

## Variables de entorno

Todo lo configurable sale del entorno. `.env` está en `.gitignore`. Copia `.env.example`.

| Variable | Descripción |
| --- | --- |
| `DATABASE_URL` | Conexión de la API (`postgresql+psycopg://…`) |
| `TEST_DATABASE_URL` | Base de los tests de integración |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` | Contenedor local |
| `ENVIRONMENT` | `local`, `test` o `production`. En `production` CORS no puede ser `*` |
| `LOG_LEVEL` | Logs a stdout (Cloud Run los recolecta) |
| `CORS_ALLOW_ORIGINS` | Orígenes separados por coma. Local: `http://localhost:5173` |
| `CREDIT_ANNUAL_RATE` | Tasa de la demo, **efectiva anual** en fracción (`0.24` = 24 % E.A.) |
| `CREDIT_MAX_ANNUAL_RATE` | Tope de tasa que el sistema acepta |

No hay secretos en la imagen Docker. En producción `DATABASE_URL` va a Secret Manager.

La tasa por defecto **no es la tasa comercial de Roda**. Es un supuesto de demo porque el
enunciado no define una.

---

## Endpoints

Prefijo de negocio: `/api/v1`. `/health` queda fuera a propósito: es sonda de infraestructura.

### `GET /health`

Proceso vivo **y** PostgreSQL alcanzable (`SELECT 1`). Un 200 aquí demuestra que Cloud SQL
está bien cableado, no solo que el contenedor arrancó.

```json
{ "status": "ok", "version": "0.1.0", "database": "ok" }
```

Si la base no responde: `503` / `SERVICE_UNAVAILABLE`.

### `POST /api/v1/simulations`

Cálculo. **No escribe en la base.** Responde `200` (no se crea un recurso).

El cliente envía solo condiciones. Cuota, intereses, financiado, total y tasa los calcula el
servidor. Si el cliente manda esos campos: `422` (`extra="forbid"`).

**Request**

```json
{
  "vehicle_type": "electric_motorcycle",
  "vehicle_value": "8000000.00",
  "down_payment": "2000000.00",
  "term_months": 24
}
```

`vehicle_type`: `electric_bicycle` | `electric_motorcycle`.

**Response `200`**

```json
{
  "vehicle_type": "electric_motorcycle",
  "vehicle_value": "8000000.00",
  "down_payment": "2000000.00",
  "financed_amount": "6000000.00",
  "term_months": 24,
  "annual_interest_rate": "0.24",
  "monthly_interest_rate": "0.018088",
  "monthly_payment": "310395.84",
  "total_interest": "1449499.98",
  "total_payment": "7449499.98",
  "schedule": [
    {
      "installment_number": 1,
      "payment": "310395.84",
      "interest": "108525.49",
      "principal": "201870.35",
      "remaining_balance": "5798129.65"
    }
  ]
}
```

Los importes van como **cadenas**: Pydantic serializa `Decimal` así y un `number` JSON pasaría
por float en JavaScript. El frontend solo formatea.

`monthly_interest_rate` es informativa (6 decimales). La cuota se calcula con la tasa sin
redondear.

### `POST /api/v1/credit-applications`

Registro formal (RF-05). Responde `201`.

El backend **vuelve a calcular** el crédito. El cliente no envía cuota ni tasa.

```
Request → Schema → CreditApplicationService → Credit Engine
                         ↓
              Repository → INSERT + COMMIT → Response desde la fila
```

**Request**

```json
{
  "first_name": "Laura",
  "last_name": "Gomez",
  "email": "laura.gomez@example.com",
  "phone": "3001234567",
  "city": "Bogota",
  "vehicle_type": "electric_motorcycle",
  "vehicle_value": "8000000.00",
  "down_payment": "2000000.00",
  "term_months": 24
}
```

**Response `201`:** `id`, `created_at`, datos del solicitante, condiciones y resultado
financiero persistido. No incluye `schedule` (es derivable; el cliente ya lo vio al simular).

Transacción atómica. Si falla la persistencia: rollback, `500` genérico al cliente, detalle
solo en logs.

Validación estructural: nombres y ciudad no vacíos (se recortan espacios); `EmailStr`;
teléfono 7–15 dígitos, `+` opcional. No se verifica que el correo o el teléfono existan.

### Errores

Mismo sobre en todos los endpoints:

```json
{
  "error": {
    "code": "BUSINESS_RULE_VIOLATION",
    "message": "El valor del vehiculo debe ser mayor o igual a $500.000 COP."
  }
}
```

| HTTP | `code` | Cuándo |
| --- | --- | --- |
| 400 | `BUSINESS_RULE_VIOLATION` | Cuerpo válido, regla de negocio incumplida |
| 422 | `VALIDATION_ERROR` | Contrato. Incluye `details` por campo |
| 404 | `NOT_FOUND` | Ruta inexistente |
| 503 | `SERVICE_UNAVAILABLE` | Dependencia caída |
| 500 | `INTERNAL_ERROR` | Inesperado. Sin traceback al cliente |

422 = “no entiendo lo que enviaste”. 400 = “te entiendo, esa operación no es posible”.

CORS: métodos `GET` y `POST`, cabecera `Content-Type`. En producción `CORS_ALLOW_ORIGINS=*`
impide arrancar.

---

## Reglas de negocio

Única fuente: `app/domain/rules.py`.

| Regla | Origen |
| --- | --- |
| Valor del vehículo ≥ $500.000 COP | Enunciado |
| Cuota inicial ≥ 0 | Enunciado |
| Cuota inicial ≤ valor del vehículo | Enunciado |
| Monto financiado > 0 | Derivada: si la inicial iguala el valor, no hay crédito |
| Valor del vehículo ≤ $1.000.000.000 COP | Protección técnica (NUMERIC), no regla de Roda |
| Plazo entre 1 y 60 meses | Supuesto técnico |
| Tasa configurada ≤ `CREDIT_MAX_ANNUAL_RATE` | Supuesto / configuración |

---

## Supuestos financieros

El enunciado no define tasa ni sistema de amortización. **Nada de lo siguiente es una
condición comercial de Roda.**

- **Tasa:** `CREDIT_ANNUAL_RATE` como efectiva anual. Demo por defecto: 24 % E.A.
- **Tope:** `CREDIT_MAX_ANNUAL_RATE` (demo 45 % E.A.), configurable porque los límites legales
  cambian.
- **Conversión a mensual:** \((1 + EA)^{1/12} - 1\). No se divide EA / 12 (eso sería nominal).
- **Amortización francesa** (cuota fija), encapsulada para poder cambiar el sistema.
- **Decimal + `ROUND_HALF_UP`** a 2 decimales en importes. Las tasas intermedias no se
  redondean. La **última cuota liquida el saldo exacto** (`0.00`). Totales = suma de la tabla,
  nunca cuota × plazo.
- **Moneda:** COP. Formato `$10.000.000 COP` en `app/domain/money.py`.

---

## Modelo de datos

Una tabla: `credit_applications`. No hay `Customer`, `Credit` ni `PaymentInstallment`: para
este alcance añadirían joins sin resolver un problema.

| Grupo | Columnas |
| --- | --- |
| Identidad | `id` (UUID), `created_at` (timestamptz) |
| Solicitante | `first_name`, `last_name`, `email`, `phone`, `city` |
| Vehículo | `vehicle_type`, `vehicle_value`, `down_payment`, `term_months` |
| Parámetros | `annual_interest_rate`, `monthly_interest_rate` |
| Resultado | `financed_amount`, `monthly_payment`, `total_interest`, `total_payment` |

El resultado se persiste aunque sea derivable: es lo que se le presentó al solicitante. Si
mañana cambia la tasa de demo, una solicitud antigua no debe recalcularse.

La amortización no se guarda: es determinista a partir de esos parámetros.

Importes: `NUMERIC(14,2)`. Tasas: `NUMERIC(8,6)`. CHECK en tabla para invariantes. El rango
de plazo no está en un CHECK (es configuración del dominio).

Migraciones: Alembic. No `create_all`.

```bash
alembic upgrade head
alembic revision --autogenerate -m "descripcion"
alembic check
alembic downgrade -1
```

En **producción** las migraciones no van en el startup de Cloud Run (varias instancias
competirían). Van en un Cloud Run Job de una sola tarea.

---

## Docker

Imagen multi-stage (`Dockerfile`): virtualenv en el builder; runtime slim, usuario `uid 1000`,
sin `.env`. Escucha `0.0.0.0` y `$PORT`. `exec uvicorn` queda como PID 1 (SIGTERM + lifespan
que cierra el pool). `--proxy-headers` porque Cloud Run termina TLS.

```bash
docker compose up --build --wait
docker build -t roda-credit-api:local .
```

---

## Tests y calidad

Los de integración usan PostgreSQL real (NUMERIC y CHECK). El esquema se aplica con Alembic.
Cada test corre en una transacción que se revierte.

```bash
pytest
ruff check .
ruff format --check .
alembic check
```

Cubre motor (cuotas, redondeo, límites, tasa), API de simulación y de solicitudes (incluido
que el cliente no pueda imponer la cuota), salud, CORS en producción y pureza del dominio.

---

## Producción (Cloud Run + Cloud SQL)

```
Frontend (Vercel) → esta API (Cloud Run) → PostgreSQL (Cloud SQL)
```

- Contenedor stateless, `PORT` inyectado, pool pequeño (`5` + overflow `5`, recycle 30 min).
- Socket Unix: `postgresql+psycopg://USER:PASSWORD@/DBNAME?host=/cloudsql/PROJECT:REGION:INSTANCE`
- Secretos en Secret Manager (`--set-secrets`).
- Migraciones: Job `alembic upgrade head`, luego el servicio HTTP.

Esquema de comandos (sustituir placeholders; no hay IDs inventados):

```bash
docker build -t REGION-docker.pkg.dev/PROJECT/REPO/roda-credit-api:TAG .
docker push REGION-docker.pkg.dev/PROJECT/REPO/roda-credit-api:TAG

gcloud run jobs deploy roda-credit-migrate \
  --image REGION-docker.pkg.dev/PROJECT/REPO/roda-credit-api:TAG \
  --region REGION \
  --set-cloudsql-instances PROJECT:REGION:INSTANCE \
  --set-secrets DATABASE_URL=roda-database-url:latest \
  --command alembic \
  --args upgrade,head \
  --max-retries 0

gcloud run jobs execute roda-credit-migrate --region REGION --wait

gcloud run deploy roda-credit-api \
  --image REGION-docker.pkg.dev/PROJECT/REPO/roda-credit-api:TAG \
  --region REGION \
  --allow-unauthenticated \
  --add-cloudsql-instances PROJECT:REGION:INSTANCE \
  --set-secrets DATABASE_URL=roda-database-url:latest \
  --set-env-vars ENVIRONMENT=production,CORS_ALLOW_ORIGINS=https://TU-FRONTEND.vercel.app \
  --port 8000
```

`--allow-unauthenticated` coincide con el enunciado (no hay login).

**¿Por qué Cloud Run?** Contenedor HTTP sin VMs. **¿Por qué Cloud SQL?** PostgreSQL
administrado junto a Cloud Run. **¿Por qué no K8s/Redis/JWT?** El enunciado no los pide.

---

## Fuera de alcance (a propósito)

Autenticación, JWT, KYC, documento de identidad, CRUD de solicitudes, microservicios.

---

## Licencia / contexto

Código de prueba técnica. Los supuestos financieros no representan productos reales de Roda.
