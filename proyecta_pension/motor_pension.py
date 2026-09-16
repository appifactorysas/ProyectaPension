#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Motor de cálculo pensional Colpensiones — Componente de Prima Media del
Pilar Contributivo (Ley 2381 de 2024 «Reforma Pensional», que recoge y
modifica Ley 100/1993 art. 33-34 y Ley 797/2003).

SUPUESTOS Y FUENTES LEGALES (sep-2026):
- Edad pensión: 62 años hombres / 57 años mujeres (Art. 32).
- Semanas mínimas: 1.300 hombres (fijo). Mujeres: reducción progresiva
  de 25 sem/año desde 1.275 (2025) hasta 1.000 (2036+) (Art. 32, tabla;
  Sentencia C-197/2023).
- Tasa de reemplazo: r = 65.50 - 0.50*s ; s = IBL / SMLMV.
  Piso 55%, techo base 65.5%. +1.5% por cada 50 sem adicionales al
  mínimo. Techo total 80%. (Art. 32 Ley 2381/2024).
- IBL = mayor entre promedio últimos 10 años indexado por IPC y promedio
  de toda la vida laboral indexado (Art. 32).
- Mesadas anuales: 13 (12 + prima dic) (Art. 32 y Art. 88).
- Tope IBC: 25 SMLMV. Tope mesada: 25 SMLMV.
- Régimen de transición (Art. 75): quien al 1-jul-2025 tenía >=750 sem
  (mujeres) o >=900 sem (hombres) continúa 100% en prima media, sin
  split del excedente de 2.3 SMLMV al Componente Complementario.
  El motor verifica esta condición y la reporta.
- Prestación anticipada (Art. 37): para afiliados fuera del régimen de
  transición que cumplan la edad pero no las semanas mínimas y tengan
  >=1.000 sem: pensión proporcional a las semanas cotizadas.
- Cotización adicional al Fondo de Solidaridad Pensional: Art. 20
  (escalonada por tramos de IBC > 4 SMLMV). No afecta el cálculo de
  la mesada, pero informativa para el afiliado.

