# Imagen de produccion (Cloud Run). Dos etapas: las dependencias se instalan en un
# virtualenv que la imagen final copia, dejando fuera el toolchain de compilacion.
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml ./
COPY app ./app
RUN pip install .


FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
# El codigo de la aplicacion viaja instalado en el venv; solo se copian las migraciones,
# que se ejecutan como paso separado y no forman parte del paquete.
COPY alembic ./alembic
COPY alembic.ini ./

RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000

# Cloud Run inyecta $PORT; en local se usa 8000. Hace falta una shell para expandir la
# variable, y `exec` para que uvicorn sustituya a esa shell y quede como PID 1: asi recibe el
# SIGTERM que envia Cloud Run al retirar la instancia y puede cerrar con las peticiones en
# curso terminadas (lifespan de FastAPI). `--proxy-headers` porque Cloud Run termina TLS y
# reenvia X-Forwarded-*.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
