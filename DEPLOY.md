# Despliegue web

La app va empaquetada en un `Dockerfile` (Python 3.12 + Chromium), así que corre
igual en cualquier proveedor que acepte contenedores.

## Antes de desplegar

Genera las dos claves:

```bash
python3 -c "import secrets; print('APP_PASSWORD    =', secrets.token_urlsafe(24))"
python3 -c "import secrets; print('FLASK_SECRET_KEY=', secrets.token_hex(32))"
```

Guárdalas en el gestor de secretos del proveedor, **nunca en el repositorio ni
en el Dockerfile**. La app se niega a arrancar en `ENTORNO=web` sin `APP_PASSWORD`.

### Variables de entorno

| Variable | Obligatoria | Valor |
|---|---|---|
| `ENTORNO` | sí | `web` |
| `APP_PASSWORD` | sí | contraseña de acceso |
| `FLASK_SECRET_KEY` | recomendada | firma la cookie de sesión; si falta, cada despliegue cierra las sesiones |
| `RETENCION_MINUTOS` | no | minutos antes de borrar los informes (por defecto 30) |
| `PORT` | la pone el proveedor | puerto de escucha |
| `WEB_CONCURRENCY` | no | workers de gunicorn (por defecto 2) |

La imagen ya define `CHROME_PATH=/usr/bin/chromium` y `SALIDAS_DIR=/tmp/salidas`.

## Requisitos de la instancia

Chromium es lo que manda: **mínimo 1 GB de RAM, recomendado 2 GB**, y un timeout
de petición de al menos 120 s (una corrida completa tarda unos 20–40 s). Con menos
memoria Chromium muere y el informe falla.

## Google Cloud Run

Escala a cero, así que sin uso no cuesta nada. Es la opción que recomiendo.

```bash
gcloud run deploy proyectapension \
  --source . \
  --region us-central1 \
  --memory 2Gi --cpu 2 \
  --timeout 300 \
  --max-instances 3 \
  --allow-unauthenticated \
  --set-env-vars ENTORNO=web,RETENCION_MINUTOS=30 \
  --set-secrets APP_PASSWORD=proyectapension-password:latest,FLASK_SECRET_KEY=proyectapension-secret:latest
```

Crea antes los secretos:

```bash
printf 'TU_PASSWORD' | gcloud secrets create proyectapension-password --data-file=-
printf 'TU_SECRET'   | gcloud secrets create proyectapension-secret   --data-file=-
```

`--allow-unauthenticated` deja pasar el tráfico hasta la app, que aplica su propia
contraseña. Si prefieres que Google haga el control de acceso, quita esa bandera y
usa Identity-Aware Proxy con las cuentas que autorices.

**Ojo:** en Cloud Run `/tmp` es memoria RAM, no disco. Los informes pesan ~400 KB,
así que no es problema, pero cuenta contra los 2 GB.

## Fly.io

```bash
fly launch --no-deploy --name proyectapension
fly secrets set ENTORNO=web APP_PASSWORD='...' FLASK_SECRET_KEY='...'
fly scale memory 2048
fly deploy
```

## Render

Crea un servicio web con runtime **Docker**, apuntando al repositorio. Define las
variables de entorno en el panel y elige un plan con 2 GB de RAM. El plan gratuito
(512 MB) no alcanza para Chromium.

## VPS con Docker

```bash
docker build -t proyectapension .
docker run -d --name proyectapension \
  -p 8080:8080 \
  -e ENTORNO=web \
  -e APP_PASSWORD='...' \
  -e FLASK_SECRET_KEY='...' \
  --memory 2g --shm-size 512m \
  --restart unless-stopped \
  proyectapension
```

Ponle un reverse proxy con HTTPS delante (Caddy o Nginx + Let's Encrypt). **La app
manda cookies con la bandera `Secure`, así que sin HTTPS no se puede iniciar sesión.**

## Comprobar que quedó bien

```bash
curl https://TU-DOMINIO/salud
# {"estado":"ok","chrome":true,"hora":"..."}
```

Si `chrome` sale en `false`, Chromium no está en la imagen o `CHROME_PATH` apunta
mal, y los informes van a fallar.

Después verifica que `GET /` redirija a `/login` y que la cookie llegue con
`Secure; HttpOnly; SameSite=Lax`.

## Protecciones que trae la app

- Acceso por contraseña en todas las rutas, con comparación en tiempo constante.
- Bloqueo temporal tras 8 intentos fallidos por IP (compartido entre workers).
- El PDF cargado se borra apenas termina la extracción.
- Los informes se borran solos a los `RETENCION_MINUTOS`, y el usuario puede
  borrarlos antes desde la pantalla de resultado.
- Tokens de corrida de 128 bits, validados para evitar path traversal.
- Cabeceras `HSTS`, `X-Frame-Options`, `nosniff`, `Referrer-Policy` y `no-store`.
- Corre como usuario sin privilegios dentro del contenedor.
- Los logs no registran el contenido de los reportes ni las cadenas de consulta.

## Lo que falta si esto va a atender a terceros

Ahora mismo es una herramienta con una sola contraseña compartida, pensada para
uso propio o de un equipo pequeño. Si va a recibir historias laborales de clientes,
hace falta además:

- Usuarios individuales con su propia credencial, en vez de una clave compartida.
- Política de tratamiento de datos y autorización expresa del titular
  (Ley 1581 de 2012 y Decreto 1377 de 2013).
- Registro de auditoría de quién consultó qué.
- Rate limiting global en el WAF del proveedor: el de la app protege una sola
  instancia, no un despliegue con varias réplicas.
