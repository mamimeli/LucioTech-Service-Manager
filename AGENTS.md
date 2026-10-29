# AGENTS.md

Instrucciones para agentes de IA que trabajen en este repositorio. Léelas antes de tocar código.

## Proyecto

**LucioTech Service Manager**: aplicación de escritorio en Python 3 y PyQt6 para registrar recepción, diagnóstico, reparación y entrega de equipos del servicio técnico del Ing. Lucio. Debe funcionar sin conexión y no enviar datos a servidores externos.

La especificación completa está en `ROADMAP.md`. Es la fuente de verdad para requisitos, esquema y estados de avance.

## Reglas obligatorias

1. **No instalar paquetes.** El usuario instala las dependencias en el `.venv`. Si falta algo, detente y da el comando exacto (`pip install <paquete>`). Las consultas de solo lectura (`pip show`, `python -c "import ..."`) sí están permitidas.
2. **Trabajar siempre dentro del `.venv`.** Ejecuta pruebas con `.venv/bin/python -m pytest`.
3. **Haz commit y push de cada bloque cuando la suite completa pase.** El usuario delegó esto el 2026-10-12. Antes de commitear, revisa `git status` y añade solo los archivos del bloque; nunca incluyas secretos ni datos reales. Nunca reescribas el historial ni hagas push forzado.
4. **Un bloque por respuesta.** Escribe código, pruebas y ejecuta la suite completa en la misma respuesta.
5. **No marcar casillas `[x]` del ROADMAP** hasta que la tarea esté implementada, probada y ejecutada. Si está incompleta, usa `[~]`.
6. **No avanzar de fase** si quedan casillas pendientes en la anterior (ROADMAP §0).
7. **No registrar contraseñas ni PIN** en logs, mensajes ni salidas de comandos.
8. **Ocultar secretos al inspeccionar configuración.** Nunca imprimir API keys ni contraseñas completas.

## Comandos

```bash
# Activar el entorno (desde la raíz del proyecto)
source .venv/bin/activate

# Pruebas completas
.venv/bin/python -m pytest

# Migraciones (la base por defecto está en ~/.local/share/luciotech-service-manager/)
.venv/bin/alembic upgrade head

# Base temporal para pruebas manuales (no toca datos reales)
LUCIOTECH_DATABASE_URL=sqlite:////tmp/luciotech-test.sqlite3 .venv/bin/alembic upgrade head
```

## Estructura

```text
src/luciotech/
├── main.py                   # Punto de entrada: migraciones y ventana principal
├── config.py                 # Nombre, app_id, organización, versión, IVA y textos por defecto
├── database/
│   ├── connection.py         # Motor SQLite, PRAGMA foreign_keys=ON
│   ├── enums.py              # Estados, prioridades, tipos (una sola definición)
│   ├── models.py             # Modelos SQLAlchemy
│   ├── repositories.py       # CRUD por entidad (solo flush, sin commit)
│   ├── migrate.py            # Aplica migraciones al arrancar
│   └── migrations/           # Alembic; versiones en versions/
├── services/                 # Reglas de negocio; reciben la sesión, no hacen commit
│   ├── order_number_service.py    # OT-AAAA-NNNNNN con tabla secuencias
│   ├── totals_service.py          # Fórmula única de totales, IVA y saldo (incluye líneas)
│   ├── state_service.py           # Cambio de estado con historial automático
│   ├── order_service.py           # Creación y borrado lógico de órdenes
│   ├── reception_service.py       # Recepción en una transacción (cliente, equipo, orden)
│   ├── order_query_service.py     # Lista de órdenes con filtros
│   ├── order_detail_service.py    # Pagos, notas y entrega de una orden
│   ├── order_view_service.py      # Datos de las pestañas Cliente y Equipo
│   ├── clinical_text_service.py   # Diagnóstico, trabajo y recomendaciones (HTML)
│   ├── predefined_text_service.py # Textos predefinidos del editor
│   ├── budget_service.py          # Líneas de presupuesto (§12)
│   ├── photo_service.py           # Fotografías: importación con UUID y EXIF
│   ├── dashboard_service.py       # Conteos del panel de inicio
│   ├── settings_service.py        # Tabla configuracion (clave/valor)
│   ├── customer_service.py        # Validación y duplicados de clientes
│   └── equipment_service.py       # Equipos y advertencia por serie repetida
├── ui/
│   ├── main_window.py        # Ventana principal maximizada con pestañas
│   ├── formatting.py         # Formatos de fecha e importe
│   ├── validation_texts.py   # Mensajes de error y nombres de campo
│   ├── documents.py          # Los cinco documentos imprimibles (§13.1)
│   ├── order_actions.py      # Siguiente paso de una orden según su estado (§9)
│   ├── print_support.py      # Tamaño de la vista previa, hoja, encabezado, pie y PDF (§13.2)
│   ├── translations.py       # Diálogos de Qt en español (qtbase_es, qt_es)
│   ├── pages/                # Inicio, órdenes, clientes y equipos
│   ├── dialogs/              # Recepción, detalle de orden, fotos, buscar y reemplazar
│   ├── widgets/              # Editor de texto enriquecido (§8)
│   └── resources/icons/      # Iconos Breeze con CREDITS.md
└── utils/
    ├── paths.py              # Rutas XDG de datos, adjuntos y logs
    └── validators.py         # Cédula (módulo 10), teléfono y correo
tests/                        # pytest y pytest-qt; base temporal por prueba
```

