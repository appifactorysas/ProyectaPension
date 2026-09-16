# ProyectaPension — Proyeccion de pension Colpensiones

## Proyecto
Dashboard de proyeccion de pension de vejez en Colpensiones (Colombia). Extrae datos del
PDF de Historia Laboral y genera un informe HTML con 4 secciones: datos actuales, proyeccion
futura, base necesaria para igualar sueldo, y valor devuelto.

## Stack
- **Lenguaje:** Python
- **Dependencias:** ver `requirements.txt`
- **Deploy:** Docker (Gunicorn), ver `DEPLOY.md`
- **Skill guardado:** `proyecta-pension` (reutilizable con nuevo PDF)

## Estado actual
Lee `ESTADO.md` para datos del afiliado, supuestos legales, resultados y pendientes.

## Como correr
Adjuntar PDF de historia laboral y pedir "corre ProyectaPension". El skill pide la
contrasena, verifica SMLMV/IPC vigentes, y regenera todo.

## Reglas criticas
- Actualizar SMLMV 2027 cuando el Gobierno lo fije (dic-2026).
- Actualizar IPC de cierre 2026 cuando el DANE lo certifique (ene-2027).
- Esto es una herramienta educativa, no una liquidacion oficial.
