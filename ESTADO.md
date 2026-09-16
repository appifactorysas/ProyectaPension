# ESTADO — Proyecto ProyectaPension (Ricardo Suárez)

Última actualización: 2026-09-12 (v5 — funcionalidades competitivas + pensión deseada)

## 1. Qué es esto

Registro del estado del proyecto **ProyectaPension**: un dashboard de proyección de pensión de vejez en Colpensiones, construido a partir del PDF de Historia Laboral de Ricardo Suárez, y empaquetado como skill reutilizable para futuras actualizaciones. Este archivo resume decisiones, supuestos, resultados y pendientes, para retomar el trabajo sin tener que rehacer todo el análisis.

## 2. Entregables generados

| Archivo | Ubicación | Descripción |
|---|---|---|
| `ProyectaPension_Dashboard.html` | carpeta de salidas | Dashboard final presentado al usuario (3 secciones) |
| Skill `proyecta-pension` | guardado en la cuenta (vía `save_skill`, id `skill_01PeVMfLhkUXoPowN5pGiRsx`) | Contiene instrucciones + los 3 scripts (Anexos A, B, C) autocontenidos para repetir el proceso con una historia laboral nueva |
| `proyecta_pension/extraer_historia.py` | carpeta de salidas | Extrae datos del PDF de Colpensiones a JSON |
| `proyecta_pension/motor_pension.py` | carpeta de salidas | Motor de cálculo (IBL, tasa de reemplazo, proyecciones) |
| `proyecta_pension/generar_dashboard.py` | carpeta de salidas | Genera el HTML del dashboard desde el JSON de resultados |
| `proyecta_pension/historia_extraida.json` | carpeta de salidas | Datos crudos extraídos del PDF (última corrida) |
| `proyecta_pension/resultado.json` | carpeta de salidas | Resultado del motor de cálculo (última corrida) |

Para regenerar todo con una historia laboral nueva: pedirle a Claude que "corra ProyectaPension" con el nuevo PDF adjunto.

## 3. Datos del afiliado (fuente: `historiaLaboral.pdf`, contraseña = cédula)

- Nombre: RICARDO MARIA SUAREZ ORTIZ
- Cédula: 12129894
- Fecha de nacimiento: 19/11/1965
- Fecha de afiliación: 01/08/1986
- Sexo asumido: **Masculino** (inferido del nombre; no confirmado explícitamente por el usuario — ver pendientes)
- Historia laboral actualizada a: 29 julio 2026
- Edad de pensión aplicable: 62 años → fecha estimada de pensión **19/11/2027**

## 4. Supuestos legales aplicados (Colombia, Colpensiones — sep-2026)

- **Ley 2381 de 2024** (reforma pensional, vigente desde 1-jul-2025): el motor ahora integra esta ley directamente, no solo la asume.
- Componente de Prima Media del Pilar Contributivo (Art. 32 Ley 2381/2024, que recoge Ley 100/1993 mod. Ley 797/2003).
- Edad de pensión: 62 años (hombres) / 57 años (mujeres) (Art. 32).
- Semanas mínimas: 1.300 hombres (fijo). Mujeres: tabla progresiva de 1.275 (2025) bajando 25/año hasta 1.000 (2036+) (Art. 32).
- Tasa de reemplazo: `r = 65.50 − 0.50×s` (s = IBL en SMLMV), piso 55%, +1.5% por cada bloque completo de 50 semanas de exceso, techo 80% (Art. 32).
- IBL = mayor entre promedio de últimos 10 años **cotizados** indexado por IPC, y promedio de toda la vida laboral indexado. Indexación con variación de IPC anual dic-dic (Art. 32).
- **Mesadas anuales: 13** (12 mensuales + prima de diciembre, Art. 32 y Art. 88).
- Tope IBC: 25 SMLMV.
- **Régimen de transición (Art. 75)**: el motor ahora **verifica** si el afiliado califica (≥900 sem hombres / ≥750 sem mujeres al 1-jul-2025). Ricardo califica (1.620 sem >> 900). Quien esté en transición sigue 100% en prima media sin split a Componente Complementario de Ahorro Individual.
- **Prestación anticipada (Art. 37)**: para afiliados fuera del régimen de transición que cumplan la edad pero no las semanas mínimas y tengan ≥1.000 sem: se calcula pensión proporcional. No aplica a Ricardo.
- **Beneficio de semanas para madres (Art. 36)**: reducción de 50 sem/hijo (máx 3, piso 850 sem). Implementado en v5 — el formulario recibe `num_hijos` y se propaga a todo el motor.
- Vr. total de aportes 1995-2026: suma real de "Cotización Pagada" del reporte (deduplicada).
- Vr. total de aportes anteriores a 1995: **estimado** con tarifa histórica aproximada del 6.5%.
- SMLMV 2027: estimado en $1.838.450 (~5%) — **aún no fijado oficialmente**.
- IPC 2026 y 2027: estimados en 5.0%.

## 5. Resultados de la última corrida (2026-08-08)

