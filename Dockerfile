# ProyectaPension — imagen para desplegar la app web
FROM python:3.12-slim

# Chromium se usa para convertir el informe HTML a PDF.
# Las fuentes DejaVu/Liberation cubren la tipografía serif del informe.
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        fonts-dejavu-core \
        fonts-liberation \
        libjpeg62-turbo \
        tini \
    && rm -rf /var/lib/apt/lists/*

ENV CHROME_PATH=/usr/bin/chromium \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENTORNO=web \
    SALIDAS_DIR=/tmp/salidas

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py gunicorn.conf.py ./
COPY proyecta_pension/ ./proyecta_pension/
COPY templates/ ./templates/

# Sin privilegios de root
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /tmp/salidas && chown -R app:app /tmp/salidas /app
USER app

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request,os; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/salud').read()"

# tini reapa los procesos de Chromium que quedan huérfanos
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]
