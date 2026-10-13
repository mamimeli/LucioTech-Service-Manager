You must develop a professional desktop application in **Python 3 and PyQt6** to register the intake, diagnosis, repair, and delivery of technological equipment received by a technician.

The program will be used by:

**Ing. Lucio — Computer and electronic equipment technical service**

The application must run primarily on **Debian, Ubuntu, MX Linux, and derivative distributions**, but its code must be prepared to run on Windows as well.

The program must be modern, stable, easy to use, and suitable for a person without advanced computer skills.

---

# 0. Progress tracking system

## State legend

- [x] Implemented and verified
- [~] Partially implemented
- [ ] Not implemented yet

### State rules

`[x]` means the functionality is implemented and verified.

`[~]` means there is a partial implementation, but at least one important requirement, test, integration, or validation is still missing.

`[ ]` means it is not implemented yet.

Do not change `[ ]` or `[~]` to `[x]` just because related code exists.

A task can only be marked as `[x]` when the complete requirement is implemented and, where applicable, tested.

### Additional rules for the agent

1. After finishing each task, update its checkbox in this same document.
2. Before starting a new phase, verify that all checkboxes from the previous phase are `[x]`. If any is `[~]` or `[ ]`, do not advance.
3. Do not mark `[x]` without having run the application and the corresponding tests.
4. If a task is split into subtasks, each subtask carries its own checkbox.
5. At the end of each phase, create a Git commit with the message:
   `phase-N: <description> [checklist updated]`.
6. Never edit historical checklists to hide incomplete work. Add new checkboxes when new requirements appear.
7. When a requirement moves to another phase, do not delete it from the checklist where it was written. Mark it in the checklist as `[~]` with the note `trasladado a Fase N (fecha)`, and add it to the checklist of the new phase.
8. Every checkbox marked `[x]` must cite the step or commit that verified it, in the format `(paso N, <hash>)` at the end of the line. Use `(paso N, pendiente de commit)` while the commit does not exist yet.
9. At the start of each phase, copy its checklist into the section "Seguimiento de fase activa" below and work from that copy. Mark items there as they are completed, then copy the final state back to the phase checklist when the phase closes.

## Estado de las fases

| Fase | Estado | Commit de cierre |
|---|---|---|
| Fase 1 — Núcleo ejecutable | Cerrada | `219a877` |
| Fase 2 — Diagnóstico y documentación | Cerrada | `1a7ab2e` |
| Fase 3 — Presupuesto, pagos, PDF e impresión | En curso | — |
| Fase 4 — Reportes, respaldos, configuración y empaquetado | Pendiente | — |

## Requisitos trasladados

| Requisito | Origen | Destino | Motivo |
|---|---|---|---|
| Fotografías de equipos (§5.4 y §7.4) | Fase 1 | Fase 2 | La importación de imágenes requiere copia a `attachments/`, miniaturas y corrección EXIF, que no son parte del núcleo de la Fase 1. Aprobado por el usuario el 2026-10-09. |
| Editor de texto enriquecido para diagnóstico, trabajo y recomendaciones (§8) | Fase 2 (original) | Fase 2 | Sin cambio; se incluye aquí para que el seguimiento de la Fase 2 quede completo. |

## Seguimiento de fase activa

Fase activa: **Fase 3 — Presupuesto, pagos, PDF e impresión** (iniciada; checklist copiado de §26 según la regla 9). Plan de bloques: 1) líneas de presupuesto (modelo, migración y servicio de totales) — entregado, 2) pestaña Presupuesto y pagos — entregado, 3) PDF e impresión, 4) papelera con restauración.

Decisiones de dinero tomadas con el usuario el 2026-10-13:

- El anticipo capturado en la recepción (campo `anticipo` de la orden) y los pagos registrados son registros distintos y ambos restan del saldo, como indica §5.3. La pestaña avisa sin bloquear si se intenta registrar un pago de tipo «Anticipo» existiendo ya un anticipo.
- `costo_repuestos` y `costo_mano_obra` se quedan en cero y no se editan: el presupuesto detallado son las líneas. Así el subtotal no cuenta dos veces el mismo importe.

- [x] Line items model and UI (bloque 1: modelo, migración 0002 y servicio; bloque 2: pestaña «Presupuesto y pagos»)
- [x] Totals calculation service (bloque 1; ampliado con las líneas de presupuesto y probado con la suite)
- [x] Payment registration (existe desde la Fase 1; desde el bloque 2 también hay diálogo propio en la pestaña)
- [x] Balance update (existe desde la Fase 1; verificado con la suite y uso real)
- [x] Payments list with void (bloque 2: listado de pagos con anulación por borrado lógico, migración 0003)
- [ ] PDF library integrated
- [ ] Reception receipt
- [ ] Technical report
- [ ] Budget PDF
- [ ] Delivery receipt PDF
- [ ] Print preview and print dialog
- [~] Tests for PDF generation and totals (totales y pagos cubiertos en los bloques 1 y 2; PDF pendiente)
- [ ] README updated
- [ ] Git commit created

---

# 1. Program name

Use as provisional name:

```text
LucioTech Service Manager
```

The name must be centralized in a configuration file so it can be changed easily. Also centralize:

- `app_id` (used by QSettings)
- `organization_name`
- `application_version`

---

# 2. Objective

The program must allow registering the intake of equipment into the workshop, storing customer and equipment data, documenting diagnosis and repairs, attaching photographs, querying the full history, and printing receipts and reports in PDF.

It must handle the following equipment types:

- Laptop
- Desktop computer
- Printer
- Security camera
- DVR
- NVR
- Monitor
- Router
- Power supply
- Other

The list of equipment types must be manageable from the program's settings.

### Checklist §2

- [ ] Configuration file centralizes name, app_id, organization, version
- [ ] Equipment types stored in database or configuration (not hardcoded)
- [ ] Equipment types editable from Settings

---

# 3. Priority (MoSCoW)

Prioritize work as follows. Do not spend time on "Could" items until all "Must" and "Should" items in the current phase are done.