ESTE MODELO ES UNA HERRAMIENTA DE PROYECCIÓN / EDUCATIVA, NO UNA LIQUIDACIÓN
OFICIAL. Los valores de IPC y SMLMV para años aún no certificados son
estimaciones y deben revisarse/actualizarse cuando haya cifras oficiales.
"""

import json
import logging
import math
import sys
from datetime import date

# ---------------------------------------------------------------------
# 1. PARÁMETROS LEGALES / MACROECONÓMICOS (ACTUALIZABLES)
# ---------------------------------------------------------------------

SMLMV = {
    2024: 1_300_000,
    2025: 1_423_500,
    2026: 1_750_905,
    2027: 1_838_450,  # ESTIMADO (~5% variación típica). Ajustar cuando el Gobierno lo fije en dic-2026.
}

# Variación IPC dic-dic (%), fuente: DANE / cifras históricas públicas.
# Años 2026 en adelante son ESTIMACIONES (se usa el último dato oficial conocido ~5.1%).
IPC_ANUAL = {
    1985: 22.45, 1986: 20.95, 1987: 24.02, 1988: 28.12, 1989: 26.12,
    1990: 32.36, 1991: 26.82, 1992: 25.13, 1993: 22.60, 1994: 22.59,
    1995: 19.46, 1996: 21.63, 1997: 17.68, 1998: 16.70, 1999: 9.23,
    2000: 8.75, 2001: 7.65, 2002: 6.99, 2003: 6.49, 2004: 5.50,
    2005: 4.85, 2006: 4.48, 2007: 5.69, 2008: 7.67, 2009: 2.00,
    2010: 3.17, 2011: 3.73, 2012: 2.44, 2013: 1.94, 2014: 3.66,
    2015: 6.77, 2016: 5.75, 2017: 4.09, 2018: 3.18, 2019: 3.80,
    2020: 1.61, 2021: 5.62, 2022: 13.12, 2023: 9.28, 2024: 5.20,
    2025: 5.10, 2026: 5.00, 2027: 5.00,  # 2026/2027 estimados
}

TASA_APORTE_ACTUAL = 0.16          # tasa total pensión (Ley 100 art. 20 + Ley 797)
TASA_APORTE_HISTORICA_PRE1995 = 0.065  # aproximación tarifa ISS previa a Ley 100

EDAD_PENSION = {'M': 62, 'F': 57}
MESADAS_ANUALES = 13  # Art. 32 Ley 2381/2024: 12 mesadas + prima de diciembre

# Semanas mínimas para pensión de vejez (Art. 32 Ley 2381/2024).
# Hombres: 1.300 fijo.  Mujeres: reducción progresiva de 25/año desde 2025
# (Sentencia C-197/2023, recogida en la reforma).
_MIN_WEEKS_MUJERES = {
    2025: 1275, 2026: 1250, 2027: 1225, 2028: 1200, 2029: 1175,
    2030: 1150, 2031: 1125, 2032: 1100, 2033: 1075, 2034: 1050,
    2035: 1025,
}
# A partir de 2036: 1.000 semanas (piso).


def min_weeks(sexo, year_pension, num_hijos=0):
    """Semanas mínimas requeridas según el año en que se cumple la edad de pensión.
    Mujeres con hijos: -50 sem/hijo (máx 3, piso 850) — Art. 36 Ley 2381/2024."""
    if sexo == 'M':
        return 1300
    if year_pension >= 2036:
        base = 1000
    else:
        base = _MIN_WEEKS_MUJERES.get(year_pension, 1300 if year_pension < 2025 else 1000)
    if num_hijos > 0:
        base = max(850, base - min(num_hijos, 3) * 50)
    return base


# Régimen de transición (Art. 75 Ley 2381/2024).
# Quienes a la entrada en vigencia (1 jul 2025) tenían >=750 (M) o >=900 (H)
# semanas cotizadas siguen 100% bajo Ley 100/1993 (prima media completa,
# sin split a Componente Complementario de Ahorro Individual).
FECHA_VIGENCIA_REFORMA = date(2025, 7, 1)
SEMANAS_TRANSICION = {'M': 900, 'F': 750}

MESES_POR_SEMANA_INV = 30 / 7  # 4.2857 semanas por mes completo (convención Colpensiones)

# Descuentos sobre la mesada pensional
DESCUENTO_SALUD = 0.12  # 12% aporte a salud (Art. 204 Ley 100 mod. Ley 1122/2007)

# Expectativa de vida adicional a la edad de pensión (DANE, tablas de mortalidad 2020)
EXPECT_VIDA = {'M': 18.5, 'F': 26.0}  # años adicionales después de los 62/57

# Cotización adicional al Fondo de Solidaridad Pensional
# Art. 27 Ley 100/1993 mod. Art. 8 Ley 797/2003; confirmado por Art. 20 Ley 2381/2024
# (lo, hi) en SMLMV, tasa sobre la porción en ese tramo
TRAMOS_SOLIDARIDAD = [
    (4, 16, 0.010),
    (16, 17, 0.012),
    (17, 18, 0.014),
    (18, 19, 0.016),
    (19, 20, 0.018),
    (20, 25, 0.020),
]


def build_ipc_index():
    """index[y] = índice acumulado a diciembre del año y (base arbitraria)."""
    years = sorted(IPC_ANUAL.keys())
    index = {}
    base_year = years[0] - 1
    index[base_year] = 1.0
    for y in years:
        index[y] = index[y - 1] * (1 + IPC_ANUAL[y] / 100)
    return index


IPC_INDEX = build_ipc_index()


def indexar(valor, year_origen, year_valuacion):
    """Indexa un valor cotizado en year_origen a pesos de year_valuacion,
    usando el índice de diciembre del año anterior en cada extremo
    (metodología Corte Suprema / Colpensiones)."""
    ini = IPC_INDEX.get(year_origen - 1, IPC_INDEX[min(IPC_INDEX)])
    fin = IPC_INDEX.get(year_valuacion - 1, IPC_INDEX[max(IPC_INDEX)])
    return valor * (fin / ini)


def smlmv_de(year):
    if year in SMLMV:
        return SMLMV[year]
    # extrapola con la última inflación conocida si el año pedido está fuera de rango
    last_year = max(SMLMV.keys())
    val = SMLMV[last_year]
    infl = IPC_ANUAL.get(last_year + 1, 5.0) / 100
    while last_year < year:
        val *= (1 + infl)
        last_year += 1
    return val


# ---------------------------------------------------------------------
# 2. TASA DE REEMPLAZO Y PENSIÓN
# ---------------------------------------------------------------------

def tasa_reemplazo(ibl, semanas_totales, sexo, year_valuacion, num_hijos=0):
    smlmv = smlmv_de(year_valuacion)
    s = ibl / smlmv
    r_base = 65.50 - 0.50 * s
    r_base = max(55.0, min(r_base, 65.50))
    mw = min_weeks(sexo, year_valuacion, num_hijos)
    exceso = max(0, semanas_totales - mw)
    incremento = (exceso // 50) * 1.5
    r = min(r_base + incremento, 80.0)
    return r, r_base, incremento, exceso, smlmv


def calcular_pension(ibl, semanas_totales, sexo, year_valuacion, num_hijos=0):
    r, r_base, incremento, exceso, smlmv = tasa_reemplazo(ibl, semanas_totales, sexo, year_valuacion, num_hijos)
    pension = ibl * r / 100
    pension = max(pension, smlmv)          # mesada mínima = 1 SMLMV
    pension = min(pension, 25 * smlmv)     # techo legal = 25 SMLMV
    return {
        'ibl': ibl, 'tasa_reemplazo': r, 'tasa_base': r_base,
        'incremento_pct': incremento, 'semanas_exceso': exceso,
        'pension_mensual': pension, 'smlmv_usado': smlmv,
    }


# ---------------------------------------------------------------------
# 2b. PENSIÓN NETA, SOLIDARIDAD, VALOR DE POR VIDA, SOBREVIVIENTES
# ---------------------------------------------------------------------

def pension_neta(pension_bruta):
    """Descuentos obligatorios sobre la mesada: 12% aporte a salud.
    Retención en fuente: pensiones exentas hasta 1.000 UVT mensuales
    (Art. 206 num. 5 E.T.); con el tope de 25 SMLMV, ninguna pensión de
    Colpensiones alcanza ese umbral → retención = 0."""
    salud = pension_bruta * DESCUENTO_SALUD
    neta = pension_bruta - salud
    return neta, salud


def cotizacion_solidaridad(ibc, smlmv):
    """Cotización adicional al Fondo de Solidaridad para IBC > 4 SMLMV."""
    if ibc <= 4 * smlmv:
        return {'aplica': False, 'valor_mensual': 0, 'valor_anual': 0, 'tramos': []}
    tramos = []
    total = 0
    for lo, hi, tasa in TRAMOS_SOLIDARIDAD:
        base_lo = lo * smlmv
        base_hi = hi * smlmv
        if ibc > base_lo:
            gravable = min(ibc, base_hi) - base_lo
            valor = gravable * tasa
            total += valor
            tramos.append({'desde_smlmv': lo, 'hasta_smlmv': hi,
                           'tasa_pct': tasa * 100, 'valor': valor})
    return {'aplica': True, 'valor_mensual': total, 'valor_anual': total * 12,
            'tramos': tramos}


def calc_valor_vida(pension_mensual, pension_neta_mensual, sexo, vr_total_aportes):
    """Valor acumulado de mesadas durante la expectativa de vida restante."""
    anos = EXPECT_VIDA[sexo]
    total_mesadas = anos * MESADAS_ANUALES
    bruto_vida = pension_mensual * total_mesadas
    neto_vida = pension_neta_mensual * total_mesadas
    roi = neto_vida / vr_total_aportes if vr_total_aportes > 0 else 0
    return {
        'expectativa_anos': anos,
        'edad_esperada': EDAD_PENSION[sexo] + anos,
        'total_mesadas': total_mesadas,
        'bruto_acumulado': bruto_vida,
        'neto_acumulado': neto_vida,
        'total_aportado': vr_total_aportes,
        'multiplicador': roi,
    }


def calc_indemnizacion_sustitutiva(ibl, semanas, serie_vida, year_valuacion):
    """Indemnización sustitutiva de la pensión de vejez (Art. 37 Ley 100/1993,
    reglamentada por Decreto 1730 de 2001, Art. 2).

    Solo aplica cuando el afiliado cumple la edad de pensión SIN completar las
    semanas mínimas.  En prima media no existe opción de "pago único" para
    quien ya cumple requisitos: el derecho es a la mesada vitalicia.

    Fórmula legal (Decreto 1730/2001):
      Indemnización = IBL_semanal × semanas × tasa_promedio_ponderada

    Donde IBL_semanal = IBL_mensual × 12 / 52 y tasa_promedio_ponderada es el
    promedio ponderado de las tasas de cotización históricas del afiliado."""
    ibl_semanal = ibl * 12 / 52
    total_meses = 0
    suma_ponderada = 0
    for year_mid, _sal, meses_eq in serie_vida:
        if year_mid < 1994:
            tasa = TASA_APORTE_HISTORICA_PRE1995
        elif year_mid < 2004:
            tasa = 0.135
        else:
            tasa = TASA_APORTE_ACTUAL
        suma_ponderada += tasa * meses_eq
        total_meses += meses_eq
    tasa_prom = suma_ponderada / total_meses if total_meses > 0 else TASA_APORTE_ACTUAL
    valor = ibl_semanal * semanas * tasa_prom
    return {
        'valor': valor,
        'ibl_semanal': ibl_semanal,
        'semanas': semanas,
        'tasa_promedio_ponderada': tasa_prom * 100,
    }


def calc_sobrevivientes(ibl, semanas, pension_mensual, sexo, year):
    """Pensión de sobrevivientes (Art. 46-49 Ley 100/1993 mod. Ley 797/2003).
    a) Fallece como pensionado: beneficiarios reciben 100% de la mesada.
    b) Fallece como afiliado activo (requiere 50 sem en últimos 3 años):
       45% del IBL + 2% por cada 50 sem sobre las primeras 500, techo 75%."""
    smlmv = smlmv_de(year)
    como_pensionado = pension_mensual
    r_base_sob = 45.0
    exceso_sob = max(0, semanas - 500)
    incremento_sob = (exceso_sob // 50) * 2.0
    r_sob = min(r_base_sob + incremento_sob, 75.0)
    como_activo = max(ibl * r_sob / 100, smlmv)
    return {
        'como_pensionado': como_pensionado,
        'como_activo': como_activo,
        'tasa_activo': r_sob,
        'requisito': '50 semanas en los últimos 3 años antes del fallecimiento',
    }


# ---------------------------------------------------------------------
# 3. IBL: PROMEDIO ÚLTIMOS 10 AÑOS COTIZADOS VS TODA LA VIDA LABORAL
# ---------------------------------------------------------------------

def periodo_a_anio(periodo):
    return int(str(periodo)[:4])


def ibl_ultimos_10_anios(serie_mensual, year_valuacion, n_meses=120):
    """serie_mensual: lista de dicts {'period': 'YYYYMM', 'ibc': valor} ordenada asc."""
    ultimos = serie_mensual[-n_meses:]
    if not ultimos:
        return 0
    valores = [indexar(r['ibc'], periodo_a_anio(r['period']), year_valuacion) for r in ultimos]
    return sum(valores) / len(valores)


def ibl_toda_la_vida(serie_completa_ponderada, year_valuacion):
    """serie_completa_ponderada: lista de (year, salario_mensual, peso_en_meses)."""
    total_pond = sum(p for _, _, p in serie_completa_ponderada)
    if total_pond == 0:
        return 0
    acumulado = sum(indexar(sal, y, year_valuacion) * p for y, sal, p in serie_completa_ponderada)
    return acumulado / total_pond


# ---------------------------------------------------------------------
# 4. CARGA DE DATOS EXTRAÍDOS DEL PDF
# ---------------------------------------------------------------------

def cargar_datos(json_path):
    with open(json_path) as f:
        return json.load(f)


def fecha(dstr):
    d, m, y = dstr.split('/')
    return date(int(y), int(m), int(d))


def meses_entre(d1, d2):
    return (d2.year - d1.year) * 12 + (d2.month - d1.month) - (1 if d2.day < d1.day else 0)


SEMANAS_POR_MES = 4.345  # promedio calendario (52.14/12), usado para llevar el IBL mensual a valor semanal


# ---------------------------------------------------------------------
# 4b. ESCENARIO "RETIRO AL CUMPLIR LA EDAD": pensionarse el mismo día que
#     se cumple la edad, frente a seguir cotizando hasta completar el
#     siguiente bloque de 50 semanas (+1,5%).
# ---------------------------------------------------------------------

def _sumar_meses(f, n):
    """Suma n meses a una fecha, recortando el día si el mes destino es más corto."""
    total = f.month - 1 + n
    y = f.year + total // 12
    m = total % 12 + 1
    dias_mes = [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28,
                31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return date(y, m, min(f.day, dias_mes))


def proyectar_hasta(pagos, serie_vida, fecha_hoy, fecha_corte, semanas_hoy,
                    ultimo_salario, vr_total_aportes_hoy, sexo, year_valuacion,
                    num_hijos=0):
    """Proyecta cotizando sobre el último salario hasta fecha_corte y valora
    el IBL en pesos de year_valuacion (año de reconocimiento de la pensión)."""
    meses = max(0, meses_entre(fecha_hoy, fecha_corte))
    semanas = semanas_hoy + meses * MESES_POR_SEMANA_INV

    pagos_proy = list(pagos)
    last_period = int(pagos[-1]['period']) if pagos else int(f"{fecha_hoy.year}{fecha_hoy.month:02d}")
    for _ in range(meses):
        y, m = last_period // 100, last_period % 100 + 1
        if m > 12:
            m, y = 1, y + 1
        last_period = y * 100 + m
        pagos_proy.append({'period': str(last_period), 'ibc': ultimo_salario,
                           'cotizacion': ultimo_salario * TASA_APORTE_ACTUAL})

    serie_proy = serie_vida + ([(fecha_corte.year, ultimo_salario, meses)] if meses else [])

    ibl_10y = ibl_ultimos_10_anios(pagos_proy, year_valuacion)
    ibl_vida = ibl_toda_la_vida(serie_proy, year_valuacion)
    ibl = max(ibl_10y, ibl_vida)
    pension = calcular_pension(ibl, semanas, sexo, year_valuacion, num_hijos)

    return {
        'fecha_corte': fecha_corte.isoformat(),
        'meses_cotizados_adicionales': meses,
        'semanas_cotizadas': semanas,
        'semanas_exceso': pension['semanas_exceso'],
        'ibl': ibl, 'ibl_10y': ibl_10y, 'ibl_vida': ibl_vida,
        'tasa_reemplazo': pension['tasa_reemplazo'],
        'tasa_base': pension['tasa_base'],
        'incremento_pct': pension['incremento_pct'],
        'pension_mensual': pension['pension_mensual'],
        'smlmv': pension['smlmv_usado'],
        'vr_total_aportes': vr_total_aportes_hoy + meses * ultimo_salario * TASA_APORTE_ACTUAL,
    }


def proyectar_retiro_al_cumplir_edad(pagos, serie_vida, fecha_hoy, fecha_pension,
                                     semanas_hoy, ultimo_salario, vr_total_aportes_hoy,
                                     sexo, semanas_faltantes_prox_tramo, num_hijos=0):
    """Compara dos decisiones reales al llegar a la edad de pensión:

      A) Retirarse el mismo día que cumple la edad y empezar a cobrar ya.
      B) Seguir cotizando los meses que falten para completar el siguiente
         bloque de 50 semanas de exceso (+1,5% en la tasa de reemplazo) y
         pensionarse ahí.

    Devuelve ambos escenarios, el costo de esperar (mesadas no cobradas) y
    el punto de equilibrio en meses. También deja la nota legal sobre la
    indemnización sustitutiva, que NO aplica a quien ya superó el mínimo
    de semanas: en el régimen de prima media no hay devolución de aportes.
    """
    mw = min_weeks(sexo, fecha_pension.year, num_hijos)

    # --- A: se pensiona el día que cumple la edad ---
    esc_a = proyectar_hasta(pagos, serie_vida, fecha_hoy, fecha_pension, semanas_hoy,
                            ultimo_salario, vr_total_aportes_hoy, sexo, fecha_pension.year,
                            num_hijos)

    # --- B: sigue cotizando hasta completar el siguiente tramo de 50 semanas ---
    meses_extra = int(math.ceil(semanas_faltantes_prox_tramo / MESES_POR_SEMANA_INV)) \
        if semanas_faltantes_prox_tramo > 0 else 0
    fecha_corte_b = _sumar_meses(fecha_pension, meses_extra)
    esc_b = proyectar_hasta(pagos, serie_vida, fecha_hoy, fecha_corte_b, semanas_hoy,
                            ultimo_salario, vr_total_aportes_hoy, sexo, fecha_corte_b.year,
                            num_hijos)

    # --- Comparación económica ---
    # OJO: la mesada de A también se reajusta por IPC cada enero, así que
    # comparar el nominal de A (pesos de su año) contra el de B (pesos de un
    # año posterior) exagera la ganancia. Se calculan las dos lecturas:
    #   · nominal: tal como saldrían los dos primeros recibos de pago
    #   · real:    llevando la mesada de A al mismo año de B antes de restar
    ganancia_mensual = esc_b['pension_mensual'] - esc_a['pension_mensual']
    pension_a_indexada = indexar(esc_a['pension_mensual'], fecha_pension.year, fecha_corte_b.year)
    ganancia_mensual_real = esc_b['pension_mensual'] - pension_a_indexada

    mesadas_sacrificadas = meses_extra
    costo_esperar = pension_a_indexada * mesadas_sacrificadas
    meses_equilibrio = (costo_esperar / ganancia_mensual) if ganancia_mensual > 0 else None
    meses_equilibrio_real = (costo_esperar / ganancia_mensual_real) if ganancia_mensual_real > 0 else None

    return {
        'fecha_pension': fecha_pension.isoformat(),
        'escenario_a': esc_a,
        'escenario_b': esc_b,
        'meses_extra': meses_extra,
        'semanas_faltantes_prox_tramo': semanas_faltantes_prox_tramo,
        'ganancia_mensual': ganancia_mensual,
        'pension_a_indexada': pension_a_indexada,
        'ganancia_mensual_real': ganancia_mensual_real,
        'mesadas_sacrificadas': mesadas_sacrificadas,
        'costo_esperar': costo_esperar,
        'meses_equilibrio': meses_equilibrio,
        'anios_equilibrio': (meses_equilibrio / 12) if meses_equilibrio else None,
        'meses_equilibrio_real': meses_equilibrio_real,
        'anios_equilibrio_real': (meses_equilibrio_real / 12) if meses_equilibrio_real else None,
        'aplica_indemnizacion_sustitutiva': esc_a['semanas_cotizadas'] < mw,
        'semanas_minimas_requeridas': mw,
    }

# ---------------------------------------------------------------------
# 5. PIPELINE PRINCIPAL
# ---------------------------------------------------------------------

def analizar(json_path, sexo='M', fecha_hoy=None, num_hijos=0, pension_deseada=None):
    d = cargar_datos(json_path)
    fecha_nac = fecha(d['fecha_nacimiento'])
    if fecha_hoy is None:
        fecha_hoy = date.today()

    if (d.get('semanas_tiempos_publicos') is None
            and d.get('semanas_simultaneas') is None):
        logging.warning(
            'Los campos [21] (tiempos públicos) y [25] (simultáneas) no se '
            'extrajeron del PDF. Si el afiliado tiene periodos en entidades '
            'públicas, las semanas totales pueden estar incompletas.')

    edad_pension = EDAD_PENSION[sexo]
    fecha_pension = date(fecha_nac.year + edad_pension, fecha_nac.month, fecha_nac.day)
    year_hoy = fecha_hoy.year
    year_futuro = fecha_pension.year

    semanas_hoy = d['semanas_totales_oficial']
    mw = min_weeks(sexo, year_futuro, num_hijos)

    pagos = sorted(d['pagos_mensuales'], key=lambda r: r['period'])
    ultimo_salario = pagos[-1]['ibc'] if pagos else None

    # --- Serie ponderada toda la vida laboral (pre-1995 + post-1995) ---
    serie_vida = []
    for r in d['resumen_periodos']:
        y_ini = fecha(r['desde']).year
        y_fin = fecha(r['hasta']).year
        y_mid = round((y_ini + y_fin) / 2)
        meses_eq = r['semanas'] / MESES_POR_SEMANA_INV
        serie_vida.append((y_mid, r['ultimo_salario'], meses_eq))

    # --- Aportes ---
    aportes_post1995 = sum(p['cotizacion'] for p in pagos)
    # pre-1995: estimado con tarifa histórica sobre "último salario" del resumen (no viene en el reporte)
    aportes_pre1995_est = 0
    for r in d['resumen_periodos']:
        if fecha(r['hasta']).year < 1995:
            meses_eq = r['semanas'] / MESES_POR_SEMANA_INV
            aportes_pre1995_est += r['ultimo_salario'] * meses_eq * TASA_APORTE_HISTORICA_PRE1995
    vr_total_aportes_hoy = aportes_post1995 + aportes_pre1995_est

    # ================= HOY =================
    ibl_10y_hoy = ibl_ultimos_10_anios(pagos, year_hoy)
    ibl_vida_hoy = ibl_toda_la_vida(serie_vida, year_hoy)
    ibl_hoy = max(ibl_10y_hoy, ibl_vida_hoy)
    pension_hoy = calcular_pension(ibl_hoy, semanas_hoy, sexo, year_hoy, num_hijos)

    # ================= FUTURO (a la edad de pensión, cotizando sobre último sueldo) =================
    meses_restantes = max(0, meses_entre(fecha_hoy, fecha_pension))
    semanas_futuras = semanas_hoy + meses_restantes * MESES_POR_SEMANA_INV

    pagos_futuros = list(pagos)
    last_period = int(pagos[-1]['period']) if pagos else int(f"{year_hoy}{fecha_hoy.month:02d}")
    for i in range(1, meses_restantes + 1):
        y = last_period // 100
        m = last_period % 100 + 1
        if m > 12:
            m = 1
            y += 1
        last_period = y * 100 + m
        pagos_futuros.append({'period': str(last_period), 'ibc': ultimo_salario,
                               'cotizacion': ultimo_salario * TASA_APORTE_ACTUAL})

    serie_vida_futura = serie_vida + [(year_futuro, ultimo_salario, meses_restantes)] if meses_restantes else serie_vida

    ibl_10y_fut = ibl_ultimos_10_anios(pagos_futuros, year_futuro)
    ibl_vida_fut = ibl_toda_la_vida(serie_vida_futura, year_futuro)
    ibl_futura = max(ibl_10y_fut, ibl_vida_fut)
    pension_futura = calcular_pension(ibl_futura, semanas_futuras, sexo, year_futuro, num_hijos)

    aportes_futuros_adicionales = meses_restantes * ultimo_salario * TASA_APORTE_ACTUAL
    vr_total_aportes_futura = vr_total_aportes_hoy + aportes_futuros_adicionales

    # semanas faltantes para subir de tramo, contadas DESPUÉS de la edad de
    # pensión: usa las semanas cotizadas proyectadas (semanas_futuras), no las
    # de hoy, porque lo que se busca es cuántos meses más habría que seguir
    # cotizando *después* de cumplir la edad para completar el siguiente
    # bloque de 50 semanas de exceso.
    exceso_fut = max(0, semanas_futuras - mw)
    resto = exceso_fut % 50
    semanas_faltantes = 0 if resto == 0 else (50 - resto)
    meses_faltantes = semanas_faltantes / MESES_POR_SEMANA_INV

    # ================= SECCIÓN 3: IBC necesario para que pensión futura = sueldo actual =================
    objetivo = ultimo_salario

    def pension_con_ibc(x):
        pf = list(pagos)
        lp = int(pagos[-1]['period']) if pagos else int(f"{year_hoy}{fecha_hoy.month:02d}")
        for i in range(1, meses_restantes + 1):
            y = lp // 100
            m = lp % 100 + 1
            if m > 12:
                m = 1
                y += 1
            lp = y * 100 + m
            pf.append({'period': str(lp), 'ibc': x, 'cotizacion': x * TASA_APORTE_ACTUAL})
        sv = serie_vida + ([(year_futuro, x, meses_restantes)] if meses_restantes else [])
        ibl10 = ibl_ultimos_10_anios(pf, year_futuro)
        iblv = ibl_toda_la_vida(sv, year_futuro)
        ibl_x = max(ibl10, iblv)
        return calcular_pension(ibl_x, semanas_futuras, sexo, year_futuro, num_hijos)['pension_mensual']

    lo, hi = ultimo_salario, 25 * smlmv_de(year_futuro)
    ibc_necesario = None
    if meses_restantes == 0:
        ibc_necesario = None  # ya está en edad de pensión, no hay margen para subir base
    elif pension_con_ibc(hi) < objetivo:
        ibc_necesario = None  # ni con el tope de 25 SMLMV se alcanza (ventana muy corta)
    else:
        for _ in range(60):
            mid = (lo + hi) / 2
            if pension_con_ibc(mid) < objetivo:
                lo = mid
            else:
                hi = mid
        ibc_necesario = hi

    # ================= SECCIÓN 4: RETIRO AL CUMPLIR LA EDAD =================
    retiro_edad = proyectar_retiro_al_cumplir_edad(
        pagos, serie_vida, fecha_hoy, fecha_pension,
        semanas_hoy, ultimo_salario, vr_total_aportes_hoy, sexo, semanas_faltantes,
        num_hijos,
    )

    # ================= RÉGIMEN DE TRANSICIÓN (Art. 75 Ley 2381/2024) =================
    en_transicion = semanas_hoy >= SEMANAS_TRANSICION[sexo]

    # ================= PRESTACIÓN ANTICIPADA (Art. 37 Ley 2381/2024) =================
    # Para quien NO esté en transición, cumpla la edad pero no las semanas
    # mínimas, y tenga ≥1.000 semanas: pensión proporcional.
    prestacion_anticipada = None
    if not en_transicion and semanas_futuras < mw and semanas_futuras >= 1000:
        pension_ant = calcular_pension(ibl_futura, semanas_futuras, sexo, year_futuro, num_hijos)
        proporcion = semanas_futuras / mw
        pension_proporcional = pension_ant['pension_mensual'] * proporcion
        smlmv_fut = smlmv_de(year_futuro)
        pension_proporcional = max(pension_proporcional, smlmv_fut)
        prestacion_anticipada = {
            'semanas_proyectadas': semanas_futuras,
            'semanas_minimas': mw,
            'proporcion': proporcion,
            'pension_mensual_proporcional': pension_proporcional,
        }

    # ================= PENSIÓN NETA (descuentos obligatorios) =================
    neta_hoy, salud_hoy = pension_neta(pension_hoy['pension_mensual'])
    neta_fut, salud_fut = pension_neta(pension_futura['pension_mensual'])

    # ================= COTIZACIÓN SOLIDARIDAD =================
    solidaridad = cotizacion_solidaridad(ultimo_salario, smlmv_de(year_hoy))

    # ================= VALOR DE POR VIDA =================
    vida = calc_valor_vida(pension_futura['pension_mensual'], neta_fut, sexo,
                           vr_total_aportes_futura)

    # ================= PENSIÓN DE SOBREVIVIENTES =================
    sobrevivientes = calc_sobrevivientes(ibl_futura, semanas_futuras,
                                         pension_futura['pension_mensual'], sexo, year_futuro)

    # ================= MULTIESCENARIO TEMPORAL =================
    intervalos = []
    if meses_restantes > 0:
        intervalos.append((0, 'Si deja de cotizar hoy'))
        if meses_restantes > 12:
            intervalos.append((12, '+12 meses cotizando'))
        if meses_restantes > 24:
            intervalos.append((24, '+24 meses cotizando'))
        intervalos.append((meses_restantes, f'Al cumplir {edad_pension} años'))
    else:
        intervalos.append((0, 'Situación actual'))
    meses_extra_tramo = int(math.ceil(semanas_faltantes / MESES_POR_SEMANA_INV)) \
        if semanas_faltantes > 0 else 0
    if meses_extra_tramo > 0:
        intervalos.append((meses_restantes + meses_extra_tramo,
                           f'+{meses_extra_tramo} meses (siguiente tramo)'))
    escenarios = []
    for meses_esc, label_esc in intervalos:
        fecha_corte_esc = _sumar_meses(fecha_hoy, meses_esc)
        year_esc = fecha_corte_esc.year
        esc = proyectar_hasta(pagos, serie_vida, fecha_hoy, fecha_corte_esc,
                              semanas_hoy, ultimo_salario, vr_total_aportes_hoy,
                              sexo, year_esc, num_hijos)
        neta_esc, _ = pension_neta(esc['pension_mensual'])
        escenarios.append({
            'label': label_esc,
            'meses': meses_esc,
            'fecha': fecha_corte_esc.isoformat(),
            'semanas': esc['semanas_cotizadas'],
            'tasa': esc['tasa_reemplazo'],
            'pension_bruta': esc['pension_mensual'],
            'pension_neta': neta_esc,
        })

    # ================= INDEMNIZACIÓN SUSTITUTIVA / ¿Y SI PREFIERO EL DINERO? =====
    indem_fut = calc_indemnizacion_sustitutiva(ibl_futura, semanas_futuras,
                                                serie_vida_futura, year_futuro)
    cumple_semanas = semanas_futuras >= mw
    opcion_dinero = {
        'cumple_semanas': cumple_semanas,
        'semanas_proyectadas': semanas_futuras,
        'semanas_minimas': mw,
        'indemnizacion': indem_fut,
        'pension_bruta_mensual': pension_futura['pension_mensual'],
        'pension_neta_mensual': neta_fut,
        'pension_neta_anual': neta_fut * MESADAS_ANUALES,
        'valor_vida_neto': vida['neto_acumulado'],
        'ratio_pension_vs_indem': vida['neto_acumulado'] / indem_fut['valor'] if indem_fut['valor'] > 0 else 0,
        'proceso_indemnizacion': [
            'Verificar que no cumple las semanas mínimas requeridas.',
            'Radicar solicitud de reconocimiento de indemnización sustitutiva ante Colpensiones '
            '(formulario de solicitud de prestaciones económicas).',
            'Adjuntar: cédula, historia laboral actualizada, certificación bancaria.',
            'Colpensiones tiene 4 meses para resolver (Art. 19 Decreto 656/1994).',
            'Si se niega, procede recurso de reposición y en subsidio apelación.',
        ],
        'proceso_pension': [
            'Cumplir la edad de pensión (62 años hombres / 57 mujeres).',
            'Radicar solicitud de reconocimiento de pensión de vejez ante Colpensiones '
            '(formulario de solicitud de prestaciones económicas).',
            'Adjuntar: cédula, historia laboral actualizada, certificación bancaria, '
            'declaración de beneficiarios.',
            'Colpensiones tiene 4 meses para resolver (Art. 19 Decreto 656/1994).',
            'La mesada se paga mes vencido, vitalicia, con reajuste anual por IPC.',
            'Incluye prima de diciembre (mesada 13).',
        ],
    }

    # ================= PENSIÓN DESEADA =================
    calc_deseada = None
    if pension_deseada is not None and pension_deseada > 0 and meses_restantes > 0:
        pension_fut_actual = pension_futura['pension_mensual']
        if pension_deseada <= pension_fut_actual:
            calc_deseada = {
                'pension_deseada': pension_deseada,
                'ya_alcanzada': True,
                'pension_proyectada': pension_fut_actual,
            }
        else:
            tope = 25 * smlmv_de(year_futuro)
            if pension_con_ibc(tope) < pension_deseada:
                calc_deseada = {
                    'pension_deseada': pension_deseada,
                    'ya_alcanzada': False,
                    'alcanzable': False,
                    'pension_maxima': pension_con_ibc(tope),
                    'ibc_tope': tope,
                }
            else:
                lo_d, hi_d = ultimo_salario, tope
                for _ in range(60):
                    mid_d = (lo_d + hi_d) / 2
                    if pension_con_ibc(mid_d) < pension_deseada:
                        lo_d = mid_d
                    else:
                        hi_d = mid_d
                ibc_deseado = hi_d
                aporte_actual = ultimo_salario * TASA_APORTE_ACTUAL
                aporte_necesario = ibc_deseado * TASA_APORTE_ACTUAL
                solidaridad_nueva = cotizacion_solidaridad(ibc_deseado, smlmv_de(year_futuro))
                neta_deseada, _ = pension_neta(pension_deseada)
                calc_deseada = {
                    'pension_deseada': pension_deseada,
                    'pension_deseada_neta': neta_deseada,
                    'ya_alcanzada': False,
                    'alcanzable': True,
                    'ibc_necesario': ibc_deseado,
                    'ibc_actual': ultimo_salario,
                    'incremento_ibc': ibc_deseado - ultimo_salario,
                    'incremento_ibc_pct': (ibc_deseado / ultimo_salario - 1) * 100,
                    'aporte_mensual_actual': aporte_actual,
                    'aporte_mensual_necesario': aporte_necesario,
                    'aporte_adicional_mensual': aporte_necesario - aporte_actual,
                    'solidaridad_nueva': solidaridad_nueva,
                    'tope_ibc': tope,
                }

    resultado = {
        'afiliado': {
            'nombre': d['nombre'], 'fecha_nacimiento': d['fecha_nacimiento'],
            'fecha_afiliacion': d['fecha_afiliacion'], 'sexo': sexo,
            'edad_pension': edad_pension, 'fecha_pension': fecha_pension.isoformat(),
            'actualizado_a': d['actualizado_a'], 'fecha_calculo': fecha_hoy.isoformat(),
        },
        'reforma_2024': {
            'en_regimen_transicion': en_transicion,
            'semanas_al_1jul2025': semanas_hoy,
            'umbral_transicion': SEMANAS_TRANSICION[sexo],
            'mesadas_anuales': MESADAS_ANUALES,
            'semanas_minimas_requeridas': mw,
            'prestacion_anticipada': prestacion_anticipada,
        },
        'hoy': {
            'semanas_cotizadas': semanas_hoy,
            'semanas_exceso': pension_hoy['semanas_exceso'],
            'vr_total_aportes': vr_total_aportes_hoy,
            'ultimo_salario': ultimo_salario,
            'ibl': ibl_hoy, 'ibl_10y': ibl_10y_hoy, 'ibl_vida': ibl_vida_hoy,
            'tasa_reemplazo': pension_hoy['tasa_reemplazo'],
            'tasa_base': pension_hoy['tasa_base'],
            'incremento_pct': pension_hoy['incremento_pct'],
            'pension_mensual': pension_hoy['pension_mensual'],
            'pension_neta': neta_hoy,
            'descuento_salud': salud_hoy,
            'pension_anual': pension_hoy['pension_mensual'] * MESADAS_ANUALES,
            'pension_anual_neta': neta_hoy * MESADAS_ANUALES,
            'smlmv': pension_hoy['smlmv_usado'],
        },
        'futura': {
            'meses_restantes': meses_restantes,
            'semanas_cotizadas': semanas_futuras,
            'semanas_exceso': pension_futura['semanas_exceso'],
            'vr_total_aportes': vr_total_aportes_futura,
            'ibl': ibl_futura, 'ibl_10y': ibl_10y_fut, 'ibl_vida': ibl_vida_fut,
            'tasa_reemplazo': pension_futura['tasa_reemplazo'],
            'tasa_base': pension_futura['tasa_base'],
            'incremento_pct': pension_futura['incremento_pct'],
            'pension_mensual': pension_futura['pension_mensual'],
            'pension_neta': neta_fut,
            'descuento_salud': salud_fut,
            'pension_anual': pension_futura['pension_mensual'] * MESADAS_ANUALES,
            'pension_anual_neta': neta_fut * MESADAS_ANUALES,
            'smlmv': pension_futura['smlmv_usado'],
            'semanas_faltantes_prox_tramo': semanas_faltantes,
            'meses_faltantes_prox_tramo': meses_faltantes,
        },
        'proyeccion_base_cotizacion': {
            'sueldo_actual_objetivo': objetivo,
            'ibc_necesario': ibc_necesario,
            'incremento_absoluto': (ibc_necesario - ultimo_salario) if ibc_necesario else None,
            'incremento_pct': ((ibc_necesario / ultimo_salario - 1) * 100) if ibc_necesario else None,
            'tope_ibc_25_smlmv': 25 * smlmv_de(year_futuro),
        },
        'retiro_edad': retiro_edad,
        'solidaridad': solidaridad,
        'escenarios': escenarios,
        'valor_vida': vida,
        'sobrevivientes': sobrevivientes,
        'pension_deseada': calc_deseada,
        'opcion_dinero': opcion_dinero,
    }
    return resultado


if __name__ == '__main__':
    json_path = sys.argv[1]
    sexo = sys.argv[2] if len(sys.argv) > 2 else 'M'
    fecha_hoy = None
    if len(sys.argv) > 3:
        y, m, dday = sys.argv[3].split('-')
        fecha_hoy = date(int(y), int(m), int(dday))
    out = analizar(json_path, sexo=sexo, fecha_hoy=fecha_hoy)
    print(json.dumps(out, indent=2, ensure_ascii=False))