### Sección 1 — Datos actuales (si deja de cotizar hoy)
- Semanas cotizadas: **1.620,00** (1.542,14 cotizadas + 250,72 tiempos públicos − 172,86 simultáneas; cifras oficiales del propio reporte de Colpensiones)
- Semanas de exceso sobre el mínimo (1.300): **320,00** → +9,0% en tasa (6 bloques de 50)
- Valor total aportes: **$197.507.965**
- Último salario reportado: **$8.967.000**
- IBL hoy: $9.507.284 (domina el promedio de últimos 10 años sobre el de toda la vida laboral, $6.794.895)
- Tasa de reemplazo: **71,79%**
- **Pensión proyectada HOY: $6.824.807**

### Sección 2 — Datos futuros (al cumplir 62 años, 19/11/2027 — 15 meses más cotizando sobre el último sueldo)
- Semanas cotizadas proyectadas: **1.684,29**
- Semanas de exceso: **384,29** → +10,5% en tasa (7 bloques de 50)
- Valor total aportes proyectado: **$219.028.765**
- IBL futura: $9.833.408
- Tasa de reemplazo: **73,33%**
- **Pensión proyectada FUTURA: $7.210.408**
- Semanas faltantes próximo tramo (+1,5%): **15,71 semanas (~3,7 meses)**, contadas **después** de cumplir los 62 años (corrección aplicada el 2026-08-08: se calcula sobre las semanas cotizadas proyectadas a la edad de pensión, no sobre las de hoy)

### Sección 3 — Base de cotización necesaria para igualar el sueldo actual
- Meta (sueldo actual): $8.967.000
- IBC mensual necesario (por los 15 meses restantes): **$28.657.578** (+219,6% sobre el IBC actual)
- Tope legal IBC (25 SMLMV 2027): $45.961.250
- Nota: el salto es tan grande porque solo quedan 15 meses de los ~120 que promedia el IBL; con tan poco tiempo restante, el margen de una base de cotización más alta hoy es limitado.

### Sección 4 — Valor devuelto (si se retira y deja de cotizar el 31/12/2026)
- **Aclaración legal clave:** la "indemnización sustitutiva de la pensión de vejez" (Art. 37 Ley 100/1993) — la única figura de devolución de dinero en Colpensiones (régimen de prima media) — **solo aplica a quien llega a la edad de pensión SIN completar las semanas mínimas**. Ricardo ya supera ampliamente el mínimo (1.300), así que **Colpensiones no le devolvería dinero** en ningún escenario; simplemente le paga la mesada mensual al cumplir 62 años, sin importar si sigue cotizando o no después de diciembre de 2026.
- Semanas congeladas al 31/12/2026: **1.637,14** (4 meses más de cotización desde ago-2026)
- IBL congelado (indexado a 2027, año de reconocimiento): $9.964.032
- Tasa de reemplazo congelada: 71,79%
- **Pensión mensual real si se retira ahí (pagada desde los 62 años, nov-2027): $7.153.188**
- Valor total aportes a esa fecha: $203.246.845
- Indemnización sustitutiva hipotética (solo referencia educativa, **no aplica** — `aplica_indemnizacion_sustitutiva: false`): $590.323.806, calculada con una tasa histórica ponderada implícita de 15,72% (derivada de los aportes reales/base nominal de toda su carrera, no de una tabla asumida)

## 6. Historial de correcciones

- **2026-08-08 (v1 → v2):** el usuario pidió que "Semanas Faltantes próximo tramo" del punto 2 se calculara con las "Semanas Cotizadas Proyectadas" del punto 2, para saber cuántos meses faltarían **después** de cumplir la edad de pensión. Se corrigió `motor_pension.py` (usaba `exceso_hoy` calculado sobre las semanas de hoy; ahora usa `exceso_fut` sobre `semanas_futuras`). El resultado cambió de "30 semanas / ~7 meses contados desde hoy" a "15,71 semanas / ~3,7 meses contados después de los 62 años". Cambio aplicado tanto al dashboard como al skill guardado (`overwrite: true`).
- **2026-08-08 (v2 → v3):** se agregó el punto 4 "Valor devuelto", a petición del usuario, para proyectar qué pasaría si se retira y deja de cotizar en diciembre de 2026. Antes de construirlo se verificó la ley (indemnización sustitutiva) y se confirmó que no aplica en su caso; el usuario pidió mostrar ambas cosas: (a) la pensión real que resultaría de congelar semanas/IBL en esa fecha, y (b) el valor hipotético de la indemnización sustitutiva solo como referencia educativa. También se corrigió un bug de formato numérico (las semanas/porcentajes mostraban "1.637.14" en vez de "1.637,14"; ahora todo el dashboard usa separador de miles "." y decimales "," consistente con formato es-CO). Cambios aplicados al dashboard y al skill guardado (`overwrite: true`, nuevo id `skill_01BsZj4wCzEbXfpMGo6tBXc4`).