## Must have

- Customer, equipment, and service order CRUD.
- Cédula validation (Ecuador, módulo 10).
- Rich text editor for diagnosis, work performed, recommendations.
- Photograph import with copy-to-data-directory and EXIF correction.
- PDF generation: reception receipt, technical report, delivery receipt.
- Printing with preview.
- Order list with filters and sorting.
- State history with automatic logging.
- Manual backup and restore (ZIP).
- Settings window.

## Should have

- Budget with line items and totals.
- Payments and balance tracking.
- Reports (equipment, orders, income).
- CSV export.
- Dark/light theme support.
- Soft delete with trash.
- Automatic backups (rotating).

## Could have

- Webcam capture.
- Charts (Qt Charts or matplotlib).
- English translation.
- Multi-user and roles.

## Won't have (now)

- Cloud sync.
- Mobile app.
- Official Registro Civil API integration (only checksum-based validation locally).

### Checklist §3

- [ ] Priorities documented and respected during implementation
- [ ] Must-have features completed before Should-have
- [ ] Should-have completed before Could-have

---

# 4. Project architecture

Create a modular and maintainable structure similar to this:

```text
luciotech_service_manager/
├── pyproject.toml
├── README.md
├── LICENSE
├── requirements.txt
├── src/
│   └── luciotech/
│       ├── __init__.py
│       ├── main.py
│       ├── app.py
│       ├── config.py
│       ├── database/
│       │   ├── connection.py
│       │   ├── models.py
│       │   ├── repositories.py
│       │   └── migrations/
│       ├── services/
│       │   ├── customer_service.py
│       │   ├── equipment_service.py
│       │   ├── repair_service.py
│       │   ├── image_service.py
│       │   ├── pdf_service.py
│       │   ├── backup_service.py
│       │   └── settings_service.py
│       ├── ui/
│       │   ├── main_window.py
│       │   ├── dialogs/
│       │   ├── widgets/
│       │   ├── pages/
│       │   └── resources/
│       ├── reports/
│       │   ├── templates/
│       │   └── styles/
│       ├── utils/
│       │   ├── validators.py
│       │   ├── paths.py
│       │   ├── dates.py
│       │   └── logging_config.py
│       └── translations/
├── tests/
├── packaging/
│   ├── debian/
│   └── appimage/
└── docs/
```

### Technical decisions to document

- **Database migrations:** use **Alembic** with SQLAlchemy.
- **Settings storage:** use **QSettings** for UI preferences (window geometry, table column widths) and the `configuracion` table for business data.
- **User-facing configuration:** stored in database, editable from Settings window.

### Checklist §4

- [ ] Full folder structure created
- [ ] Alembic configured and initial migration created
- [ ] QSettings vs database configuration split documented
- [ ] `pyproject.toml` with dependencies declared
- [ ] `requirements.txt` with pinned versions

---

# 5. Database

Use SQLite via SQLAlchemy.

The database must be stored by default at:

```text
~/.local/share/luciotech-service-manager/database.sqlite3
```

On Windows, use an appropriate path inside the user's application data.

Create at least the following entities.

## 5.1. Customers

Fields:

```text
id
nombre_completo
numero_identificacion
telefono_principal
telefono_secundario
correo_electronico
direccion
notas
fecha_creacion
fecha_actualizacion
```

The identification number may be cédula, RUC, passport, or other.

### Checklist §5.1

- [ ] Model created with all fields
- [ ] Repository with CRUD operations
- [ ] Index on `numero_identificacion`
- [ ] Index on `telefono_principal`
- [ ] Tests for creation, update, deletion

## 5.2. Equipment

Fields:

```text
id
cliente_id
tipo_equipo
marca
modelo
numero_serie
color
sistema_operativo
contrasena_equipo
accesorios_recibidos
estado_fisico
problema_reportado_cliente
observaciones_ingreso
fecha_creacion
fecha_actualizacion
```

The equipment password must not be shown directly in general lists. Add a button to show or hide it when the user has the record open. It must be optional because some equipment does not have one.

**Storage decision:** the equipment password is stored in plain text in the local SQLite database (no server), and the security model relies on filesystem permissions. Document this explicitly in the README and warn the user in the Settings window.

### Checklist §5.2

- [ ] Model created with all fields
- [ ] Password field masked in lists
- [ ] Show/hide button on the order detail form
- [ ] Password field optional
- [ ] Password never written to logs
- [ ] Storage policy documented in README

## 5.3. Service orders

Fields:

```text
id
numero_orden
cliente_id
equipo_id
fecha_ingreso
fecha_estimada_entrega
fecha_finalizacion
fecha_entrega
estado
prioridad
tecnico_responsable
problema_reportado
diagnostico_html
trabajo_realizado_html
recomendaciones_html
repuestos_utilizados
costo_diagnostico
costo_repuestos
costo_mano_obra
descuento
impuestos
total
anticipo
saldo_pendiente
garantia_dias
notas_internas
activo
fecha_eliminacion
fecha_creacion
fecha_actualizacion
```

The order number must be generated automatically. Use a configurable format, for example:

```text
OT-2026-000001
```

Available states (defined once here, referenced elsewhere):

```text
Recibido
Pendiente de diagnóstico
Diagnosticado
Esperando aprobación
Esperando repuesto
En reparación
Reparado
Listo para entregar
Entregado
No reparable
Cancelado
```

Priorities:

```text
Baja
Normal
Alta
Urgente
```

**Clarification about "Cancelado" vs. soft delete vs. trash:**

- `Cancelado` is an operational state of a valid order (e.g., the customer backed out).
- Soft delete (`activo = False`, `fecha_eliminacion` set) is a separate mechanism to remove records from normal views while keeping them recoverable.
- The trash view lists soft-deleted orders and allows restoring them.
- Cancelling does not imply deleting, and deleting does not imply cancelling.

**Total calculation formula (defined once, referenced elsewhere):**

