# ProyectaPension

Proyección de pensión de vejez en Colpensiones (régimen de prima media) a partir
del *Reporte de semanas cotizadas en pensiones* en PDF. Incluye un front local
para cargar el archivo y un informe final en PDF.

## Instalación

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Opcional: `cp .env.example .env` y define `FLASK_SECRET_KEY`.

Para generar el PDF se usa **Google Chrome** en modo headless (ya viene instalado
en la mayoría de equipos). También sirve Chromium, Edge o Brave.

## Uso local

```bash
.venv/bin/python app.py
```

Abre <http://127.0.0.1:5000>, arrastra el PDF de la historia laboral, escribe la
contraseña (Colpensiones usa el número de cédula) y genera el informe.

## Uso web

La app se despliega como contenedor. Ver **[DEPLOY.md](DEPLOY.md)**.

```bash
docker build -t proyectapension .
docker run -p 8080:8080 -e ENTORNO=web -e APP_PASSWORD='...' proyectapension
```

En `ENTORNO=web` la app exige contraseña de acceso, usa cookies seguras y borra
los informes automáticamente. Se niega a arrancar sin `APP_PASSWORD`.

## Uso por línea de comandos

```bash
.venv/bin/python proyecta_pension/extraer_historia.py historia.pdf CEDULA datos.json
.venv/bin/python proyecta_pension/motor_pension.py datos.json M > resultado.json
.venv/bin/python proyecta_pension/generar_pdf.py resultado.json Informe.pdf
```

`motor_pension.py` acepta un tercer argumento opcional con la fecha del cálculo
(`AAAA-MM-DD`) para reproducir corridas anteriores.

## Qué contiene el informe

| Sección | Pregunta que responde |
|---|---|
| 1 | ¿Cuánto sería la pensión si dejara de cotizar hoy? |
| 2 | ¿Cuánto será al cumplir la edad de pensión? |
| 3 | ¿Qué base de cotización necesitaría para pensionarse con el sueldo completo? |
| 4 | ¿Conviene retirarse apenas cumpla la edad, o cotizar unos meses más? |
| Anexo | Supuestos legales, estimaciones del modelo y advertencias |

## Estructura

```
app.py                        aplicación Flask
gunicorn.conf.py              configuración del servidor de producción
Dockerfile                    imagen con Python + Chromium
templates/                    plantillas del front
proyecta_pension/
  extraer_historia.py         PDF de Colpensiones → JSON
  motor_pension.py            motor de cálculo (IBL, tasa de reemplazo, escenarios)
  generar_pdf.py              JSON → informe en PDF
salidas/<token>/              resultados por corrida (no se versiona)
ESTADO.md                     bitácora del proyecto
DEPLOY.md                     guía de despliegue web
```

## Datos personales

El PDF cargado se borra apenas termina la extracción. Los resultados quedan en
`salidas/`, que está excluida de git junto con `.env` y los JSON intermedios. El
servidor escucha solo en `127.0.0.1`. Desde el front puedes borrar los archivos
de una corrida con un clic.

## Advertencia

Es una **herramienta de proyección educativa**, no una liquidación oficial ni
asesoría legal. Usa supuestos de IPC y salario mínimo para años que el Gobierno
aún no ha fijado. Valida siempre con Colpensiones antes de decidir.
