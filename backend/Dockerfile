FROM python:3.12-slim

# Sin buffer, los logs JSON salen a stdout apenas se emiten y no cuando se llena el buffer:
# la plataforma de hosting los necesita en orden y en tiempo real.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# El servicio no necesita privilegios: si alguna vez lo comprometen, que sea con las manos atadas.
RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000

# Railway inyecta PORT; Fly.io usa el internal_port de fly.toml y el default alcanza.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/api/v1/health', timeout=4).status==200 else 1)"

# Los secretos entran por variables de entorno de la plataforma (fly secrets / Railway vars).
# El .env no se copia nunca: está fuera del build context y además excluido en .dockerignore.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
