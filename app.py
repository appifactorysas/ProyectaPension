# -*- coding: utf-8 -*-
"""ProyectaPension — aplicación web para generar el informe pensional.

Sube el PDF de historia laboral de Colpensiones, corre el pipeline completo
(extracción → motor de cálculo → informe) y devuelve el PDF.

Local:      .venv/bin/python app.py            →  http://127.0.0.1:5000
Producción: gunicorn -c gunicorn.conf.py app:app

Variables de entorno: ver .env.example
"""
import hmac
import json
import logging
import os
import secrets
import shutil
import sys
import threading
import time
import traceback
from datetime import date, datetime, timezone
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, send_file, session, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'proyecta_pension'))
import extraer_historia          # noqa: E402
import motor_pension             # noqa: E402
import generar_pdf               # noqa: E402

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SALIDAS = os.environ.get('SALIDAS_DIR', os.path.join(BASE_DIR, 'salidas'))
MAX_MB = int(os.environ.get('MAX_UPLOAD_MB', '25'))
# Los resultados llevan datos personales: se borran solos pasado este tiempo.
RETENCION_MIN = int(os.environ.get('RETENCION_MINUTOS', '30'))
# Intentos de contraseña permitidos por IP antes de bloquear temporalmente.
MAX_INTENTOS = int(os.environ.get('MAX_INTENTOS_LOGIN', '8'))
BLOQUEO_SEG = int(os.environ.get('BLOQUEO_LOGIN_SEGUNDOS', '900'))

ENTORNO = os.environ.get('ENTORNO', 'local').lower()   # 'local' | 'web'
APP_USERNAME = os.environ.get('APP_USERNAME', '')
APP_PASSWORD = os.environ.get('APP_PASSWORD', '')
HTTPS_ENABLED = os.environ.get('HTTPS_ENABLED', '1').lower() not in ('0', 'false', 'no')

if ENTORNO == 'web' and not APP_PASSWORD:
    logging.warning(
        'ENTORNO=web sin APP_PASSWORD: la aplicación queda abierta sin contraseña. '
        'Los datos personales se siguen purgando por retención, pero cualquiera '
        'con la URL puede subir un PDF.')

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or secrets.token_hex(32)
app.config.update(
    MAX_CONTENT_LENGTH=MAX_MB * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=(ENTORNO == 'web' and HTTPS_ENABLED),
    PERMANENT_SESSION_LIFETIME=60 * 60 * 8,
)
if ENTORNO == 'web':
    # Detrás de Cloud Run / Fly / Render / Nginx: respetar X-Forwarded-*
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

# Los intentos fallidos se cuentan en un archivo compartido: gunicorn corre
# varios workers y un dict en memoria haría que cada uno contara por su lado.
# Nota: esto protege una instancia. Si el servicio escala a varias réplicas,
# el límite global debe ponerse en el WAF o rate limiter del proveedor.
_ARCHIVO_INTENTOS = os.path.join(SALIDAS, '.intentos.json')
_lock = threading.Lock()


