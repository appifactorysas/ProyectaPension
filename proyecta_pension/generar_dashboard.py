#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera el dashboard HTML de ProyectaPension a partir del JSON de motor_pension.py"""
import json
import sys


def cop(v):
    if v is None:
        return "N/A"
    return "$ " + _es("{:,.0f}".format(v))


def _es(s):
    """Convierte formato numérico en-US ('1,620.00') a es-CO ('1.620,00')."""
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v):
    if v is None:
        return "N/A"
    return _es("{:.2f}".format(v)) + "%"


def semanas(v):
    return _es("{:,.2f}".format(v))


TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>ProyectaPension – {nombre}</title>
<style>
  :root {{
    --bg: #0f1420; --card: #161d2e; --card2: #1b2438; --accent: #4fd1c5;
    --accent2: #f6ad55; --text: #e8ecf4; --muted: #93a0bb; --good:#68d391; --warn:#f6ad55;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 28px; background: var(--bg); color: var(--text);
    font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
  }}
  h1 {{ font-size: 22px; margin: 0 0 2px 0; }}
  .sub {{ color: var(--muted); font-size: 13px; margin-bottom: 22px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 14px; margin-bottom: 26px; }}
  .card {{ background: var(--card); border: 1px solid #232d45; border-radius: 12px; padding: 16px 18px; }}
  .card .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; margin-bottom: 6px;}}
  .card .value {{ font-size: 21px; font-weight: 600; }}
  .card .value.small {{ font-size: 16px; }}
  .card .hint {{ color: var(--muted); font-size: 11.5px; margin-top: 4px; }}
  .section-title {{ font-size: 15px; font-weight: 700; margin: 30px 0 12px 0; color: var(--accent); display:flex; align-items:center; gap:8px;}}
  .section-title .n {{ background: var(--accent); color: #0f1420; width:20px; height:20px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; font-size:12px;}}
  .highlight {{ border-color: var(--accent); }}
  .highlight .value {{ color: var(--accent); }}
  .warnbox {{ background: var(--card2); border-left: 3px solid var(--accent2); border-radius: 8px; padding: 14px 18px; font-size: 13px; color: var(--muted); margin-top: 8px; line-height: 1.5; }}
  .warnbox b {{ color: var(--text); }}
  .footer {{ margin-top: 28px; font-size: 11.5px; color: var(--muted); line-height:1.6; border-top: 1px solid #232d45; padding-top: 14px;}}
  .badge {{ display:inline-block; background:#233047; color: var(--accent); font-size:11px; padding: 2px 8px; border-radius: 20px; margin-left: 8px;}}
</style>
</head>
<body>

<h1>ProyectaPension — {nombre}</h1>
<div class="sub">Historia laboral actualizada a {actualizado_a} · Fecha de cálculo {fecha_calculo} · Edad de pensión: {edad_pension} años ({sexo_txt}) · Fecha estimada de pensión: {fecha_pension}</div>

<div class="section-title"><span class="n">1</span> Datos actuales (si deja de cotizar hoy)</div>
<div class="grid">
  <div class="card highlight">
    <div class="label">Semanas cotizadas</div>
    <div class="value">{sem_hoy}</div>
  </div>
  <div class="card">
    <div class="label">Semanas de exceso (sobre 1.300)</div>
    <div class="value">{exc_hoy}</div>
    <div class="hint">Tramos completos de 50 semanas: +{inc_hoy}% en tasa</div>
  </div>
  <div class="card">
    <div class="label">Valor total aportes</div>
    <div class="value">{aportes_hoy}</div>
    <div class="hint">Incluye estimado tarifa histórica pre-1995</div>
  </div>
  <div class="card">
    <div class="label">Último salario reportado</div>
    <div class="value">{ult_salario}</div>
  </div>
  <div class="card highlight">
    <div class="label">Pensión proyectada HOY</div>
    <div class="value">{pension_hoy}</div>
    <div class="hint">Tasa de reemplazo: {tasa_hoy} · IBL: {ibl_hoy}</div>
  </div>
</div>

<div class="section-title"><span class="n">2</span> Datos futuros (al cumplir {edad_pension} años · {fecha_pension})</div>
<div class="grid">
  <div class="card highlight">
    <div class="label">Semanas cotizadas proyectadas</div>
    <div class="value">{sem_fut}</div>
    <div class="hint">Cotizando {meses_rest} meses más sobre el último sueldo</div>
  </div>
  <div class="card">
    <div class="label">Semanas de exceso</div>
    <div class="value">{exc_fut}</div>
    <div class="hint">Tramos completos de 50 semanas: +{inc_fut}% en tasa</div>
  </div>
  <div class="card">
    <div class="label">Valor total aportes proyectado</div>
    <div class="value">{aportes_fut}</div>
  </div>
  <div class="card highlight">
    <div class="label">Pensión proyectada FUTURA</div>
    <div class="value">{pension_fut}</div>
    <div class="hint">Tasa de reemplazo: {tasa_fut} · IBL: {ibl_fut}</div>
  </div>
  <div class="card">
    <div class="label">Semanas faltantes próximo tramo (+1.5%)</div>
    <div class="value small">{sem_falt} semanas <span class="badge">~{mes_falt} meses</span></div>
    <div class="hint">Meses adicionales a cotizar después de cumplir {edad_pension} años, para completar el siguiente bloque de 50 semanas de exceso</div>
  </div>
</div>

<div class="section-title"><span class="n">3</span> Base de cotización necesaria para igualar el sueldo actual</div>
<div class="grid">
  <div class="card">
    <div class="label">Sueldo actual (meta de pensión)</div>
    <div class="value">{sueldo_meta}</div>
  </div>
  <div class="card highlight">
    <div class="label">IBC mensual necesario</div>
    <div class="value">{ibc_necesario}</div>
    <div class="hint">Desde ahora y hasta la fecha de pensión ({meses_rest} meses)</div>
  </div>
  <div class="card">
    <div class="label">Incremento requerido</div>
    <div class="value small">{incr_abs}</div>
    <div class="hint">{incr_pct} sobre el IBC actual</div>
  </div>
  <div class="card">
    <div class="label">Tope legal IBC (25 SMLMV)</div>
    <div class="value small">{tope_ibc}</div>
  </div>
</div>
{warning_ibc}

<div class="section-title"><span class="n">4</span> Valor devuelto — si se retira y deja de cotizar el {fecha_retiro}</div>
<div class="warnbox"><b>Importante:</b> con {sem_congeladas} semanas cotizadas (más que las {sem_minimas} mínimas), Colpensiones <b>no te devuelve dinero</b> ni con indemnización sustitutiva ni con devolución de saldos — eso solo aplica a quien llega a la edad de pensión SIN completar las semanas mínimas. Lo que realmente pasaría es que tus semanas y tu IBL quedan congelados en esa fecha, y de todas formas recibes la mesada pensional mensual al cumplir {edad_pension} años.</div>
<div class="grid" style="margin-top:14px;">
  <div class="card highlight">
    <div class="label">Pensión mensual si te retiras ahí (desde los {edad_pension} años)</div>
    <div class="value">{pension_congelada}</div>
    <div class="hint">Semanas congeladas: {sem_congeladas} · Tasa: {tasa_congelada} · IBL: {ibl_congelado}</div>
  </div>
  <div class="card">
    <div class="label">Valor total aportes a esa fecha</div>
    <div class="value">{aportes_congelado}</div>
  </div>
  <div class="card">
    <div class="label">Indemnización sustitutiva (hipotética, NO aplica)</div>
    <div class="value small">{indemnizacion}</div>
    <div class="hint">Solo referencia educativa: lo que pagaría la fórmula legal SI no tuvieras las semanas mínimas. Tasa histórica ponderada implícita: {tasa_ponderada}</div>
  </div>
</div>

<div class="footer">
<b>Supuestos legales y metodológicos (Colombia, Colpensiones / Régimen de Prima Media):</b><br>
· Tasa de reemplazo: r = 65.50 − 0.50×s (s = IBL en SMLMV), piso 55%, +1.5% por cada 50 semanas de exceso sobre el mínimo, techo 80% (Art. 34 Ley 100/1993 mod. Ley 797/2003).<br>
· IBL = mayor entre el promedio de los últimos 10 años cotizados y el promedio de toda la vida laboral, ambos indexados por IPC anual dic-dic (Art. 21 Ley 100/1993).<br>
· Semanas mínimas: 1.300 (hombres) / 1.250 (mujeres, 2026). Edad de pensión: 62 (hombres) / 57 (mujeres).<br>
· Se asume régimen de transición de la Ley 2381 de 2024 (reforma pensional): el afiliado permanece 100% en Colpensiones sin trasladar el excedente de 2.3 SMLMV al Componente Complementario de Ahorro Individual.<br>
· SMLMV 2027 e IPC 2026-2027 son <b>estimaciones</b> (no certificadas aún); Vr. aportes anteriores a 1995 es un <b>estimado</b> con tarifa histórica del 6.5% (el reporte de Colpensiones no incluye ese valor).<br>
· Esta es una herramienta de proyección educativa, no una liquidación oficial. Colpensiones puede diferir por ajustes, mora, correcciones o cambios normativos.
</div>

</body>
</html>
"""


def generar(json_path, out_html):
    with open(json_path) as f:
        r = json.load(f)

    a, h, f_, p, v = r['afiliado'], r['hoy'], r['futura'], r['proyeccion_base_cotizacion'], r['valor_devuelto']

    if p['ibc_necesario'] is None:
        warning = ('<div class="warnbox"><b>Nota:</b> con el tiempo restante hasta la edad de pensión '
                   'no es posible, ni cotizando sobre el tope legal de 25 SMLMV, hacer que la pensión '
                   'proyectada iguale el sueldo actual. El IBL depende del promedio de los últimos 10 años, '
                   'así que entre menos tiempo falte para pensionarse, menor es el margen de una base de '
                   'cotización más alta hoy.</div>')
        ibc_nec_txt = "No alcanzable"
        incr_abs_txt = "N/A"
        incr_pct_txt = "N/A"
    else:
        warning = ""
        ibc_nec_txt = cop(p['ibc_necesario'])
        incr_abs_txt = cop(p['incremento_absoluto'])
        incr_pct_txt = "+" + pct(p['incremento_pct'])

    html = TEMPLATE.format(
        nombre=a['nombre'], actualizado_a=a['actualizado_a'], fecha_calculo=a['fecha_calculo'],
        edad_pension=a['edad_pension'], sexo_txt=('Hombre' if a['sexo'] == 'M' else 'Mujer'),
        fecha_pension=a['fecha_pension'],
        sem_hoy=semanas(h['semanas_cotizadas']), exc_hoy=semanas(h['semanas_exceso']),
        inc_hoy=pct(h['incremento_pct']).replace('%',''),
        aportes_hoy=cop(h['vr_total_aportes']), ult_salario=cop(h['ultimo_salario']),
        pension_hoy=cop(h['pension_mensual']), tasa_hoy=pct(h['tasa_reemplazo']), ibl_hoy=cop(h['ibl']),
        sem_fut=semanas(f_['semanas_cotizadas']), meses_rest=f_['meses_restantes'],
        exc_fut=semanas(f_['semanas_exceso']), inc_fut=pct(f_['incremento_pct']).replace('%',''),
        aportes_fut=cop(f_['vr_total_aportes']),
        pension_fut=cop(f_['pension_mensual']), tasa_fut=pct(f_['tasa_reemplazo']), ibl_fut=cop(f_['ibl']),
        sem_falt=semanas(f_['semanas_faltantes_prox_tramo']),
        mes_falt=_es("{:.1f}".format(f_['meses_faltantes_prox_tramo'])),
        sueldo_meta=cop(p['sueldo_actual_objetivo']), ibc_necesario=ibc_nec_txt,
        incr_abs=incr_abs_txt, incr_pct=incr_pct_txt, tope_ibc=cop(p['tope_ibc_25_smlmv']),
        warning_ibc=warning,
        fecha_retiro=v['fecha_retiro'], sem_congeladas=semanas(v['semanas_congeladas']),
        sem_minimas=int(v['semanas_minimas_requeridas']),
        pension_congelada=cop(v['pension_mensual_si_congela']),
        tasa_congelada=pct(v['tasa_reemplazo_congelada']), ibl_congelado=cop(v['ibl_congelado']),
        aportes_congelado=cop(v['vr_total_aportes_congelado']),
        indemnizacion=cop(v['indemnizacion_sustitutiva_hipotetica']),
        tasa_ponderada=pct(v['tasa_ponderada_historica_pct']),
    )

    with open(out_html, 'w') as f:
        f.write(html)
    print("Dashboard generado en", out_html)


if __name__ == '__main__':
    generar(sys.argv[1], sys.argv[2])
