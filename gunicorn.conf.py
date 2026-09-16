"""Configuración de gunicorn para ProyectaPension."""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"

# Generar el PDF lanza Chromium: es trabajo pesado y bloqueante, así que se usan
# hilos en vez de muchos procesos (Chromium ya consume bastante memoria).
workers = int(os.environ.get('WEB_CONCURRENCY', '2'))
threads = int(os.environ.get('WEB_THREADS', '4'))
worker_class = 'gthread'

# Una corrida completa (extracción + cálculo + Chromium) puede tardar ~30 s.
timeout = int(os.environ.get('WEB_TIMEOUT', '180'))
graceful_timeout = 30
keepalive = 5

max_requests = 200          # recicla workers para no acumular memoria
max_requests_jitter = 40

accesslog = '-'
errorlog = '-'
loglevel = os.environ.get('LOG_LEVEL', 'info')
# No registrar cadenas de consulta: pueden llevar tokens de corrida.
access_log_format = '%(h)s "%(m)s %(U)s" %(s)s %(b)s %(M)sms'
forwarded_allow_ips = '*'   # detrás del balanceador del proveedor