def _leer_intentos():
    try:
        with open(_ARCHIVO_INTENTOS, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _escribir_intentos(d):
    tmp = _ARCHIVO_INTENTOS + f'.{os.getpid()}'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(d, f)
        os.replace(tmp, _ARCHIVO_INTENTOS)
    except OSError:
        pass


# ---------------------------------------------------------------------
# Retención: los resultados con datos personales no se quedan en disco
# ---------------------------------------------------------------------

def purgar_antiguos():
    if RETENCION_MIN <= 0 or not os.path.isdir(SALIDAS):
        return
    limite = time.time() - RETENCION_MIN * 60
    for nombre in os.listdir(SALIDAS):
        if nombre.startswith('.'):
            continue
        ruta = os.path.join(SALIDAS, nombre)
        try:
            if os.path.isdir(ruta) and os.path.getmtime(ruta) < limite:
                shutil.rmtree(ruta, ignore_errors=True)
                app.logger.info('Corrida %s purgada por antigüedad', nombre[:8])
        except OSError:
            pass


@app.before_request
def _antes():
    purgar_antiguos()


@app.after_request
def _cabeceras(resp):
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['X-Frame-Options'] = 'DENY'
    resp.headers['Referrer-Policy'] = 'no-referrer'
    # Nada de esto debe quedar cacheado: son datos personales.
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    if ENTORNO == 'web' and HTTPS_ENABLED:
        resp.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return resp


# ---------------------------------------------------------------------
# Control de acceso
# ---------------------------------------------------------------------

def ip_cliente():
    return (request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
            or request.remote_addr or '?')


def bloqueado(ip):
    with _lock:
        d = _leer_intentos()
        reg = d.get(ip)
        if not reg:
            return False
        conteo, desde = reg
        if conteo >= MAX_INTENTOS and time.time() - desde < BLOQUEO_SEG:
            return True
        if time.time() - desde >= BLOQUEO_SEG:
            d.pop(ip, None)
            _escribir_intentos(d)
        return False


def fallo_login(ip):
    with _lock:
        d = _leer_intentos()
        # Purga registros vencidos para que el archivo no crezca sin control.
        ahora = time.time()
        d = {k: v for k, v in d.items() if ahora - v[1] < BLOQUEO_SEG}
        conteo = d.get(ip, [0, ahora])[0]
        d[ip] = [conteo + 1, ahora]
        _escribir_intentos(d)


def limpiar_intentos(ip):
    with _lock:
        d = _leer_intentos()
        if d.pop(ip, None) is not None:
            _escribir_intentos(d)


def requiere_acceso(f):
    @wraps(f)
    def envoltura(*a, **kw):
        if not APP_PASSWORD or session.get('autorizado'):
            return f(*a, **kw)
        return redirect(url_for('login', siguiente=request.path))
    return envoltura


@app.route('/login', methods=['GET', 'POST'])
def login():
    if not APP_PASSWORD:
        return redirect(url_for('index'))
    if request.method == 'POST':
        ip = ip_cliente()
        if bloqueado(ip):
            flash('Demasiados intentos fallidos. Espera unos minutos.')
            return render_template('login.html'), 429
        usuario = request.form.get('usuario', '')
        clave = request.form.get('clave', '')
        usuario_ok = (not APP_USERNAME) or hmac.compare_digest(usuario, APP_USERNAME)
        clave_ok = hmac.compare_digest(clave, APP_PASSWORD)
        if usuario_ok and clave_ok:
            session.clear()
            session['autorizado'] = True
            session.permanent = True
            limpiar_intentos(ip)
            destino = request.args.get('siguiente', '')
            if not destino.startswith('/') or destino.startswith('//'):
                destino = url_for('index')
            return redirect(destino)
        fallo_login(ip)
        app.logger.warning('Intento de acceso fallido desde %s', ip)
        flash('Usuario o contraseña incorrectos.')
    return render_template('login.html')


@app.route('/salir')
def salir():
    session.clear()
    return redirect(url_for('login'))


@app.route('/salud')
def salud():
    return {'estado': 'ok', 'chrome': bool(generar_pdf.encontrar_chrome()),
            'hora': datetime.now(timezone.utc).isoformat()}


# ---------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------

def dir_corrida(token):
    """Ruta de la corrida, validando el token para evitar path traversal."""
    if not token or len(token) != 32 or not all(c in '0123456789abcdef' for c in token):
        abort(404)
    d = os.path.join(SALIDAS, token)
    if not os.path.isdir(d):
        abort(404)
    return d


@app.route('/')
@requiere_acceso
def index():
    return render_template('index.html', max_mb=MAX_MB, hoy=date.today().isoformat(),
                           retencion=RETENCION_MIN, entorno=ENTORNO,
                           protegido=bool(APP_PASSWORD))


@app.route('/procesar', methods=['POST'])
@requiere_acceso
def procesar():
    archivo = request.files.get('pdf')
    password = (request.form.get('password') or '').strip()
    sexo = request.form.get('sexo', 'M')
    fecha_calculo = (request.form.get('fecha_calculo') or '').strip()
    num_hijos = int(request.form.get('num_hijos', '0') or '0')
    pension_deseada_raw = (request.form.get('pension_deseada') or '').strip()
    pension_deseada = None
    if pension_deseada_raw:
        try:
            pension_deseada = float(pension_deseada_raw.replace('.', '').replace(',', '.'))
        except ValueError:
            pass

    if not archivo or not archivo.filename:
        flash('Selecciona el PDF de la historia laboral.')
        return redirect(url_for('index'))
    if not archivo.filename.lower().endswith('.pdf'):
        flash('El archivo debe ser un PDF.')
        return redirect(url_for('index'))
    if sexo not in ('M', 'F'):
        flash('Sexo inválido.')
        return redirect(url_for('index'))

    token = secrets.token_hex(16)
    destino = os.path.join(SALIDAS, token)
    os.makedirs(destino, exist_ok=True)
    pdf_entrada = os.path.join(destino, secure_filename(archivo.filename) or 'entrada.pdf')
    archivo.save(pdf_entrada)

    try:
        # 1 · Extracción del PDF de Colpensiones
        try:
            datos = extraer_historia.extraer(pdf_entrada, password)
        except Exception as e:
            msg = str(e).lower()
            if 'password' in msg or 'decrypt' in msg or 'encrypt' in msg:
                raise ValueError('No se pudo abrir el PDF: la contraseña parece incorrecta. '
                                 'En los reportes de Colpensiones suele ser el número de cédula.')
            raise ValueError(f'No se pudo leer el PDF: {e}')

        faltantes = [k for k in ('nombre', 'fecha_nacimiento', 'semanas_totales_oficial')
                     if not datos.get(k)]
        if faltantes or not datos.get('pagos_mensuales'):
            raise ValueError(
                'El PDF se abrió, pero no tiene el formato del "Reporte de semanas cotizadas en '
                'pensiones" de Colpensiones (no se encontró: '
                + ', '.join(faltantes + ([] if datos.get('pagos_mensuales') else ['detalle de pagos']))
                + '). Verifica que sea ese reporte y no otro documento.')

        json_datos = os.path.join(destino, 'historia_extraida.json')
        with open(json_datos, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)

        # 2 · Motor de cálculo
        fh = date.fromisoformat(fecha_calculo) if fecha_calculo else None
        resultado = motor_pension.analizar(json_datos, sexo=sexo, fecha_hoy=fh,
                                              num_hijos=num_hijos,
                                              pension_deseada=pension_deseada)
        json_resultado = os.path.join(destino, 'resultado.json')
        with open(json_resultado, 'w', encoding='utf-8') as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)

        # 3 · Informe en PDF
        generar_pdf.generar(json_resultado, os.path.join(destino, 'Informe_Pension.pdf'))

    except Exception as e:
        shutil.rmtree(destino, ignore_errors=True)
        # Nunca registrar el contenido del reporte: solo el tipo de fallo.
        app.logger.error('Fallo procesando una carga: %s', traceback.format_exc(limit=3))
        flash(str(e) if isinstance(e, ValueError) else
              'Error inesperado generando el informe. Revisa que el PDF sea el reporte correcto.')
        return redirect(url_for('index'))
    finally:
        # El PDF de origen tiene datos personales y ya no hace falta.
        if os.path.exists(pdf_entrada):
            os.unlink(pdf_entrada)

    return redirect(url_for('resultado', token=token))