```text
subtotal = costo_diagnostico + costo_repuestos + costo_mano_obra + sum(line_items)
impuestos = round(subtotal * impuesto_porcentaje / 100, 2)   # 0 if taxes disabled
total = round(subtotal - descuento + impuestos, 2)
saldo_pendiente = round(total - anticipo - sum(payments), 2)
```

### Checklist §5.3

- [ ] Model created with all fields including `activo` and `fecha_eliminacion`
- [ ] Order number auto-generated with configurable format
- [ ] Order number generation is atomic (no collisions)
- [ ] States stored as enumerable (or constant list)
- [ ] Priorities stored as enumerable
- [ ] Total and balance calculation implemented once in a service
- [ ] Tests for total calculation with discount, taxes, payments
- [ ] Tests for order number generation
- [ ] Soft delete mechanism implemented
- [ ] Trash view implemented

## 5.4. Photographs

Fields:

```text
id
orden_id
ruta_archivo
nombre_archivo
descripcion
tipo_fotografia
fecha_captura
fecha_creacion
orden_visualizacion
```

Photograph types (defined once here, referenced elsewhere):

```text
Estado al recibir
Número de serie
Accesorios
Daño físico
Proceso de reparación
Equipo reparado
Otro
```

### Checklist §5.4

- [ ] Model created
- [ ] Photograph types stored as enumerable
- [ ] Ordering field respected in UI
- [ ] Tests for creation and ordering

## 5.5. State history

Fields:

```text
id
orden_id
estado_anterior
estado_nuevo
comentario
fecha
usuario
```

Every time the state of an order changes, a record must be created automatically in this history.

### Checklist §5.5

- [ ] Model created
- [ ] Automatic record on state change
- [ ] History never deleted when order is edited
- [ ] Tests for automatic logging

## 5.6. Events or history notes

Fields:

```text
id
orden_id
tipo_evento
titulo
descripcion
fecha
usuario
```

Example event types:

```text
Llamada al cliente
Mensaje enviado
Presupuesto aprobado
Presupuesto rechazado
Repuesto solicitado
Repuesto recibido
Diagnóstico actualizado
Pago recibido
Equipo entregado
Nota interna
```

### Checklist §5.6

- [ ] Model created
- [ ] Event types enumerable
- [ ] UI to add events
- [ ] Events shown in chronological order

## 5.7. Payments

Fields:

```text
id
orden_id
fecha
tipo_pago
metodo_pago
monto
referencia
observaciones
```

Payment types:

```text
Anticipo
Abono
Pago final
Reembolso
```

Payment methods:

```text
Efectivo
Transferencia bancaria
Tarjeta
Depósito
Otro
```

### Checklist §5.7

- [x] Model created (desde la Fase 1; ampliado en el bloque 2 con `anulado`, `fecha_anulacion` y `motivo_anulacion`, migración 0003)
- [x] Payment types enumerable
- [x] Payment methods enumerable
- [x] Balance updates automatically after payment
- [x] Tests for payment registration and balance update
- [x] Payments list with void (bloque 2: la anulación es lógica, el pago sigue en el historial y deja de contar en el saldo)

## 5.8. Configuration

Store:

```text
nombre_taller
nombre_tecnico
numero_identificacion
telefono
correo
direccion
logo
moneda
formato_numero_orden
texto_pie_reporte
condiciones_servicio
ruta_copias_seguridad
tema_visual
idioma
impuesto_porcentaje
impuesto_activo
```

Default currency:

```text
USD
```

Default country: Ecuador.

Default tax: **15% (IVA Ecuador, 2025)**. Editable. Taxes can be disabled with `impuesto_activo = False`.

### Checklist §5.8

- [ ] Model created
- [ ] Default values set for first run
- [ ] Tax configurable and can be disabled
- [ ] Tax default value is 15 but not hardcoded
- [ ] Settings read/write tested

---

# 6. Home panel

The main panel must show information cards:

- Equipment received today
- Pending diagnosis
- Under repair
- Awaiting approval
- Ready for delivery
- Equipment delivered during the month
- Outstanding balance
- Monthly income

It must also show:

- Latest orders created
- Equipment with upcoming estimated delivery
- Overdue orders
- Recent activity

Cards must be clickable to open the corresponding filtered list.

### Checklist §6

- [ ] Cards showing live counts
- [ ] Cards clickable to navigate to filtered list
- [ ] Latest orders list
- [ ] Upcoming delivery list
- [ ] Overdue orders list
- [ ] Recent activity list
- [ ] Counts update after changes without restarting the app

---

# 7. New reception form

Create a wizard or form organized by sections.

## 7.1. Customer data

Fields:

```text
Nombre completo
Cédula, RUC o identificación
Teléfono principal
Teléfono secundario
Correo electrónico
Dirección
Observaciones
```

### 7.1.1. Ecuadorian cédula validation (módulo 10)

The system must validate the Ecuadorian cédula using the **módulo 10** check-digit algorithm:

1. Cédula must be exactly 10 digits.
2. First two digits: province code (01–24, plus 30 for Ecuadorians abroad).
3. Third digit: 0–5 for natural persons.
4. Take the first 9 digits and multiply by coefficients `2, 1, 2, 1, 2, 1, 2, 1, 2`.
5. If a product is ≥ 10, subtract 9.
6. Sum all results.
7. Compute `check = (10 - (sum % 10)) % 10`.
8. Compare with the tenth digit.

**Note (do not confuse):** The **módulo 11** algorithm described by the SRI applies to the 48-digit access key of electronic invoices, **not** to the cédula. Do not apply módulo 11 to cédulas. If RUC validation is implemented (13 digits), it uses a different rule and must be documented separately.

The fields must allow:

- Searching for an already registered customer.
- Autocompleting their data.
- Creating a new customer without leaving the form.
- Showing previous orders of the customer.
- Avoiding duplicates by identification or phone, showing a warning.

### Checklist §7.1