## Convenciones de código

- Usar `from __future__ import annotations` y anotaciones de tipo.
- Docstrings en español en módulos y funciones públicas.
- Importes monetarios con `Decimal`, nunca `float`. Redondeo a centavos con `ROUND_HALF_UP`.
- Consultas solo con SQLAlchemy. No concatenar SQL.
- La UI nunca escribe SQL directamente; pasa por servicios o repositorios.
- Textos visibles al usuario en español y envueltos en `self.tr(...)` cuando haya UI (§21).
- Sin comentarios salvo que expliquen un porqué no evidente.

## Reglas de dominio que no se deben romper

- **Cédula:** módulo 10. No aplicar módulo 11 (eso es para la clave de acceso de facturas).
- **Número de orden:** formato `OT-AAAA-NNNNNN`, generado con la tabla `secuencias` dentro de la transacción. No usar `MAX(id)+1`.
- **Totales:** solo en `totals_service.py`. Fórmula en ROADMAP §5.3.
- **IVA:** **desactivado por defecto** desde `config.py` (los precios del taller ya lo llevan incluido, así que el total es el subtotal); el 15 % sigue configurable y se reactiva con `impuesto_activo`. No dejar el 15 fijo en la lógica.
- **Totales guardados:** al cambiar el IVA hay que recalcular las columnas guardadas de las órdenes (`totals_service.recalculate_stored_totals`, ya se llama al arrancar). Si no, la lista, la papelera y el panel de inicio muestran cifras viejas.
- **Historial de estados:** se crea automáticamente en cada cambio y nunca se borra al editar.
- **Borrado:** lógico (`activo=False`, `fecha_eliminacion`). Cancelar un servicio no es borrarlo.
- **Número de serie repetido:** advertencia no bloqueante.

## Datos y ficheros locales

Las rutas de datos son XDG (`~/.local/share/...` y `~/.local/state/.../logs/`). Nunca commitear datos reales de clientes.

### Reglas de `.gitignore` que conviene conocer

- `logs/` ignora **cualquier carpeta llamada `logs`** en el proyecto, no solo la raíz. Si se crea un paquete o módulo con ese nombre dentro de `src/`, cambia la regla a `/logs/` para no ignorarlo por error.
- `*.sqlite3`, `*.sqlite` y `*.db` impiden versionar bases de datos.
- `attachments/` y `backups/` impiden versionar fotos de equipos y copias de seguridad.
- Los temporales de Kate (`*~`, `*.kate-swp`, `.kateproject`, `.kateconfig`) están ignorados.
- Si un archivo ignorado ya estaba versionado, quítalo del índice con `git rm --cached`, sin borrarlo del disco. Si el archivo nuevo debe versionarse, revisa antes si una regla lo excluye (`git check-ignore -v <ruta>`)

## Documentación que debe mantenerse

- `README.md`: actualizar cuando cambie el comportamiento visible para el usuario.
- `ROADMAP.md`: actualizar casillas al terminar cada tarea y fase.
- Este archivo: actualizar cuando cambien comandos, estructura o reglas.

## Estado actual

- Fase 1 (núcleo) y Fase 2 (diagnóstico, textos predefinidos y fotografías) cerradas. Fase 3 (presupuesto, pagos, PDF e impresión) en curso.
- Bloques 1 a 6 de la Fase 3 entregados: líneas de presupuesto, pestaña Presupuesto y pagos, papelera, los cinco documentos de §13.1 (comprobante de recepción, presupuesto, informe técnico, comprobante de entrega e historial) con selector «Documentos…» en la ventana de la orden, §13.2 (A4/Carta, márgenes, numeración de páginas, encabezado y pie, PDF con nombre descriptivo en `ui/print_support.py`) y el bloque 7 (siguiente paso según el estado en el resumen, `ui/order_actions.py`).
- 373 pruebas pasan con `.venv/Scripts/python.exe -m pytest` en Windows (`.venv/bin/python -m pytest` en Linux/macOS).
- El punto de entrada es `luciotech.main`; ejecútalo con `PYTHONPATH=src` o con el paquete instalado. La aplicación migra la base al arrancar.
