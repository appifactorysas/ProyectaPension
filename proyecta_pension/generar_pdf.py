# -*- coding: utf-8 -*-
"""Genera el informe de pensión en PDF a partir de resultado.json.

Construye un HTML pensado para impresión (A4, tipografía serif, paleta sobria)
y lo convierte a PDF con Chrome headless (--print-to-pdf), que ya viene
instalado en macOS y da mejor tipografía que las librerías de PDF en Python.

Uso:  python generar_pdf.py resultado.json informe.pdf
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

CHROME_CANDIDATOS = [
    # Linux / contenedor
    '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    # macOS
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
]


# ---------------------------------------------------------------------
# Formato es-CO: miles con ".", decimales con ","
# ---------------------------------------------------------------------

def num(v, dec=0):
    if v is None:
        return '—'
    s = f'{v:,.{dec}f}'
    return s.replace(',', '\x00').replace('.', ',').replace('\x00', '.')


def money(v, dec=0):
    return '—' if v is None else '$' + num(v, dec)


def pct(v, dec=2):
    return '—' if v is None else num(v, dec) + '%'


def fecha_larga(iso):
    y, m, d = (int(x) for x in iso.split('-'))
    return f'{d} de {MESES[m - 1]} de {y}'


def fecha_corta(iso):
    y, m, d = (int(x) for x in iso.split('-'))
    return f'{d:02d}/{m:02d}/{y}'


CSS = """
@page { size: A4; margin: 17mm 15mm 20mm 15mm; }

:root {
  --tinta:   #16202e;
  --tinta-2: #45566b;
  --tenue:   #8092a6;
  --linea:   #d9dee5;
  --papel:   #ffffff;
  --crema:   #f7f5f0;
  --oro:     #9a7434;
  --verde:   #1f6b4d;
  --rojo:    #9b3226;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  color: var(--tinta);
  background: var(--papel);
  font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  font-size: 10.2pt;
  line-height: 1.5;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}

.num { font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1; }

/* ---------- Portada ---------- */
.portada { height: 245mm; display: flex; flex-direction: column; justify-content: space-between; }
.portada-top { padding-top: 26mm; }
.marca {
  font-size: 7.6pt; letter-spacing: .26em; text-transform: uppercase;
  color: var(--oro); font-weight: 600;
}
.regla-oro { width: 46mm; height: 2.2pt; background: var(--oro); margin: 5mm 0 9mm; }
h1.titulo { font-size: 33pt; line-height: 1.08; margin: 0 0 5mm; font-weight: 600; letter-spacing: -.015em; }
.subtitulo { font-size: 12.5pt; color: var(--tinta-2); font-style: italic; margin: 0; }
.portada-datos { border-top: .6pt solid var(--linea); padding-top: 6mm; }
.portada-datos dl { display: grid; grid-template-columns: 42mm 1fr; gap: 2.6mm 0; margin: 0; }
.portada-datos dt { font-size: 7.6pt; letter-spacing: .13em; text-transform: uppercase; color: var(--tenue); padding-top: .7mm; }
.portada-datos dd { margin: 0; font-size: 10.4pt; }
.aviso-portada {
  background: var(--crema); border-left: 2.2pt solid var(--oro);
  padding: 4mm 5mm; font-size: 8.6pt; color: var(--tinta-2); line-height: 1.45;
}

/* ---------- Estructura de secciones ---------- */
.seccion { page-break-before: always; display: flex; flex-direction: column; min-height: 235mm; }
.seccion-cab { border-bottom: .6pt solid var(--linea); padding-bottom: 3mm; margin-bottom: 6mm; }
.seccion-num { font-size: 7.6pt; letter-spacing: .22em; text-transform: uppercase; color: var(--oro); font-weight: 600; }
h2 { font-size: 19pt; margin: 1.5mm 0 1mm; font-weight: 600; letter-spacing: -.01em; }
.seccion-sub { font-size: 9.6pt; color: var(--tinta-2); font-style: italic; margin: 0; }
h3 { font-size: 11pt; margin: 7mm 0 3mm; font-weight: 600; }

/* ---------- Cifra protagonista ---------- */
.hero { background: var(--crema); padding: 7mm 8mm; margin: 0 0 6mm; text-align: center; }
.hero-label { font-size: 7.8pt; letter-spacing: .2em; text-transform: uppercase; color: var(--tenue); }
.hero-cifra { font-size: 31pt; font-weight: 600; letter-spacing: -.02em; margin: 2mm 0 1mm; }
.hero-pie { font-size: 8.8pt; color: var(--tinta-2); font-style: italic; }

/* ---------- Tablas de datos ---------- */
table.datos { width: 100%; border-collapse: collapse; }
table.datos th, table.datos td { padding: 2.4mm 0; border-bottom: .4pt solid var(--linea); vertical-align: baseline; }
table.datos th { text-align: left; font-weight: 400; color: var(--tinta-2); font-size: 9.6pt; }
table.datos td { text-align: right; font-weight: 600; }
table.datos tr.total th, table.datos tr.total td { border-bottom: none; border-top: 1.2pt solid var(--tinta); padding-top: 3mm; font-size: 11pt; }
table.datos tr.total th { color: var(--tinta); font-weight: 600; }
.nota-celda { display: block; font-size: 8.2pt; color: var(--tenue); font-weight: 400; font-style: italic; }