- [ ] Form with all customer fields
- [ ] Customer search with autocomplete
- [ ] Inline creation of new customer
- [ ] Previous orders visible from the form
- [ ] Cédula validation with módulo 10
- [ ] Province code validated (01–24, plus 30)
- [ ] Third digit validated (0–5)
- [ ] Duplicate detection by identification
- [ ] Duplicate detection by phone
- [ ] Warning dialog with possible matches
- [ ] Unit tests for cédula validation (valid and invalid cases)
- [ ] Unit tests for duplicate detection

## 7.2. Equipment data

Fields:

```text
Tipo de equipo
Marca
Modelo
Número de serie
Color
Sistema operativo
Contraseña o PIN
Accesorios recibidos
Estado físico del equipo
Problema reportado por el cliente
Observaciones de ingreso
```

Add quick checkboxes for common accessories:

### Laptop

```text
Cargador
Batería
Bolso
Mouse
Adaptador
Memoria USB
Otro
```

### Desktop computer

```text
Cable de corriente
Monitor
Teclado
Mouse
Parlantes
Adaptador Wi-Fi
Otro
```

### Printer

```text
Cable de corriente
Cable USB
Cartuchos
Botellas de tinta
Bandejas
Otro
```

### Cameras and security systems

```text
Fuente de alimentación
Adaptador
Cable
Disco duro
Control remoto
Mouse
Antena
Otro
```

Allow typing additional accessories manually.

**Duplicate serial number policy:** if a serial number already exists, show a **non-blocking warning** with a link to the existing order. Do not block saving.

### Checklist §7.2

- [ ] Form with all equipment fields
- [ ] Accessory quick-check lists per equipment type
- [ ] Manual accessories field
- [ ] Non-blocking warning for duplicate serial number
- [ ] Password field masked with show/hide button

## 7.3. Reception

Fields:

```text
Fecha y hora de ingreso
Fecha estimada de entrega
Prioridad
Técnico responsable
Costo inicial de diagnóstico
Anticipo recibido
Estado inicial
```

Date and time of entry must be filled automatically but must be editable.

### Checklist §7.3

- [ ] Date and time filled automatically
- [ ] Date and time editable
- [ ] Estimated date cannot be earlier than entry date (validation)
- [ ] Priority selector

## 7.4. Photographs

Allow:

- Selecting one or multiple photographs.
- Dragging and dropping images.
- Pasting an image from the clipboard.
- Capturing a photograph from a webcam, when a compatible camera exists.
- Viewing thumbnails.
- Opening the photograph in full size.
- Rotating the photograph.
- Changing its description.
- Classifying the photograph type.
- Removing it from the order.
- Reordering photographs.

Accepted formats:

```text
JPEG
PNG
WEBP
BMP
```

When importing photographs:

- Create a copy inside the program's data directory.
- Do not depend on the original location.
- Generate thumbnails.
- Preserve the original file when possible.
- Avoid duplicate names using UUID.
- Automatically correct EXIF orientation.
- Optionally compress images that are too large.

Suggested path:

```text
~/.local/share/luciotech-service-manager/attachments/<numero_orden>/
```

### Checklist §7.4

- [ ] Multiple file selector
- [ ] Drag & drop
- [ ] Paste from clipboard
- [ ] Webcam capture (optional, graceful fallback)
- [ ] Thumbnail grid
- [ ] Full-size viewer
- [ ] Rotate image
- [ ] Edit description
- [ ] Classify by type
- [ ] Remove from order
- [ ] Reorder (drag & drop)
- [ ] Copy to data directory
- [ ] EXIF orientation correction
- [ ] Optional compression
- [ ] Tests for import in each supported format
- [ ] Tests for UUID collision handling

## 7.5. Confirmation

Before saving, show a summary with:

- Customer
- Equipment
- Reported problem
- Accessories
- Physical condition
- Photographs
- Entry date
- Down payment
- Order number that will be generated

After saving, offer:

```text
Abrir orden
Imprimir comprobante
Exportar PDF
Crear otra recepción
```

### Checklist §7.5

- [ ] Summary dialog before saving
- [ ] Post-save action dialog
- [ ] Order number shown in summary

---

# 8. Word-like diagnosis editor

The diagnosis must be written in a rich text editor based on `QTextEdit`.

Create a toolbar with:

- Font family
- Font size
- Bold
- Italic
- Underline
- Strikethrough
- Text color
- Background color
- Align left
- Center
- Align right
- Justify
- Bullet list
- Numbered list
- Increase indent
- Decrease indent
- Undo
- Redo
- Cut
- Copy
- Paste
- Paste as plain text
- Insert table
- Insert image
- Insert horizontal line
- Clear formatting
- Find and replace
- Zoom
- Print preview

The content must be stored as clean HTML compatible with `QTextDocument`.

Create separate editors for:

```text
Diagnóstico técnico
Trabajo realizado
Recomendaciones al cliente
```

The editor must allow adding predefined texts, for example:

```text
Se realizó inspección visual del equipo.
Se realizaron pruebas de encendido.
Se verificó el estado del almacenamiento.
Se verificó la memoria RAM.
Se recomienda realizar mantenimiento preventivo.
Se recomienda reemplazar el componente defectuoso.
El equipo fue probado y funciona correctamente.
```

Templates must be manageable from Settings.

### Checklist §8

- [ ] Rich text editor widget reusable
- [ ] Full toolbar implemented
- [ ] Three separate editors integrated into the order view
- [ ] Content stored as clean HTML
- [ ] HTML sanitized/escaped before display
- [ ] Predefined text dropdown
- [ ] Predefined texts manageable from Settings
- [ ] Find and replace dialog
- [ ] Zoom control
- [ ] Tests for HTML round-trip (save/load)

---

# 9. Order view

The order detail must show tabs:

```text
Resumen
Cliente
Equipo
Diagnóstico
Reparación
Fotografías
Presupuesto y pagos
Historial
```

The "Documentos" tab from the previous draft has been removed. Documents are generated on demand from the Summary tab.

## Summary

Show:

- Order number
- State
- Priority
- Customer
- Phone
- Equipment
- Brand
- Model
- Serial number
- Entry date
- Estimated date
- Outstanding balance
- Technician in charge