- **2026-09-02 (v3 → v4):** integración completa de la Ley 2381 de 2024 (reforma pensional). Cambios en `motor_pension.py`: (1) semanas mínimas mujeres ahora son progresivas por año vía función `min_weeks(sexo, year_pension)` en lugar de dict estático; (2) nuevo bloque `reforma_2024` en el resultado con verificación del régimen de transición (Art. 75), mesadas anuales (13), y prestación anticipada (Art. 37); (3) `pension_anual` (mensual × 13) agregada a secciones `hoy` y `futura`; (4) docstring actualizado con todas las fuentes de la Ley 2381/2024. Cambios en `resultado.html`: nueva sección informativa sobre la reforma. Fix previo (misma sesión): regex de extracción de campos [21], [25], [26] del PDF corregidos para tolerar variaciones de espaciado entre versiones de PDF.

- **2026-09-12 (v4 → v5):** paquete de 7 funcionalidades competitivas + pensión deseada. Cambios:
  1. **Pensión neta** (`pension_neta()`): bruta − 12% aporte salud (Art. 204 Ley 100/1993). Sin retención en la fuente (exentas hasta 1.000 UVT, Art. 206 E.T.). Se muestra en secciones hoy/futura del web y PDF.
  2. **Cotización adicional solidaridad** (`cotizacion_solidaridad()`): Art. 27 Ley 100 mod. Ley 797/2003. Tramos escalonados 1.0%–2.0% para IBC > 4 SMLMV. Sección informativa en web y PDF.
  3. **Valor acumulado de por vida** (`calc_valor_vida()`): expectativa DANE (M: 18.5 años después de 62, F: 26.0 después de 57), total mesadas, bruto/neto acumulado, multiplicador ROI. Sección "Riqueza pensional" en web y PDF.
  4. **Pensión de sobrevivientes** (`calc_sobrevivientes()`): Art. 46-49 Ley 100 mod. Ley 797/2003. Como pensionado: 100%. Como activo: 45% IBL + 2%/50 sem sobre 500, tope 75%. Sección en web y PDF.
  5. **Multiescenario temporal**: tabla con pensión a diferentes momentos (hoy, +12m, +24m, a la edad de pensión, +1 tramo). Tabla en web y nueva página en PDF.
  6. **Beneficio hijos mujeres**: Art. 36 Ley 2381/2024. Campo `num_hijos` en formulario, reduce semanas mínimas 50/hijo (máx 3, piso 850). Propagado a `min_weeks()`, `tasa_reemplazo()`, `calcular_pension()`, `proyectar_hasta()`, `proyectar_retiro_al_cumplir_edad()`.
  7. **Pensión deseada**: nuevo campo de formulario. Búsqueda binaria del IBC necesario para alcanzar la mesada deseada. Muestra IBC necesario, aporte mensual, aporte adicional, y pensión neta resultante. 3 variantes: ya alcanzada, no alcanzable (tope 25 SMLMV), alcanzable.
  - Archivos modificados: `motor_pension.py` (4 nuevas funciones + parámetro `num_hijos` en 5 funciones existentes + bloque multiescenario/pensión deseada en `analizar()`), `app.py` (parsing de nuevos campos), `templates/index.html` (2 nuevos campos de formulario), `templates/resultado.html` (5 nuevas secciones de resultados), `generar_pdf.py` (6 nuevos bloques HTML dinámicos + CSS).

## 7. Pendientes / cosas a verificar en el futuro

- **Confirmar el sexo del afiliado** con el usuario de forma explícita (se asumió "M" por el nombre; si en algún momento se corre el skill para otra persona, hay que preguntarlo).
- **Verificar con Colpensiones o un asesor pensional** el régimen de transición. El motor ahora verifica automáticamente la condición del Art. 75 (≥900 sem al 1-jul-2025) y Ricardo califica ampliamente (1.620 sem), pero conviene confirmarlo con fuente oficial.
- **Actualizar el SMLMV 2027** en `motor_pension.py` cuando el Gobierno lo fije oficialmente (diciembre de 2026).
- **Actualizar el IPC de cierre de 2026** en la tabla `IPC_ANUAL` cuando el DANE lo certifique (enero de 2027).
- El estimado de aportes pre-1995 (tarifa 6.5%) es aproximado; si se necesita precisión legal, habría que confirmar la tarifa histórica exacta del ISS para cada año 1986-1994.
- La deduplicación de pagos "ciclo doble" toma el valor máximo por período, lo que puede sobreestimar levemente unos pocos meses de 1999-2000 (impacto marginal sobre el total).
- Este modelo es una **herramienta de proyección educativa**, no una liquidación oficial. Cualquier decisión de pensionarse debe validarse directamente con Colpensiones.

## 8. Cómo continuar

- Para refrescar el dashboard con una historia laboral nueva: adjuntar el PDF actualizado y pedir "corre ProyectaPension" (el skill ya sabe pedir la contraseña, verificar SMLMV/IPC vigentes con WebSearch, y regenerar todo).
- Para ajustar la lógica de cálculo: editar `motor_pension.py` (en la carpeta de salidas o dentro del skill guardado) y volver a correr `extraer_historia.py` → `motor_pension.py` → `generar_dashboard.py`.
- Para cambios permanentes en el skill: usar `save_skill` con `overwrite: true`, igual que se hizo en este proyecto.