/* ---------- Comparativo A vs B ---------- */
.comparativo { display: grid; grid-template-columns: 1fr 1fr; gap: 5mm; margin: 5mm 0; }
.opcion { border: .6pt solid var(--linea); padding: 5mm; }
.opcion.gana { border-color: var(--verde); border-width: 1.4pt; background: #f4faf7; }
.opcion-tag { font-size: 7.4pt; letter-spacing: .18em; text-transform: uppercase; color: var(--tenue); }
.opcion.gana .opcion-tag { color: var(--verde); font-weight: 600; }
.opcion-titulo { font-size: 10.6pt; font-weight: 600; margin: 1.5mm 0 1mm; }
.opcion-fecha { font-size: 8.6pt; color: var(--tinta-2); font-style: italic; margin-bottom: 3.5mm; }
.opcion-cifra { font-size: 19pt; font-weight: 600; letter-spacing: -.02em; }
.opcion-cifra small { font-size: 8.6pt; font-weight: 400; color: var(--tenue); }
.opcion ul { list-style: none; padding: 0; margin: 4mm 0 0; font-size: 9pt; }
.opcion li { display: flex; justify-content: space-between; padding: 1.4mm 0; border-bottom: .4pt dotted var(--linea); }
.opcion li span:last-child { font-weight: 600; }

/* ---------- Veredicto ---------- */
.veredicto { border: .6pt solid var(--linea); border-left: 2.6pt solid var(--verde); padding: 5mm 6mm; margin: 5mm 0; }
.veredicto-tit { font-size: 7.8pt; letter-spacing: .2em; text-transform: uppercase; color: var(--verde); font-weight: 600; margin-bottom: 2mm; }
.veredicto p { margin: 0 0 2mm; }
.veredicto p:last-child { margin-bottom: 0; }

/* ---------- Avisos ---------- */
.aviso { background: var(--crema); border-left: 2.2pt solid var(--oro); padding: 4mm 5mm; margin: 5mm 0; font-size: 9pt; line-height: 1.45; }
.aviso strong { color: var(--oro); }
.aviso.legal { border-left-color: var(--rojo); }
.aviso.legal strong { color: var(--rojo); }

ul.limpia { padding-left: 4.5mm; margin: 2mm 0; }
ul.limpia li { margin-bottom: 1.6mm; }

/* ---------- Tabla escenarios ---------- */
table.escenarios { width: 100%; border-collapse: collapse; font-size: 8.8pt; }
table.escenarios th { text-align: left; font-size: 7pt; letter-spacing: .1em; text-transform: uppercase; color: var(--tenue); padding: 2mm 1.5mm; border-bottom: .8pt solid var(--linea); }
table.escenarios td { padding: 2.2mm 1.5mm; border-bottom: .3pt solid var(--linea); }
table.escenarios tr.dest td { font-weight: 600; background: var(--crema); }

/* ---------- Info box ---------- */
.info-box { border: .6pt solid var(--linea); padding: 5mm; margin: 4mm 0; }
.info-box-tit { font-size: 7.6pt; letter-spacing: .18em; text-transform: uppercase; color: var(--oro); font-weight: 600; margin-bottom: 2mm; }

/* Sección 4: compacta para que la comparación quepa en una sola página */
.s4 { font-size: 9.5pt; }
.s4 .opcion-cifra { font-size: 17pt; }
.s4 table.datos th { font-size: 9.1pt; }
.s4 h3 { margin: 4.5mm 0 2mm; }
.s4 .comparativo { gap: 4mm; margin: 3.5mm 0; }
.s4 .opcion { padding: 4mm; }
.s4 .opcion ul { margin-top: 3mm; }
.s4 table.datos th, .s4 table.datos td { padding: 1.9mm 0; }
.s4 .veredicto { padding: 3.5mm 5mm; margin: 3.5mm 0; }
.s4 .aviso { margin: 3mm 0 0; padding: 3.5mm 4.5mm; font-size: 8.6pt; }

.pie-seccion {
  margin-top: auto; padding-top: 3mm;
  border-top: .4pt solid var(--linea);
  font-size: 7.4pt; color: var(--tenue);
}
"""


def construir_html(r):
    a = r['afiliado']
    hoy, fut = r['hoy'], r['futura']
    base = r['proyeccion_base_cotizacion']
    ret = r['retiro_edad']
    esc_a, esc_b = ret['escenario_a'], ret['escenario_b']

    edad_hoy = int((date.fromisoformat(a['fecha_calculo']) -
                    date(*[int(x) for x in reversed(a['fecha_nacimiento'].split('/'))])).days / 365.25)

    espera_vale = (ret['anios_equilibrio_real'] is not None and ret['anios_equilibrio_real'] < 10)
    clase_a = '' if espera_vale else ' gana'
    clase_b = ' gana' if espera_vale else ''

    if ret['anios_equilibrio_real'] is None:
        veredicto = ('Seguir cotizando después de cumplir la edad <strong>no mejora la mesada</strong> '
                     'en términos reales: no hay un punto de equilibrio que recuperar.')
    elif espera_vale:
        veredicto = (f"Esperar los {ret['meses_extra']} meses adicionales se recupera en "
                     f"<strong>{num(ret['anios_equilibrio_real'], 1)} años</strong> de mesada. "
                     f"Si la expectativa de vida supera esa cifra, conviene esperar.")
    else:
        veredicto = (f"Esperar los {ret['meses_extra']} meses adicionales solo se recupera después de "
                     f"<strong>{num(ret['anios_equilibrio_real'], 1)} años</strong> cobrando la mesada más alta. "
                     f"Es decir, habría que vivir hasta cerca de los "
                     f"{a['edad_pension'] + int(ret['anios_equilibrio_real'])} años solo para empatar. "
                     f"<strong>Financieramente conviene pensionarse el mismo día que cumple la edad.</strong>")

    pie = (f"ProyectaPension · {a['nombre'].title()} · Cálculo del "
           f"{fecha_corta(a['fecha_calculo'])} — proyección educativa, no es una liquidación oficial")

    # --- Bloques dinámicos (usan loops que no caben en el f-string) ---
    escenarios = r.get('escenarios', [])
    filas_esc = ''
    for e in escenarios:
        dest = ' class="dest"' if e['meses'] == fut['meses_restantes'] else ''
        filas_esc += (f'    <tr{dest}><td>{e["label"]}</td>'
                      f'<td class="num">{fecha_corta(e["fecha"])}</td>'
                      f'<td class="num">{num(e["semanas"], 0)}</td>'
                      f'<td class="num">{pct(e["tasa"])}</td>'
                      f'<td class="num">{money(e["pension_bruta"])}</td>'
                      f'<td class="num"><strong>{money(e["pension_neta"])}</strong></td></tr>\n')

    sol = r.get('solidaridad', {})
    bloque_sol = ''
    if sol.get('aplica'):
        filas_sol = ''
        for t in sol['tramos']:
            filas_sol += (f'    <tr><th>{t["desde_smlmv"]}–{t["hasta_smlmv"]} SMLMV '
                          f'({pct(t["tasa_pct"], 1)})</th><td>{money(t["valor"])}</td></tr>\n')
        bloque_sol = (f'<div class="info-box"><div class="info-box-tit">Cotización adicional al '
                      f'Fondo de Solidaridad</div>\n'
                      f'<table class="datos num">\n{filas_sol}'
                      f'<tr class="total"><th>Total mensual adicional</th>'
                      f'<td>{money(sol["valor_mensual"])}</td></tr>\n'
                      f'<tr><th>Total anual adicional</th>'
                      f'<td>{money(sol["valor_anual"])}</td></tr>\n'
                      f'</table></div>')

    pension_des = r.get('pension_deseada')
    bloque_deseada = ''
    if pension_des:
        if pension_des.get('ya_alcanzada'):
            bloque_deseada = (
                f'\n\n<!-- ══════════════ SECCIÓN: PENSIÓN DESEADA ══════════════ -->\n'
                f'<section class="seccion">\n'
                f'  <div class="seccion-cab"><div class="seccion-num">Pensión deseada</div>\n'
                f'  <h2>{money(pension_des["pension_deseada"])}/mes</h2>\n'
                f'  <p class="seccion-sub">Ya la alcanza con la cotización actual</p></div>\n'
                f'  <div class="hero"><div class="hero-label">Pensión proyectada al cumplir la edad</div>\n'
                f'  <div class="hero-cifra num">{money(pension_des["pension_proyectada"])}</div>\n'
                f'  <div class="hero-pie">supera la meta en {money(pension_des["pension_proyectada"] - pension_des["pension_deseada"])}</div></div>\n'
                f'  <div class="pie-seccion">{pie}</div>\n</section>')
        elif not pension_des.get('alcanzable'):
            bloque_deseada = (
                f'\n\n<!-- ══════════════ SECCIÓN: PENSIÓN DESEADA ══════════════ -->\n'
                f'<section class="seccion">\n'
                f'  <div class="seccion-cab"><div class="seccion-num">Pensión deseada</div>\n'
                f'  <h2>{money(pension_des["pension_deseada"])}/mes</h2>\n'
                f'  <p class="seccion-sub">No alcanzable con el tope legal de 25 SMLMV</p></div>\n'
                f'  <div class="hero"><div class="hero-label">Pensión máxima posible</div>\n'
                f'  <div class="hero-cifra num">{money(pension_des["pension_maxima"])}</div>\n'
                f'  <div class="hero-pie">cotizando sobre el tope de {money(pension_des["ibc_tope"])}</div></div>\n'
                f'  <div class="aviso legal"><strong>No alcanzable.</strong> Ni cotizando sobre el tope legal de '
                f'25 salarios mínimos se alcanza la meta. La pensión máxima posible es '
                f'{money(pension_des["pension_maxima"])}.</div>\n'
                f'  <div class="pie-seccion">{pie}</div>\n</section>')
        else:
            pd = pension_des
            bloque_deseada = (
                f'\n\n<!-- ══════════════ SECCIÓN: PENSIÓN DESEADA ══════════════ -->\n'
                f'<section class="seccion">\n'
                f'  <div class="seccion-cab"><div class="seccion-num">Pensión deseada</div>\n'
                f'  <h2>¿Cómo alcanzar {money(pd["pension_deseada"])}/mes?</h2>\n'
                f'  <p class="seccion-sub">Base de cotización necesaria durante los {fut["meses_restantes"]} meses restantes</p></div>\n'
                f'  <div class="hero"><div class="hero-label">IBC mensual necesario</div>\n'
                f'  <div class="hero-cifra num">{money(pd["ibc_necesario"])}</div>\n'
                f'  <div class="hero-pie">+{pct(pd["incremento_ibc_pct"], 1)} sobre el IBC actual</div></div>\n'
                f'  <table class="datos num">\n'
                f'    <tr><th>Meta — pensión deseada (bruta)</th><td>{money(pd["pension_deseada"])}</td></tr>\n'
                f'    <tr><th>Pensión deseada neta (−12% salud)</th><td>{money(pd["pension_deseada_neta"])}</td></tr>\n'
                f'    <tr><th>IBC actual</th><td>{money(pd["ibc_actual"])}</td></tr>\n'
                f'    <tr><th>IBC necesario</th><td>{money(pd["ibc_necesario"])}</td></tr>\n'
                f'    <tr><th>Aporte mensual actual (16%)</th><td>{money(pd["aporte_mensual_actual"])}</td></tr>\n'
                f'    <tr><th>Aporte mensual necesario (16%)</th><td>{money(pd["aporte_mensual_necesario"])}</td></tr>\n'
                f'    <tr class="total"><th>Aporte adicional mensual</th>'
                f'<td>{money(pd["aporte_adicional_mensual"])}</td></tr>\n'
                f'  </table>\n'
                f'  <div class="aviso"><strong>Importante.</strong> Para que el IBC suba, el ingreso real del afiliado '
                f'(nómina, honorarios, renta) debe respaldar esa base. Cotizar sobre una base sin '
                f'sustento de ingresos puede acarrear sanciones.</div>\n'
                f'  <div class="pie-seccion">{pie}</div>\n</section>')

    vida = r.get('valor_vida', {})
    sob = r.get('sobrevivientes', {})
    bloque_proteccion = ''
    if vida or sob:
        bloque_proteccion = (
            f'\n\n<!-- ══════════════ SECCIÓN: PROTECCIÓN Y RIQUEZA ══════════════ -->\n'
            f'<section class="seccion">\n'
            f'  <div class="seccion-cab"><div class="seccion-num">Protección y riqueza pensional</div>\n'
            f'  <h2>Lo que vale su pensión</h2>\n'
            f'  <p class="seccion-sub">Pensión de sobrevivientes y valor acumulado de por vida</p></div>\n')
        if sob:
            bloque_proteccion += (
                f'  <h3>Pensión de sobrevivientes</h3>\n'
                f'  <p style="font-size:9.6pt;color:var(--tinta-2)">Art.&nbsp;46–49 Ley&nbsp;100/1993 mod. Ley&nbsp;797/2003. '
                f'Beneficiarios: cónyuge o compañero(a) permanente, hijos menores de 25 años '
                f'(si estudian) o en situación de invalidez, padres dependientes.</p>\n'
                f'  <table class="datos num">\n'
                f'    <tr><th>Si fallece como pensionado<span class="nota-celda">100% de la mesada se transfiere</span></th>'
                f'<td>{money(sob["como_pensionado"])}</td></tr>\n'
                f'    <tr><th>Si fallece como afiliado activo<span class="nota-celda">'
                f'tasa del {pct(sob["tasa_activo"])} — requisito: {sob["requisito"]}</span></th>'
                f'<td>{money(sob["como_activo"])}</td></tr>\n'
                f'  </table>\n')
        if vida:
            bloque_proteccion += (
                f'  <h3>Valor acumulado de por vida</h3>\n'
                f'  <p style="font-size:9.6pt;color:var(--tinta-2)">Basado en expectativa de vida '
                f'del DANE: {num(vida["expectativa_anos"], 0)} años adicionales después de pensionarse '
                f'(hasta los ~{num(vida["edad_esperada"], 0)} años).</p>\n'
                f'  <table class="datos num">\n'
                f'    <tr><th>Total de mesadas estimadas en vida</th>'
                f'<td>{num(vida["total_mesadas"], 0)}</td></tr>\n'
                f'    <tr><th>Valor bruto acumulado</th>'
                f'<td>{money(vida["bruto_acumulado"])}</td></tr>\n'
                f'    <tr><th>Valor neto acumulado (−12% salud)</th>'
                f'<td>{money(vida["neto_acumulado"])}</td></tr>\n'
                f'    <tr><th>Total aportado durante la vida laboral</th>'
                f'<td>{money(vida["total_aportado"])}</td></tr>\n'
                f'    <tr class="total"><th>Multiplicador — por cada peso aportado, recibe</th>'
                f'<td>{num(vida["multiplicador"], 1)}×</td></tr>\n'
                f'  </table>\n'
                f'  <div class="aviso"><strong>Es una estimación.</strong> Los valores están en pesos nominales '
                f'del año de reconocimiento. La mesada se reajusta anualmente con IPC, pero el '
                f'poder adquisitivo real depende de la inflación futura. El multiplicador real '
                f'será mayor porque cada mesada futura se reajusta.</div>\n')
        bloque_proteccion += f'  <div class="pie-seccion">{pie}</div>\n</section>'

    # --- Bloque: ¿Y si prefiero el dinero? ---
    od = r.get('opcion_dinero', {})
    bloque_dinero = ''
    if od:
        ind = od['indemnizacion']
        bloque_dinero = (
            f'\n\n<!-- ══════════════ SECCIÓN: ¿Y SI PREFIERO EL DINERO? ══════════════ -->\n'
            f'<section class="seccion">\n'
            f'  <div class="seccion-cab"><div class="seccion-num">Opción de pago único</div>\n'
            f'  <h2>¿Y si prefiero el dinero?</h2>\n'
            f'  <p class="seccion-sub">Indemnización sustitutiva vs. pensión vitalicia</p></div>\n')
        if od['cumple_semanas']:
            pasos = ''
            for i, p in enumerate(od['proceso_pension'], 1):
                pasos += f'    <li>{p}</li>\n'
            bloque_dinero += (
                f'  <div class="aviso legal"><strong>No es posible.</strong> Con '
                f'<span class="num">{num(od["semanas_proyectadas"], 0)}</span> semanas proyectadas (mínimo: '
                f'<span class="num">{num(od["semanas_minimas"])}</span>), <strong>cumple los requisitos para pensión</strong>. '
                f'En Colpensiones (régimen de prima media) <strong>no existe la opción de recibir un pago '
                f'único</strong> en lugar de la mesada vitalicia. El derecho adquirido es a la pensión mensual. '
                f'La indemnización sustitutiva (Art.&nbsp;37 Ley&nbsp;100/1993) solo aplica a quien '
                f'llega a la edad <em>sin</em> completar las semanas mínimas.</div>\n'
                f'  <h3>Comparación educativa: pensión vs. indemnización hipotética</h3>\n'
                f'  <table class="datos num">\n'
                f'    <tr><th>Indemnización sustitutiva (hipotética)<span class="nota-celda">'
                f'IBL semanal {money(ind["ibl_semanal"])} × {num(ind["semanas"], 0)} sem × '
                f'{pct(ind["tasa_promedio_ponderada"], 1)}</span></th>'
                f'<td>{money(ind["valor"])}</td></tr>\n'
                f'    <tr><th>Pensión neta mensual (vitalicia)</th>'
                f'<td>{money(od["pension_neta_mensual"])}</td></tr>\n'
                f'    <tr><th>Pensión neta anual (13 mesadas)</th>'
                f'<td>{money(od["pension_neta_anual"])}</td></tr>\n'
                f'    <tr><th>Pensión neta acumulada de por vida</th>'
                f'<td>{money(od["valor_vida_neto"])}</td></tr>\n'
                f'    <tr class="total"><th>La pensión vale más que la indemnización</th>'
                f'<td>{num(od["ratio_pension_vs_indem"], 1)}×</td></tr>\n'
                f'  </table>\n'
                f'  <h3>Proceso para solicitar la pensión de vejez</h3>\n'
                f'  <ol class="limpia">\n{pasos}  </ol>\n')
        else:
            pasos = ''
            for i, p in enumerate(od['proceso_indemnizacion'], 1):
                pasos += f'    <li>{p}</li>\n'
            bloque_dinero += (
                f'  <div class="hero"><div class="hero-label">Indemnización sustitutiva estimada</div>\n'
                f'  <div class="hero-cifra num">{money(ind["valor"])}</div>\n'
                f'  <div class="hero-pie">IBL semanal {money(ind["ibl_semanal"])} × '
                f'{num(ind["semanas"], 0)} sem × {pct(ind["tasa_promedio_ponderada"], 1)}</div></div>\n'
                f'  <div class="aviso"><strong>No cumple semanas mínimas.</strong> Con '
                f'<span class="num">{num(od["semanas_proyectadas"], 0)}</span> semanas proyectadas frente a las '
                f'<span class="num">{num(od["semanas_minimas"])}</span> requeridas, no hay derecho a pensión mensual. '
                f'Lo que corresponde es la <strong>indemnización sustitutiva</strong> '
                f'(Art.&nbsp;37 Ley&nbsp;100/1993, Decreto&nbsp;1730/2001).</div>\n'
                f'  <h3>Proceso para solicitar la indemnización</h3>\n'
                f'  <ol class="limpia">\n{pasos}  </ol>\n')
        bloque_dinero += f'  <div class="pie-seccion">{pie}</div>\n</section>'

    return f"""<!DOCTYPE html>
<html lang="es-CO"><head><meta charset="utf-8">
<title>Informe de proyección pensional</title>
<style>{CSS}</style></head><body>


<!-- ══════════════ PORTADA ══════════════ -->
<section class="portada">
  <div class="portada-top">
    <div class="marca">Proyecta&nbsp;Pension</div>
    <div class="regla-oro"></div>
    <h1 class="titulo">Informe de<br>proyección pensional</h1>
    <p class="subtitulo">Régimen de prima media · Colpensiones</p>
  </div>

  <div class="portada-datos">
    <dl>
      <dt>Afiliado</dt><dd>{a['nombre'].title()}</dd>
      <dt>Fecha de nacimiento</dt><dd class="num">{a['fecha_nacimiento']} &nbsp;·&nbsp; {edad_hoy} años cumplidos</dd>
      <dt>Afiliación desde</dt><dd class="num">{a['fecha_afiliacion']}</dd>
      <dt>Historia laboral a</dt><dd>{a['actualizado_a']}</dd>
      <dt>Edad de pensión</dt><dd class="num">{a['edad_pension']} años &nbsp;·&nbsp; {fecha_larga(a['fecha_pension'])}</dd>
      <dt>Fecha del cálculo</dt><dd class="num">{fecha_corta(a['fecha_calculo'])}</dd>
    </dl>
  </div>

  <div class="aviso-portada">
    Este documento es una <strong>herramienta de proyección educativa</strong> construida a partir del reporte
    de semanas cotizadas de Colpensiones. Aplica la normatividad vigente (Ley&nbsp;100/1993,
    Ley&nbsp;797/2003 y Ley&nbsp;2381 de 2024 — reforma pensional) y supuestos de inflación y salario
    mínimo para años aún no fijados oficialmente.
    No constituye una liquidación oficial ni asesoría legal: toda decisión de pensionarse
    debe validarse directamente con Colpensiones.
  </div>
</section>

<!-- ══════════════ SECCIÓN 1 ══════════════ -->
<section class="seccion">
  <div class="seccion-cab">
    <div class="seccion-num">Sección 1</div>
    <h2>Situación actual</h2>
    <p class="seccion-sub">Lo que tendría si dejara de cotizar hoy mismo</p>
  </div>

  <div class="hero">
    <div class="hero-label">Pensión mensual proyectada</div>
    <div class="hero-cifra num">{money(hoy['pension_mensual'])}</div>
    <div class="hero-pie">neta (−12% salud): <strong>{money(hoy['pension_neta'])}</strong> · {num(hoy['semanas_cotizadas'], 2)} semanas · {pct(hoy['tasa_reemplazo'])}</div>
  </div>

  <table class="datos num">
    <tr><th>Semanas cotizadas (total certificado)</th><td>{num(hoy['semanas_cotizadas'], 2)}</td></tr>
    <tr><th>Semanas mínimas exigidas por ley</th><td>{num(ret['semanas_minimas_requeridas'])}</td></tr>
    <tr><th>Semanas de exceso sobre el mínimo<span class="nota-celda">{int(hoy['semanas_exceso'] // 50)} bloques completos de 50 semanas</span></th><td>{num(hoy['semanas_exceso'], 2)}</td></tr>
    <tr><th>Último salario reportado (IBC)</th><td>{money(hoy['ultimo_salario'])}</td></tr>
    <tr><th>Valor total aportado a la fecha<span class="nota-celda">incluye estimación del tramo anterior a 1995</span></th><td>{money(hoy['vr_total_aportes'])}</td></tr>
    <tr><th>IBL — promedio últimos 10 años indexado</th><td>{money(hoy['ibl_10y'])}</td></tr>
    <tr><th>IBL — promedio de toda la vida laboral</th><td>{money(hoy['ibl_vida'])}</td></tr>
    <tr><th>IBL aplicable <span class="nota-celda">la ley toma el mayor de los dos</span></th><td>{money(hoy['ibl'])}</td></tr>
    <tr><th>Tasa base según nivel de IBL</th><td>{pct(hoy['tasa_base'])}</td></tr>
    <tr><th>Incremento por semanas de exceso</th><td>+{pct(hoy['incremento_pct'], 1)}</td></tr>
    <tr class="total"><th>Tasa de reemplazo aplicada</th><td>{pct(hoy['tasa_reemplazo'])}</td></tr>
    <tr><th>Pensión mensual bruta</th><td>{money(hoy['pension_mensual'])}</td></tr>
    <tr><th>Descuento salud (12%)</th><td>−{money(hoy['descuento_salud'])}</td></tr>
    <tr class="total"><th>Pensión mensual neta</th><td>{money(hoy['pension_neta'])}</td></tr>
  </table>
  {bloque_sol}

  <div class="aviso">
    <strong>Cómo se lee.</strong> La tasa de reemplazo es el porcentaje del IBL que se convierte en mesada.
    Parte de una tasa base que baja a medida que sube el IBL (fórmula <span class="num">65,5 − 0,5 × s</span>,
    con <em>s</em> = IBL medido en salarios mínimos) y sube <span class="num">1,5%</span> por cada bloque completo
    de 50 semanas cotizadas por encima del mínimo, con un techo del <span class="num">80%</span>.
  </div>
  <div class="pie-seccion">{pie}</div>
</section>

<!-- ══════════════ SECCIÓN 2 ══════════════ -->
<section class="seccion">
  <div class="seccion-cab">
    <div class="seccion-num">Sección 2</div>
    <h2>Al cumplir la edad de pensión</h2>
    <p class="seccion-sub">Cotizando {fut['meses_restantes']} meses más sobre el salario actual, hasta el {fecha_corta(a['fecha_pension'])}</p>
  </div>

  <div class="hero">
    <div class="hero-label">Pensión mensual proyectada a los {a['edad_pension']} años</div>
    <div class="hero-cifra num">{money(fut['pension_mensual'])}</div>
    <div class="hero-pie">neta (−12% salud): <strong>{money(fut['pension_neta'])}</strong> · {money(fut['pension_mensual'] - hoy['pension_mensual'])} más que hoy</div>
  </div>

  <table class="datos num">
    <tr><th>Meses que faltan para cumplir la edad</th><td>{fut['meses_restantes']}</td></tr>
    <tr><th>Semanas cotizadas proyectadas</th><td>{num(fut['semanas_cotizadas'], 2)}</td></tr>
    <tr><th>Semanas de exceso<span class="nota-celda">{int(fut['semanas_exceso'] // 50)} bloques completos de 50 semanas</span></th><td>{num(fut['semanas_exceso'], 2)}</td></tr>
    <tr><th>Valor total aportado proyectado</th><td>{money(fut['vr_total_aportes'])}</td></tr>
    <tr><th>IBL proyectado <span class="nota-celda">indexado a pesos de {fut['smlmv'] and a['fecha_pension'][:4]}</span></th><td>{money(fut['ibl'])}</td></tr>
    <tr><th>Tasa base</th><td>{pct(fut['tasa_base'])}</td></tr>
    <tr><th>Incremento por semanas de exceso</th><td>+{pct(fut['incremento_pct'], 1)}</td></tr>
    <tr class="total"><th>Tasa de reemplazo aplicada</th><td>{pct(fut['tasa_reemplazo'])}</td></tr>
    <tr><th>Pensión mensual bruta</th><td>{money(fut['pension_mensual'])}</td></tr>
    <tr><th>Descuento salud (12%)</th><td>−{money(fut['descuento_salud'])}</td></tr>
    <tr class="total"><th>Pensión mensual neta</th><td>{money(fut['pension_neta'])}</td></tr>
    <tr><th>Pensión anual bruta (13 mesadas)</th><td>{money(fut['pension_anual'])}</td></tr>
    <tr><th>Pensión anual neta</th><td>{money(fut['pension_anual_neta'])}</td></tr>
  </table>

  <div class="aviso">
    <strong>Siguiente tramo.</strong> Para ganar el próximo incremento de
    <span class="num">1,5%</span> faltarían <span class="num">{num(fut['semanas_faltantes_prox_tramo'], 2)} semanas</span>
    (unos <span class="num">{num(fut['meses_faltantes_prox_tramo'], 1)} meses</span>), contadas
    <em>después</em> de cumplir los {a['edad_pension']} años. La Sección 4 evalúa si vale la pena esperarlas.
  </div>
  <div class="pie-seccion">{pie}</div>
</section>

<!-- ══════════════ SECCIÓN: MULTIESCENARIO ══════════════ -->
<section class="seccion">
  <div class="seccion-cab">
    <div class="seccion-num">Escenarios de retiro</div>
    <h2>¿Cuándo conviene pensionarse?</h2>
    <p class="seccion-sub">Comparación a diferentes plazos de cotización — pensión neta = bruta − 12% salud</p>
  </div>

  <table class="escenarios num">
    <thead>
    <tr><th>Escenario</th><th>Fecha</th><th>Semanas</th><th>Tasa</th><th>Pensión bruta</th><th>Pensión neta</th></tr>
    </thead>
    <tbody>
{filas_esc}    </tbody>
  </table>

  <div class="aviso">
    <strong>Pensión neta.</strong> Las pensiones de Colpensiones están exentas de retención en la fuente
    (el tope de 25 SMLMV queda por debajo de las 1.000 UVT mensuales, Art.&nbsp;206 num.&nbsp;5 E.T.).
    El único descuento obligatorio es el <span class="num">12%</span> de aporte a salud que se retiene de la mesada.
  </div>
  <div class="pie-seccion">{pie}</div>
</section>

<!-- ══════════════ SECCIÓN 3 ══════════════ -->
<section class="seccion">
  <div class="seccion-cab">
    <div class="seccion-num">Sección 3</div>
    <h2>¿Y si quisiera pensionarse con el sueldo completo?</h2>
    <p class="seccion-sub">Base de cotización necesaria para que la mesada iguale el salario actual</p>
  </div>

  <div class="hero">
    <div class="hero-label">IBC mensual necesario durante los {fut['meses_restantes']} meses restantes</div>
    <div class="hero-cifra num">{money(base['ibc_necesario'])}</div>
    <div class="hero-pie">un aumento del {pct(base['incremento_pct'], 1)} sobre la base actual</div>
  </div>

  <table class="datos num">
    <tr><th>Meta — salario actual</th><td>{money(base['sueldo_actual_objetivo'])}</td></tr>
    <tr><th>Base de cotización actual</th><td>{money(hoy['ultimo_salario'])}</td></tr>
    <tr><th>Base de cotización necesaria</th><td>{money(base['ibc_necesario'])}</td></tr>
    <tr><th>Aumento requerido</th><td>{money(base['incremento_absoluto'])}</td></tr>
    <tr class="total"><th>Tope legal — 25 salarios mínimos</th><td>{money(base['tope_ibc_25_smlmv'])}</td></tr>
  </table>

  <div class="aviso">
    <strong>Por qué el salto es tan grande.</strong> El IBL promedia los últimos
    <span class="num">120</span> meses cotizados. Quedan solo <span class="num">{fut['meses_restantes']}</span> de esos 120,
    así que cada peso adicional de cotización pesa apenas
    <span class="num">{num(fut['meses_restantes'] / 120 * 100, 1)}%</span> en el promedio final.
    Subir la base de cotización a estas alturas mueve poco la mesada y cuesta mucho:
    el aporte mensual pasaría de {money(hoy['ultimo_salario'] * 0.16)} a {money(base['ibc_necesario'] * 0.16) if base['ibc_necesario'] else '—'}.
  </div>
  <div class="pie-seccion">{pie}</div>
</section>

<!-- ══════════════ SECCIÓN 4 ══════════════ -->
<section class="seccion s4">
  <div class="seccion-cab">
    <div class="seccion-num">Sección 4</div>
    <h2>Retiro tan pronto cumpla la edad</h2>
    <p class="seccion-sub">Pensionarse el mismo día que cumple {a['edad_pension']} años, frente a seguir cotizando hasta el siguiente tramo</p>
  </div>

  <div class="comparativo">
    <div class="opcion{clase_a}">
      <div class="opcion-tag">Opción A</div>
      <div class="opcion-titulo">Se retira al cumplir la edad</div>
      <div class="opcion-fecha">Empieza a cobrar el {fecha_corta(esc_a['fecha_corte'])}</div>
      <div class="opcion-cifra num">{money(esc_a['pension_mensual'])} <small>/ mes</small></div>
      <ul class="num">
        <li><span>Semanas</span><span>{num(esc_a['semanas_cotizadas'], 2)}</span></li>
        <li><span>Tasa de reemplazo</span><span>{pct(esc_a['tasa_reemplazo'])}</span></li>
        <li><span>IBL</span><span>{money(esc_a['ibl'])}</span></li>
        <li><span>Total aportado</span><span>{money(esc_a['vr_total_aportes'])}</span></li>
      </ul>
    </div>

    <div class="opcion{clase_b}">
      <div class="opcion-tag">Opción B</div>
      <div class="opcion-titulo">Cotiza {ret['meses_extra']} meses más</div>
      <div class="opcion-fecha">Empieza a cobrar el {fecha_corta(esc_b['fecha_corte'])}</div>
      <div class="opcion-cifra num">{money(esc_b['pension_mensual'])} <small>/ mes</small></div>
      <ul class="num">
        <li><span>Semanas</span><span>{num(esc_b['semanas_cotizadas'], 2)}</span></li>
        <li><span>Tasa de reemplazo</span><span>{pct(esc_b['tasa_reemplazo'])}</span></li>
        <li><span>IBL</span><span>{money(esc_b['ibl'])}</span></li>
        <li><span>Total aportado</span><span>{money(esc_b['vr_total_aportes'])}</span></li>
      </ul>
    </div>
  </div>

  <h3>La comparación honesta</h3>
  <table class="datos num">
    <tr><th>Diferencia nominal entre las dos mesadas<span class="nota-celda">pesos de {esc_b['fecha_corte'][:4]} contra pesos de {esc_a['fecha_corte'][:4]}: exagera la ganancia</span></th><td>{money(ret['ganancia_mensual'])}</td></tr>
    <tr><th>Mesada de la opción A reajustada por IPC a {esc_b['fecha_corte'][:4]}<span class="nota-celda">la mesada de A también sube cada enero</span></th><td>{money(ret['pension_a_indexada'])}</td></tr>
    <tr><th>Ganancia real de esperar<span class="nota-celda">el {pct(esc_b['incremento_pct'] - esc_a['incremento_pct'], 1)} del tramo adicional, ya descontada la inflación</span></th><td>{money(ret['ganancia_mensual_real'])}</td></tr>
    <tr><th>Mesadas que deja de cobrar mientras espera</th><td>{ret['mesadas_sacrificadas']}</td></tr>
    <tr><th>Costo de esperar</th><td>{money(ret['costo_esperar'])}</td></tr>
    <tr class="total"><th>Tiempo para recuperar ese costo</th><td>{num(ret['anios_equilibrio_real'], 1) if ret['anios_equilibrio_real'] else '—'} años</td></tr>
  </table>

  <div class="veredicto">
    <div class="veredicto-tit">Conclusión</div>
    <p>{veredicto}</p>
  </div>

  <div class="aviso legal">
    <strong>No hay devolución de aportes.</strong> En el régimen de prima media la única figura de pago
    único es la <strong>indemnización sustitutiva</strong> (Art.&nbsp;37, Ley&nbsp;100/1993), reservada a quien
    llega a la edad <em>sin</em> completar las semanas mínimas. Con
    <span class="num">{num(esc_a['semanas_cotizadas'], 2)}</span> semanas frente a las
    <span class="num">{num(ret['semanas_minimas_requeridas'])}</span> exigidas <strong>no aplica</strong>:
    lo que corresponde es la mesada vitalicia.
  </div>
  <div class="pie-seccion">{pie}</div>
</section>
{bloque_deseada}
{bloque_proteccion}
{bloque_dinero}

<!-- ══════════════ SUPUESTOS ══════════════ -->
<section class="seccion">
  <div class="seccion-cab">
    <div class="seccion-num">Anexo</div>
    <h2>Supuestos y advertencias</h2>
    <p class="seccion-sub">Qué está fijado por ley y qué es una estimación de este modelo</p>
  </div>

  <h3>Marco legal aplicado</h3>
  <ul class="limpia">
    <li>Componente de Prima Media del Pilar Contributivo — Ley&nbsp;100/1993, Ley&nbsp;797/2003, Ley&nbsp;2381 de 2024 (reforma pensional).</li>
    <li>Edad de pensión: <span class="num">{a['edad_pension']}</span> años. Semanas mínimas: <span class="num">{num(ret['semanas_minimas_requeridas'])}</span>.</li>
    <li>Tasa de reemplazo <span class="num">r = 65,5 − 0,5 × s</span> (piso <span class="num">55%</span>),
        más <span class="num">1,5%</span> por bloque completo de 50 semanas de exceso, techo <span class="num">80%</span> (Art.&nbsp;32).</li>
    <li>IBL: el mayor entre los últimos 10 años y toda la vida laboral, ambos indexados por IPC (Art.&nbsp;32).</li>
    <li>Mesadas anuales: <span class="num">13</span> (12 + prima de diciembre, Art.&nbsp;32 y Art.&nbsp;88).</li>
    <li>Pensión neta: mesada bruta − 12% aporte a salud. Sin retención en fuente (exenta hasta 1.000 UVT, Art.&nbsp;206 E.T.).</li>
    <li>Pensión de sobrevivientes: Art.&nbsp;46–49 Ley&nbsp;100 mod. Ley&nbsp;797/2003.</li>
    <li>Indemnización sustitutiva (Art.&nbsp;37 Ley&nbsp;100/1993, Decreto&nbsp;1730/2001): IBL semanal × semanas × tasa promedio de cotización.</li>
    <li>Tope de IBC: 25 salarios mínimos.</li>
  </ul>

  <h3>Estimaciones del modelo — revisar antes de decidir</h3>
  <ul class="limpia">
    <li><strong>Salario mínimo {a['fecha_pension'][:4]}</strong>: estimado en {money(fut['smlmv'])} (~5% de incremento).
        El Gobierno lo fija en diciembre del año anterior.</li>
    <li><strong>IPC 2026 en adelante</strong>: estimado en <span class="num">5,0%</span> anual.
        Último dato oficial conocido: 2025 cerró en <span class="num">5,10%</span>.</li>
    <li><strong>Salario futuro</strong>: se asume que sigue cotizando sobre el mismo IBC actual,
        sin aumentos. Cualquier aumento salarial mejora las proyecciones.</li>
    <li><strong>Aportes anteriores a 1995</strong>: estimados con una tarifa histórica aproximada del
        <span class="num">6,5%</span>, porque el reporte de Colpensiones no valoriza ese tramo.</li>
    <li><strong>Régimen de transición de la Ley&nbsp;2381 de 2024</strong>: se asume que permanece
        íntegramente en Colpensiones, por superar las 900 semanas a julio de 2024.
        <strong>No verificado con Colpensiones.</strong></li>
    <li><strong>Comparación de mesadas</strong>: en pesos nominales de cada año de reconocimiento;
        el cálculo de equilibrio de la Sección 4 sí descuenta la inflación.</li>
  </ul>

  <div class="aviso legal">
    <strong>Advertencia final.</strong> Este informe es una proyección construida con supuestos explícitos,
    no una liquidación oficial de Colpensiones ni asesoría legal, tributaria o financiera.
    Antes de tomar cualquier decisión de retiro, solicite la liquidación oficial a Colpensiones
    y consulte a un asesor pensional.
  </div>
  <div class="pie-seccion">{pie}</div>
</section>

</body></html>"""


def encontrar_chrome():
    ruta = os.environ.get('CHROME_PATH')
    if ruta and os.path.exists(ruta):
        return ruta
    for c in CHROME_CANDIDATOS:
        if os.path.exists(c):
            return c
    for n in ('google-chrome', 'chromium', 'chromium-browser'):
        p = shutil.which(n)
        if p:
            return p
    return None


def html_a_pdf(html, pdf_path, timeout=90):
    """Convierte el HTML a PDF con Chrome headless.

    Chrome escribe el PDF correctamente pero en algunas versiones no cierra el
    proceso, así que en vez de esperar a que termine se espera a que el archivo
    aparezca y deje de crecer, y luego se cierra el proceso.
    """
    chrome = encontrar_chrome()
    if not chrome:
        raise RuntimeError(
            'No se encontró Chrome/Chromium para generar el PDF. '
            'Instale Google Chrome o abra el HTML e imprima a PDF manualmente.')

    if os.path.exists(pdf_path):
        os.unlink(pdf_path)

    tmp_html = tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8')
    tmp_html.write(html)
    tmp_html.close()
    perfil = tempfile.mkdtemp(prefix='pp-chrome-')
    proc = None
    try:
        cmd = [chrome, '--headless', '--disable-gpu', '--no-first-run',
               '--disable-extensions', '--disable-background-networking',
               f'--user-data-dir={perfil}', '--no-pdf-header-footer',
               '--virtual-time-budget=5000']
        # En contenedores se corre como root y sin /dev/shm grande: sin estos
        # dos flags Chromium no arranca.
        if sys.platform.startswith('linux'):
            cmd += ['--no-sandbox', '--disable-dev-shm-usage']
        cmd += [f'--print-to-pdf={pdf_path}', 'file://' + tmp_html.name]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        limite = time.time() + timeout
        tam_previo, estable = -1, 0
        while time.time() < limite:
            if os.path.exists(pdf_path):
                tam = os.path.getsize(pdf_path)
                if tam > 0 and tam == tam_previo:
                    estable += 1
                    if estable >= 3:      # ~0.9 s sin cambios: PDF terminado
                        break
                else:
                    estable = 0
                tam_previo = tam
            if proc.poll() is not None and os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                break
            time.sleep(0.3)
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        os.unlink(tmp_html.name)
        shutil.rmtree(perfil, ignore_errors=True)

    if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
        raise RuntimeError('Chrome no produjo el PDF dentro del tiempo previsto.')
    return pdf_path


def generar(resultado_path, pdf_path, guardar_html=None):
    with open(resultado_path, encoding='utf-8') as f:
        r = json.load(f)
    html = construir_html(r)
    if guardar_html:
        with open(guardar_html, 'w', encoding='utf-8') as f:
            f.write(html)
    return html_a_pdf(html, pdf_path)


if __name__ == '__main__':
    res = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else 'informe_pension.pdf'
    html_debug = sys.argv[3] if len(sys.argv) > 3 else None
    generar(res, os.path.abspath(out), html_debug)
    print('PDF generado:', os.path.abspath(out))