Include quick buttons:

```text
Editar
Cambiar estado
Añadir nota
Registrar pago
Añadir fotografías
Generar PDF
Imprimir
Marcar como entregado
```

## History

Show a chronological timeline with:

- Date and time
- Event type
- State
- User
- Comment
- Changes made

Do not delete historical events when editing the order.

### Checklist §9

- [x] Tabbed order view
- [~] Summary tab with all fields (falta el técnico responsable)
- [ ] Quick action buttons
- [x] State change button with history log
- [x] Payment registration dialog
- [x] Add note dialog
- [x] Add photographs dialog
- [ ] PDF generation from Summary tab
- [ ] Print from Summary tab
- [x] "Mark as delivered" action
- [x] History tab with chronological timeline
- [x] "Presupuesto y pagos" tab (bloque 2 de la Fase 3: líneas, descuento, totales en vivo y pagos)

---

# 10. Order list

Create an advanced table with columns:

```text
Número de orden
Fecha de ingreso
Cliente
Teléfono
Tipo de equipo
Marca y modelo
Número de serie
Problema reportado
Estado
Prioridad
Fecha estimada
Total
Saldo
```

Allow:

- Sorting columns.
- Hiding or showing columns.
- Changing width.
- Saving table configuration.
- Opening an order with double click.
- Context menu.
- Exporting results.
- Printing the list.
- Multiple selection.

Add filters:

```text
Texto libre
Número de orden
Cliente
Teléfono
Tipo de equipo
Marca
Número de serie
Estado
Prioridad
Técnico
Rango de fechas
Con saldo pendiente
Con retraso
```

Search must run on typing, with a short delay to avoid excessive queries (debounce).

**Table configuration storage:** QSettings, keyed by table name.

### Checklist §10

- [ ] Table with all defined columns
- [ ] Column sorting
- [ ] Column visibility toggle
- [ ] Column width persistence (QSettings)
- [ ] Double-click opens order
- [ ] Context menu
- [ ] CSV export
- [ ] Print list
- [ ] Multiple selection
- [ ] All filters implemented
- [ ] Debounced search
- [ ] Tests for filter combinations

---

# 11. Customers and history

Each customer's profile must show:

- Personal data
- Registered equipment
- Previous orders
- Equipment currently under repair
- Payments made
- Outstanding balance
- Notes
- Last visit date

Allow opening any previous order.

Add an option to generate a PDF report with the customer's complete history.

### Checklist §11

- [ ] Customer profile view
- [ ] Equipment list per customer
- [ ] Order history per customer
- [ ] Payments list per customer
- [ ] Outstanding balance calculation
- [ ] Last visit date
- [ ] PDF history report

---

# 12. Budgets and costs

Allow adding individual line items:

```text
Diagnóstico
Mano de obra
Repuesto
Accesorio
Servicio
Otro
```

Each line item must contain:

```text
Descripción
Cantidad
Precio unitario
Subtotal
```

Automatically calculate (using the formula defined in §5.3):

```text
Subtotal
Descuento
Impuestos
Total
Anticipo
Pagos realizados
Saldo pendiente
```

Allow configuring whether the workshop uses taxes.

For Ecuador, allow configuring IVA, but do not permanently hardcode a percentage in the code. It must be an editable value from Settings (default 15%, see §5.8).

### Checklist §12

- [x] Line items model and table (bloque 1 de la Fase 3; migración 0002)
- [x] Add / edit / remove line items (bloque 1: servicio; bloque 2: pestaña «Presupuesto y pagos»)
- [x] Subtotal per line item (se calcula, no se guarda)
- [x] Subtotal, discount, taxes, total, balance computed via shared service (totals_service ampliado con las líneas)
- [x] Discount editable from the budget tab (bloque 2: `budget_service.set_discount`, recalculado en vivo)
- [~] Tax configurable from Settings (configurable en la tabla configuracion desde la Fase 1, con 15% por defecto; la ventana de Ajustes llega en la Fase 4)
- [x] Tests for totals with different tax rates and discounts (bloques 1 y 2)

---

# 13. Documents and printing (PDF + printing consolidated)

The program must generate professional PDF documents and print them.

## 13.1. PDF document types

Create at least these types:

### 13.1.1. Reception receipt

Must include:

- Workshop logo
- Workshop name
- Technician name
- Address
- Phone
- Email
- Order number
- Entry date and time
- Customer data
- Equipment data
- Serial number
- Reported problem
- Physical condition
- Accessories received
- Selected photographs
- Down payment
- Balance
- Estimated delivery date
- Service conditions
- Space for customer signature
- Space for technician signature

### 13.1.2. Technical report

Must include:

- Workshop data
- Customer data
- Equipment data
- Reported problem
- Technical diagnosis
- Work performed
- Parts used
- Recommendations
- Before and after photographs
- Costs
- Warranty
- Signatures

### 13.1.3. Budget

Must include:

- Line item list
- Quantities
- Prices
- Subtotals
- Taxes
- Total
- Budget validity
- Space for customer approval

### 13.1.4. Delivery receipt

Must include:

- Order data
- Work performed
- Final state
- Payments
- Balance
- Warranty
- Delivery date
- Declaration of conformity
- Customer signature
- Technician signature

### 13.1.5. Full history

Must contain all events of the order in chronological order.

## 13.2. PDF requirements

PDFs must:

- Be A4 size by default.
- Allow choosing Letter size.
- Include page numbers.
- Allow preview.
- Allow saving as file.
- Allow sending directly to printer.
- Correctly split content across pages.
- Respect rich text, tables, and images.
- Avoid deforming images.
- Include header and footer.
- Use configurable margins.

File name must be descriptive, for example:

```text
OT-2026-000001_Juan-Perez_Informe-Tecnico.pdf
```

## 13.3. Printing

Implement printing using:

```text
QPrinter
QPrintDialog
QPrintPreviewDialog
QPageLayout
QPageSize
```

Allow:

- Selecting printer.
- Choosing orientation.
- Choosing paper size.
- Setting margins.
- Printing all pages.
- Choosing page range.
- Setting number of copies.
- Previewing before printing.

**Recommended implementation:** generate PDFs with **ReportLab** or **WeasyPrint** (choose one and document the decision). Use Qt printing only for the print dialog and preview. If using QTextDocument for PDF export, document the limitations.

### Checklist §13

- [ ] PDF generation library chosen and documented
- [ ] Reception receipt template
- [ ] Technical report template
- [ ] Budget template
- [ ] Delivery receipt template
- [ ] Full history template
- [ ] A4 and Letter sizes
- [ ] Page numbers
- [ ] Header and footer
- [ ] Configurable margins
- [ ] Descriptive file names
- [ ] Preview dialog
- [ ] Print dialog
- [ ] Page range selection
- [ ] Multiple copies
- [ ] Tests for PDF generation (at least file creation and text extraction)

---

# 14. Reports

Create a reports section with filters by date range.

Required reports:

```text
Equipos ingresados
Equipos entregados
Equipos pendientes
Equipos por tipo
Equipos por marca
Órdenes por estado
Órdenes atrasadas
Trabajos no reparables
Ingresos económicos
Pagos recibidos
Saldos pendientes
Clientes frecuentes
Repuestos utilizados
```

Allow exporting reports to:

```text
PDF
CSV
```

Economic reports must show:

```text
Ingresos por día
Ingresos por semana
Ingresos por mes
Costos de repuestos
Mano de obra
Saldo pendiente
Total cobrado
```

Add simple charts using Qt Charts (`PyQt6-Charts`) or matplotlib, keeping this dependency as **optional**. If not installed, the app must still work without charts.

### Checklist §14

- [ ] Reports section with date range filter
- [ ] All required reports implemented
- [ ] PDF export per report
- [ ] CSV export per report
- [ ] Economic report totals
- [ ] Optional charts with graceful fallback
- [ ] `PyQt6-Charts` or matplotlib declared as optional dependency
- [ ] Tests for report calculations

---

# 15. Backups

Create a backup system that includes:

- Database.
- Photographs.
- Logo.
- Configuration.
- Text templates.
- Report templates.

Create backups in format:

```text
ZIP
```

Allow:

- Creating a manual backup.
- Choosing destination folder.
- Restoring a backup.
- Verifying integrity before restoring.
- Creating automatic backups.
- Keeping the last N backups.
- Showing date and size of each backup.
- Opening the backups folder.

Before restoring, automatically create a backup of the current state.

Clearly show that a restoration will replace existing data.

### Checklist §15

- [ ] ZIP backup creation
- [ ] Manual backup with destination chooser
- [ ] Automatic backups with rotation
- [ ] Keep last N backups configurable
- [ ] Backup list with date and size
- [ ] Integrity check before restore
- [ ] Automatic pre-restore backup
- [ ] Confirmation dialog for restore
- [ ] Tests for backup and restore

---

# 16. Settings

Create a settings window organized by categories:

```text
Taller
Técnico
Numeración
Tipos de equipos
Estados
Costos e impuestos
Textos predefinidos
Documentos PDF
Fotografías
Copias de seguridad
Apariencia
Idioma
```

## Initial data

Use:

```text
Nombre del técnico: Ing. Lucio
Moneda: USD
País: Ecuador
IVA por defecto: 15%
```

All other data must remain editable.

Allow uploading the workshop logo.

### Checklist §16

- [ ] Settings window with categories
- [ ] All categories editable
- [ ] Logo upload
- [ ] Equipment types editable
- [ ] Predefined text templates editable
- [ ] Tax rate editable and can be disabled
- [ ] Backup path editable
- [ ] Theme selector
- [ ] Language selector (Spanish default)
- [ ] Settings persisted and reloaded on startup

---

# 17. Visual design

Create a clean and professional interface.

Requirements:

- Modern design.
- Good readability.
- Adequate spacing.
- Clearly identified buttons.
- Do not overload the interface.
- Adapt to resolutions from 1366 × 768.
- Allow maximizing the window.
- Remember size and position.
- Remember panel and splitter state.
- Support light and dark theme.
- Do not use fixed colors that prevent working with dark themes.
- Respect the system palette.
- Use QSS stylesheets only when necessary.

Show states with colored visual labels, but always include the text so as not to depend only on color.

### Checklist §17

- [ ] Clean layout
- [ ] Window geometry persisted
- [ ] Splitter state persisted
- [ ] Light theme works
- [ ] Dark theme works
- [ ] No hardcoded colors breaking themes
- [ ] State labels with text and color
- [ ] Works at 1366 × 768

---

# 18. Validations

Implement validations for:

- Customer name required.
- Valid phone number.
- Estimated date not earlier than entry date.
- Non-negative amounts.
- Down payment not greater than total, unless handled as credit.
- Duplicate serial number, showing warning (see §7.2).
- Duplicate customer, showing possible matches.
- Photographs in valid formats.
- Safe paths and file names.
- Numeric fields with `QDoubleValidator`.
- Confirmation before deleting information.

Do not permanently delete orders by default.

Implement soft delete:

```text
activo
fecha_eliminacion
```

Add a trash view from which an order can be restored.

### Checklist §18

- [ ] All listed validations implemented
- [ ] Cédula validation (see §7.1.1)
- [ ] Duplicate serial number warning
- [ ] Duplicate customer warning
- [ ] Soft delete fields in all relevant models
- [ ] Trash view with restore
- [ ] Tests for each validation

---

# 19. Security and privacy

The application must:

- Work completely offline.
- Not send data to external servers.
- Not log equipment passwords.
- Protect sensitive fields.
- Correctly escape HTML displayed in the UI.
- Avoid SQL injection using SQLAlchemy.
- Confirm destructive operations.
- Prevent an imported photograph from overwriting another file.
- Hide the password or PIN via a password field.

Prepare the architecture to add users and roles in the future. **For the first version, do not create user or role tables.** Only ensure that:
- Any place that writes a `usuario` field uses a configurable value from Settings (default "Ing. Lucio").
- Services do not assume a single global user in a way that would break multi-user later.