@app.route('/resultado/<token>')
@requiere_acceso
def resultado(token):
    d = dir_corrida(token)
    with open(os.path.join(d, 'resultado.json'), encoding='utf-8') as f:
        r = json.load(f)
    return render_template('resultado.html', token=token, r=r, retencion=RETENCION_MIN,
                           money=generar_pdf.money, num=generar_pdf.num,
                           pct=generar_pdf.pct, fecha_corta=generar_pdf.fecha_corta)


@app.route('/informe/<token>.pdf')
@requiere_acceso
def informe(token):
    d = dir_corrida(token)
    return send_file(os.path.join(d, 'Informe_Pension.pdf'),
                     mimetype='application/pdf', download_name='Informe_Pension.pdf')


@app.route('/borrar/<token>', methods=['POST'])
@requiere_acceso
def borrar(token):
    shutil.rmtree(dir_corrida(token), ignore_errors=True)
    flash('Los archivos de esa corrida fueron borrados.')
    return redirect(url_for('index'))


@app.errorhandler(413)
def demasiado_grande(e):
    flash(f'El archivo supera el límite de {MAX_MB} MB.')
    return redirect(url_for('index')), 302


os.makedirs(SALIDAS, exist_ok=True)

if __name__ == '__main__':
    puerto = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0' if ENTORNO == 'web' else '127.0.0.1'
    app.run(host=host, port=puerto, debug=False)
