import re, sys, json
import pdfplumber

def to_money(s):
    return int(s.replace('$','').replace(' ','').replace('.','').replace(',',''))

def to_weeks(s):
    return float(s.replace('.','').replace(',','.'))

def extraer(pdf_path, password):
    with pdfplumber.open(pdf_path, password=password) as pdf:
        pages_text = [p.extract_text() for p in pdf.pages]
    text = "\n".join(pages_text)

    data = {}

    # Datos del afiliado
    m = re.search(r'Nombre:\s*(.+?)\s+Correo', text)
    data['nombre'] = m.group(1).strip() if m else None
    m = re.search(r'Fecha de Nacimiento:\s*(\d{2}/\d{2}/\d{4})', text)
    data['fecha_nacimiento'] = m.group(1) if m else None
    m = re.search(r'Fecha Afiliaci[oó]n:\s*(\d{2}/\d{2}/\d{4})', text)
    data['fecha_afiliacion'] = m.group(1) if m else None
    m = re.search(r'ACTUALIZADO A:\s*(\d{1,2}\s+\w+\s+\d{4})', text)
    data['actualizado_a'] = m.group(1) if m else None

    # Totales oficiales de semanas — los regex toleran espacios variables y
    # saltos de línea entre el marcador y el número porque pdfplumber a veces
    # parte la línea en un punto distinto según la versión del PDF.
    m10 = re.search(r'\[10\]\s*TOTAL\s+SEMANAS\s+COTIZADAS:\s*([\d\.,]+)', text)
    m21 = re.search(r'\[21\]\s*TOTAL\s+SEMANAS\s+REPORTADAS:\s*([\d\.,]+)', text)
    m25 = re.search(r'\[25\]\s*TOTAL\s+SEMANAS\s+SIMULT[ÁA]NEAS:\s*([\d\.,]+)', text)
    m26 = re.search(r'\[26\]\s*TOTAL\s+SEMANAS\b.*?\)\s*([\d\.,]+)', text, re.DOTALL)
    data['semanas_cotizadas_oficial'] = to_weeks(m10.group(1)) if m10 else None
    data['semanas_tiempos_publicos'] = to_weeks(m21.group(1)) if m21 else None
    data['semanas_simultaneas'] = to_weeks(m25.group(1)) if m25 else None
    data['semanas_totales_oficial'] = to_weeks(m26.group(1)) if m26 else None

    # Fallback: si [26] no se encontró pero tenemos [10], reconstruir la suma.
    if data['semanas_totales_oficial'] is None and data['semanas_cotizadas_oficial'] is not None:
        tp = data['semanas_tiempos_publicos'] or 0
        sim = data['semanas_simultaneas'] or 0
        data['semanas_totales_oficial'] = data['semanas_cotizadas_oficial'] + tp - sim

    # Resumen por empleador (para último salario y serie histórica aproximada)
    row_re = re.compile(
        r'(\d{6,10})\s+(.+?)\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+\$\s?([\d\.]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s*$',
        re.MULTILINE
    )
    resumen = []
    for m in row_re.finditer(text):
        ident, nombre, desde, hasta, salario, semanas, lic, sim, total = m.groups()
        resumen.append({
            'ident': ident, 'nombre': nombre.strip(), 'desde': desde, 'hasta': hasta,
            'ultimo_salario': to_money('$'+salario), 'semanas': to_weeks(semanas),
            'total': to_weeks(total)
        })
    data['resumen_periodos'] = resumen

    # Detalle de pagos (IBC + cotizacion pagada) 1995+
    lines = text.split('\n')
    pay_re = re.compile(r'(\d{6,10})\D*?\b(SI|NO)\s+(\d{6})\s+(.*)$')
    money_re = re.compile(r'-?\$\s?[\d\.]+')
    pagos = {}
    for line in lines:
        mm = pay_re.search(line.strip())
        if mm:
            ident, ra, period, rest = mm.groups()
            monies = money_re.findall(rest)
            if len(monies) >= 2:
                ibc = to_money(monies[0])
                cot = to_money(monies[1])
                devuelto = 'Devuelto' in rest
                key = (ident, period)
                cot_eff = 0 if devuelto else cot
                if key not in pagos or cot_eff > pagos[key]['cotizacion']:
                    pagos[key] = {'ident': ident, 'period': period, 'ibc': ibc, 'cotizacion': cot_eff}
    pagos_list = sorted(pagos.values(), key=lambda r: r['period'])
    data['pagos_mensuales'] = pagos_list

    return data

if __name__ == '__main__':
    pdf_path = sys.argv[1]
    password = sys.argv[2]
    out = extraer(pdf_path, password)
    with open(sys.argv[3], 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("OK", len(out['pagos_mensuales']), "pagos;", len(out['resumen_periodos']), "periodos resumen")