### Checklist §19

- [ ] App works offline
- [ ] No external network calls
- [ ] Passwords never logged
- [ ] HTML escaped in UI
- [ ] SQLAlchemy used everywhere (no raw SQL string concatenation)
- [ ] Destructive operations confirmed
- [ ] Photograph import uses UUID file names
- [ ] Password field masked
- [ ] `usuario` field read from Settings
- [ ] No user/role tables created in v1

---

# 20. Error logging

Create logs at:

```text
~/.local/state/luciotech-service-manager/logs/
```

Log:

- Program start and shutdown.
- Database errors.
- Image import failures.
- PDF generation failures.
- Backup failures.
- Unhandled exceptions.

Do not log:

- Passwords.
- PIN.
- Unnecessary sensitive information.

Implement a global exception handler that shows the user a comprehensible message.

### Checklist §20

- [ ] Logging configured with rotation
- [ ] Log path correct per OS
- [ ] All listed events logged
- [ ] No sensitive data in logs
- [ ] Global exception handler shows friendly message
- [ ] Tests for exception handler (non-fatal exception path)

---

# 21. Internationalization

Prepare the program for translations with:

```text
QTranslator
pylupdate6
linguist
lrelease
```

Initial language:

```text
Español
```

Prepare at least translations for:

```text
Español
Inglés
```

Do not write visible texts directly in places that are hard to translate.

### Checklist §21

- [ ] All user-visible strings wrapped with `self.tr(...)`
- [ ] `pylupdate6` configuration
- [ ] Spanish translation loaded by default
- [ ] English translation prepared
- [ ] Language selectable from Settings
- [ ] Language change applies without restart (or documented restart requirement)

---

# 22. Accessibility and usability

Implement:

- Keyboard navigation.
- Correct tab order.
- Keyboard shortcuts.
- Labels associated with each field.
- Tooltips.
- Comprehensible error messages.
- Clear confirmations.
- Configurable font size.
- Good contrast.
- Visible required field indicators.

Suggested shortcuts:

```text
Ctrl+N    New reception
Ctrl+F    Search
Ctrl+S    Save
Ctrl+P    Print
Ctrl+Shift+P    Preview
Ctrl+B    Bold
Ctrl+I    Italic
Ctrl+U    Underline
F5        Refresh
Esc       Close dialog
```

### Checklist §22

- [ ] Keyboard navigation
- [ ] Tab order verified
- [ ] All shortcuts implemented
- [ ] Labels associated with fields
- [ ] Tooltips on non-obvious controls
- [ ] Configurable font size
- [ ] Required fields marked visually
- [ ] Contrast verified in light and dark themes

---

# 23. Tests

Create automated tests using **pytest** and **pytest-qt**.

Test at least:

- Customer creation.
- Equipment creation.
- Order creation.
- Order number generation.
- State change.
- History logging.
- Cost calculation.
- Balance calculation.
- Payment registration.
- Photograph import.
- Backup creation and restore.
- PDF generation.
- Validations (including cédula módulo 10).
- Database migrations.

Use a temporary database during tests.

### Checklist §23

- [ ] `pytest` configured
- [ ] `pytest-qt` configured
- [ ] Temporary database fixture
- [ ] All listed tests implemented
- [ ] Tests pass on a clean checkout
- [ ] Coverage tool configured (optional but recommended)

---

# 24. Packaging

Prepare the project to create:

```text
.deb package
AppImage
Windows executable
```

## Debian

- Use XDG-compatible paths.
- Do not write to `/usr` during execution.
- Include `.desktop` file.
- Include icons in different sizes.
- Include AppStream metadata.
- Include license.
- Include basic manual.
- Correctly declare dependencies.
- Avoid downloading dependencies at runtime.

Suggested tools: **`fpm`** or **`dh-virtualenv`** or **`stdeb`**. Choose one and document it.

Desktop entry:

```ini
[Desktop Entry]
Type=Application
Name=LucioTech Service Manager
Comment=Gestión de recepción y reparación de equipos
Exec=luciotech-service-manager
Icon=luciotech-service-manager
Categories=Office;Utility;
Terminal=false
```

## AppImage

Suggested tool: **`python-appimage`** or **`appimagetool`** with a bundled virtualenv.

## Windows

Suggested tool: **Nuitka** 

### Checklist §24

- [ ] `.deb` build script
- [ ] AppImage build script
- [ ] Nuitka
- [ ] Icons in multiple sizes
- [ ] `.desktop` file
- [ ] AppStream metadata
- [ ] License included
- [ ] Basic manual included
- [ ] Build tested on a clean machine or VM

---

# 25. README

Create a complete README with:

- Description.
- Features.
- Provisional screenshots.
- Requirements.
- Installation in virtual environment.
- Execution.
- Tests.
- Project structure.
- Package creation.
- Data location.
- Backup creation.
- Restore.
- Troubleshooting.
- License.

