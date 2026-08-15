# Roda Credit API

API REST para simular y registrar solicitudes de crédito de bicicletas y motos eléctricas.

Prueba técnica — vacante Full Stack Developer (Roda).

**API en producción:** [https://roda-credit-api-446921260054.us-central1.run.app](https://roda-credit-api-446921260054.us-central1.run.app)

| Recurso | URL |
| --- | --- |
| Health | [GET /health](https://roda-credit-api-446921260054.us-central1.run.app/health) |
| OpenAPI | [/docs](https://roda-credit-api-446921260054.us-central1.run.app/docs) |
| Frontend | [prueba-tecnica-roda-frontend.vercel.app](https://prueba-tecnica-roda-frontend.vercel.app) |

El cliente web: [PruebaTecnicaRodaFrontend](https://github.com/Chrispin12/PruebaTecnicaRodaFrontend).

Esta API es la **única fuente de verdad financiera**. Calcula cuota, intereses, valor
financiado, totales y tabla de amortización. El frontend solo captura datos, llama a estos
endpoints y muestra la respuesta.

---

## Qué resuelve

Una persona indica tipo de vehículo, valor, cuota inicial y plazo. Recibe un plan de pagos.
Si decide continuar, registra nombre, apellido, documento de identidad, correo, teléfono y
ciudad. Esa solicitud queda persistida en PostgreSQL junto con las condiciones y el resultado
financiero **recalculado en el servidor** (nunca se confía en cifras enviadas por el cliente).
La cédula identifica al cliente: puede tener varios créditos; el correo puede cambiar; nombre
y contacto de la primera solicitud no se pisan.

Cumple el enunciado:

| Requisito | Cómo |
| --- | --- |
| RF-01 Formulario de simulación | `POST /api/v1/simulations` |
| RF-02 Cálculo en backend | Motor en `app/domain` |
| RF-03 / RF-04 Resumen y amortización | Respuesta de simulación + `schedule` |
| RF-05 Solicitud persistida | `POST /api/v1/credit-applications` + `customers` + `credit_applications` |
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
              Repository → upsert customer + INSERT solicitud → Response
```

**Request**

```json
{
  "first_name": "Laura",
  "last_name": "Gomez",
  "document_type": "cc",
  "document_number": "1023456789",
  "email": "laura.gomez@example.com",
  "phone": "3001234567",
  "city": "Bogota",
  "vehicle_type": "electric_motorcycle",
  "vehicle_value": "8000000.00",
  "down_payment": "2000000.00",
  "term_months": 24
}
```

**Response `201`:** `id`, `customer_id`, `created_at`, datos del solicitante, condiciones y
resultado financiero persistido. No incluye `schedule`.

Identidad (sin JWT):

- Misma cédula + mismos nombre/apellido → mismo cliente, N créditos.
- El correo puede cambiar si no lo usa otra cédula.
- Nombre, teléfono y ciudad de la **primera** solicitud se conservan.
- Mismo correo con **otra** cédula, o nombre que no coincide con la cédula: `400`.

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

Dos tablas: `customers` (identidad, email único) y `credit_applications` (cada crédito, FK a
cliente). Un cliente puede tener varias solicitudes. El vehículo queda como snapshot en la
solicitud (tipo + valor): no hay inventario ni placa, así que no hay tabla `vehicles`.

No hay login. La cédula identifica al cliente: N solicitudes, el correo puede cambiar si
está libre. Nombre, teléfono y ciudad quedan de la **primera** solicitud. El mismo correo
con otra cédula se rechaza.

| Tabla | Qué guarda |
| --- | --- |
| `customers` | `id`, nombre, documento (tipo + número, único), `email` (único), teléfono, ciudad, `created_at` |
| `credit_applications` | `id`, `customer_id`, vehículo, tasas usadas, resultado financiero, `created_at` |

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

**URL pública de la API:**
[https://roda-credit-api-446921260054.us-central1.run.app](https://roda-credit-api-446921260054.us-central1.run.app)

```
Navegador → Vercel (SPA) → Cloud Run (esta API) → Cloud SQL (PostgreSQL 16)
```

### Cómo está desplegado este entorno

| Recurso | Valor |
| --- | --- |
| Proyecto GCP | `roda-credit-cs0603` |
| Región | `us-central1` |
| Servicio Cloud Run | `roda-credit-api` |
| Imagen | `us-central1-docker.pkg.dev/roda-credit-cs0603/roda/roda-credit-api:v3` |
| Instancia Cloud SQL | `roda-pg` (PostgreSQL 16, Enterprise, `db-f1-micro`) |
| Conexión | `roda-credit-cs0603:us-central1:roda-pg` |
| Base / usuario | `roda` / `roda_app` |
| Secret | `roda-database-url` (inyectado como `DATABASE_URL`) |
| Job de migraciones | `roda-credit-migrate` (`alembic upgrade head`) |
| CORS | `https://prueba-tecnica-roda-frontend.vercel.app` |

### Cómo se almacena la información

1. El usuario simula (`POST /api/v1/simulations`): **no se escribe en base de datos**.
2. El usuario solicita crédito (`POST /api/v1/credit-applications`): el servidor **recalcula**
   el plan y, en una transacción, resuelve el cliente por **cédula** (alta o reutilización) e
   inserta una fila en `credit_applications`. El correo se actualiza si cambió y está libre.
3. En `customers` queda la identidad. Nombre/teléfono/ciudad no se pisan después del primer
   registro. En la solicitud quedan vehículo, tasas y resultado. **No** se guarda la amortización.
4. Cloud Run llega a Cloud SQL por **socket Unix** del sidecar `/cloudsql/...`, no por IP
   pública. La contraseña no está en el código: vive en Secret Manager.

```
postgresql+psycopg://USER:PASSWORD@/DBNAME?host=/cloudsql/PROJECT:REGION:INSTANCE
```

Consultar filas (Cloud Shell / gcloud):

```bash
gcloud sql connect roda-pg --user=roda_app --database=roda --project=roda-credit-cs0603
```

```sql
SELECT id, first_name, last_name, email, vehicle_type, monthly_payment, created_at
FROM credit_applications
ORDER BY created_at DESC
LIMIT 10;
```

### Proceso de despliegue (resumen)

1. Crear instancia Cloud SQL y base `roda`.
2. Guardar `DATABASE_URL` en Secret Manager.
3. Construir y subir la imagen a Artifact Registry.
4. Ejecutar el Job `roda-credit-migrate` (Alembic). **No** migrar en el arranque del servicio.
5. Desplegar `roda-credit-api` con Cloud SQL, secreto, `ENVIRONMENT=production` y CORS.
6. Apuntar Vercel (`VITE_API_URL`) a esta URL y redesplegar el frontend.

- Contenedor stateless, `PORT` inyectado, pool pequeño (`5` + overflow `5`, recycle 30 min).
- `--proxy-headers` porque Cloud Run termina TLS.
- `--allow-unauthenticated`: el enunciado no pide login.

Esquema de comandos (referencia; este entorno ya está creado):

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

Autenticación, JWT, verificación KYC, CRUD de solicitudes, microservicios.

---

## Licencia / contexto

Código de prueba técnica. Los supuestos financieros no representan productos reales de Roda.