Include instructions like:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
python -m luciotech.main
```

### Checklist §25

- [ ] All sections present
- [ ] Installation instructions verified on a clean environment
- [ ] Test instructions verified
- [ ] Data locations documented
- [ ] Backup/restore documented

---

# 26. Implementation methodology

Do not try to build everything in one step.

Work in phases and always keep a runnable version.

## Phase 1

Create:

- Project structure.
- Main window.
- Database.
- Models.
- Customers.
- Equipment.
- New reception.
- Order list.
- Basic order view.

### Checklist Phase 1

- [x] Project structure created
- [x] `pyproject.toml`, `requirements.txt`
- [x] Main window opens and closes without errors
- [x] SQLAlchemy configured
- [x] All models created
- [x] Alembic initial migration applied
- [x] Repositories with CRUD
- [x] Customer form with cédula validation
- [x] Equipment form
- [x] Reception form
- [x] Order list with basic filters
- [x] Basic order view (Summary, Customer, Equipment, History)
- [x] Order number auto-generated
- [x] State history logging
- [x] Tests for cédula validation, order number generation, totals
- [x] README updated
- [ ] Git commit created

> Nota (2026-10-09): las fotografías (§5.4 y §7.4) no forman parte de la Fase 1; se trasladan a la Fase 2. La lista de órdenes filtra por texto, estado, prioridad, tipo de equipo y saldo; no incluye columnas ordenables ni exportación CSV, que quedan para fases posteriores de §10.

## Phase 2

Create:

- Rich text editor.
- Diagnosis.
- Work performed.
- Recommendations.
- History.
- States.
- Photographs.

### Checklist Phase 2

- [x] Rich text editor widget (pasos 10 y 12, `57b1df8` y `76fe7a9`)
- [x] Diagnosis editor integrated (paso 11, `3d844ee`)
- [x] Work performed editor integrated (paso 11, `3d844ee`)
- [x] Recommendations editor integrated (pasos 11 y 13, `3d844ee` y `a83b911`)
- [x] Predefined texts (pasos 11 y 12, `3d844ee` y `76fe7a9`; edición desde Ajustes queda en Fase 4)
- [x] State change with history (paso 4 de la Fase 1; reutilizado y probado en pasos 11 a 14)
- [x] Photograph import (paso 14, `1a7ab2e`)
- [x] Photograph viewer (paso 14, `1a7ab2e`)
- [x] Photograph reorder (paso 14, `1a7ab2e`)
- [x] Tests for HTML round-trip and photograph import (pasos 10 a 14; 226 pruebas)
- [x] README updated (pasos 12 a 14, `76fe7a9` y `1a7ab2e`)
- [x] Git commit created (`1a7ab2e`)

## Phase 3

Create:

- Budgets.
- Payments.
- Calculations.
- PDF.
- Printing.
- Reception receipt.
- Technical report.

### Checklist Phase 3

- [x] Line items model and UI (bloques 1 y 2)
- [x] Totals calculation service (bloque 1)
- [x] Payment registration (Fase 1; diálogo propio desde el bloque 2)
- [x] Balance update (Fase 1; cubierto por la suite)
- [ ] PDF library integrated
- [ ] Reception receipt
- [ ] Technical report
- [ ] Budget PDF
- [ ] Delivery receipt PDF
- [ ] Print preview and print dialog
- [ ] Tests for PDF generation and totals
- [ ] README updated
- [ ] Git commit created

## Phase 4

Create:

- Reports.
- Backups.
- Settings.
- Themes.
- Translations.
- Packaging.

### Checklist Phase 4

- [ ] Reports section
- [ ] CSV export
- [ ] Backup and restore
- [ ] Automatic backups
- [ ] Settings window
- [ ] Light and dark themes
- [ ] Spanish and English translations
- [ ] `.deb` package
- [ ] AppImage
- [ ] Windows executable
- [ ] README updated
- [ ] Git commit created

After each phase:

1. Run the application.
2. Fix errors.
3. Run the tests.
4. Update the README.
5. Make a descriptive Git commit.

---

# 27. Definition of Done

A task is Done only when **all** of the following are true:

- The requirement is fully implemented (not partially).
- The code runs without unhandled exceptions.
- The related UI is reachable and usable from the main window.
- Automated tests cover the new functionality (unit and/or integration).
- Tests pass locally.
- No sensitive data is written to logs.
- The README is updated if user-facing behavior changed.
- The corresponding checkbox in this document is marked `[x]`.
- A Git commit exists with a clear message.

If any of these is missing, the task must remain `[~]`, not `[x]`.

---

# 28. Working style

Before writing code:

1. Analyze all requirements.
2. Propose the final architecture.
3. Present the database model.
4. List the screens.
5. Identify technical risks.
6. Split the work into small tasks.

Then start with Phase 1.

Do not generate empty files without purpose.

Do not use pseudocode when functional code can be implemented.

Each module must include:

- Data types.
- Docstrings.
- Error handling.
- Clear names.
- Separation of responsibilities.

Use:

```python
from __future__ import annotations
```

Add type annotations.

Avoid overly long functions and classes with too many responsibilities.

---

# 29. Expected initial result

In the first functional implementation it must be possible to:

1. Open the program.
2. Create or select a customer.
3. Register equipment.
4. Create an intake order.
5. Add the reported problem.
6. Add photographs.
7. Save the order.
8. Query it from the list.
9. Write a rich diagnosis.
10. Change the state.
11. Consult the history.
12. Generate a reception receipt in PDF.
13. Print it.
14. Close and reopen the program without losing data.

Begin by showing:

- The proposed architecture.
- The database schema.
- The technical decisions.
- The implementation plan.

Then create the files for Phase 1 and provide exact instructions to install and run the project.

---

# 30. Master phase checklist (summary)

## Phase 1 — Runnable core

- [x] Structure
- [x] Database
- [x] Models
- [x] Repositories
- [x] Main window
- [x] Home panel
- [x] Customer form
- [x] Equipment form
- [x] Reception form
- [x] Order list
- [x] Basic order view
- [x] Cédula validation (módulo 10)
- [x] Order number generation
- [x] State history
- [x] Tests
- [x] README
- [ ] Commit

## Phase 2 — Diagnosis and documentation

- [x] Rich text editor
- [x] Three editors integrated
- [x] Predefined texts
- [x] State changes with history
- [x] Photographs
- [x] Tests
- [x] README
- [x] Commit

## Phase 3 — Budget, payments, PDF, printing

- [x] Line items
- [x] Payments
- [x] Totals and balance
- [ ] PDF generation
- [ ] All PDF types
- [ ] Print preview and print
- [ ] Tests
- [ ] README
- [ ] Commit

## Phase 4 — Reports, backups, settings, packaging

- [ ] Reports
- [ ] CSV export
- [ ] Backups
- [ ] Restore
- [ ] Settings
- [ ] Themes
- [ ] Translations
- [ ] Packaging (`.deb`, AppImage, Windows)
- [ ] Tests
- [ ] README
- [ ] Commit
