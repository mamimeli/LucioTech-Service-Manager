# LucioTech Service Manager

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-41cd52.svg)](https://riverbankcomputing.com/software/pyqt/)
[![Tests](https://img.shields.io/badge/tests-322%2F322%20on%20Windows-brightgreen.svg)](#windows-test-status)
[![Status](https://img.shields.io/badge/status-Phase%203%20in%20progress-orange.svg)](ROADMAP.md)

A desktop application written in Python 3 and PyQt6 to record the intake, diagnosis, repair and delivery of electronic equipment at the technical service of **Ing. Lucio**.

The application works fully offline and does not send data to any external server.

> **Status:** Phase 1 (runnable core) and Phase 2 (diagnosis, predefined texts and photographs) are closed. Phase 3 is in progress: budget line items, the **Presupuesto y pagos** tab, the printable **reception receipt**, the trash with restore and the terms and conditions are implemented; the remaining PDF document types (technical report, budget, delivery receipt and full history) are still pending. See [`ROADMAP.md`](ROADMAP.md) for details.

> **Language note:** the application's user interface is in Spanish, because it is made for a Spanish-speaking service technician. This README is in English for developers. Translations of the interface are planned for Phase 4.

## Contents

- [Requirements](#requirements)
- [Installation on Windows](#installation-on-windows)
- [Running the application](#running-the-application)
- [Trying the interface](#trying-the-interface)
- [Reception receipt and terms and conditions](#reception-receipt-and-terms-and-conditions)
- [Testing](#testing)
- [Project structure](#project-structure)
- [Data location](#data-location)
- [Password storage policy](#password-storage-policy)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Requirements

- Windows 10 or 11 (64-bit) is supported. The code branches on the platform and stores its data under `%APPDATA%` / `%LOCALAPPDATA%` on Windows.
- Linux (Debian, Ubuntu, MX Linux or a derivative) is the primary target platform.
- Python 3.11 or newer (64-bit). On Windows, Python 3.12 or 3.13 is recommended.
- No additional system packages are needed on Windows: PyQt6 ships its own Qt runtime through the `PyQt6-Qt6` wheel.

### Install Python on Windows

1. Download the installer from <https://www.python.org/downloads/windows/>.
2. During setup, tick **Add python.exe to PATH** and **Install the py launcher**.
3. Verify it in a terminal:

   ```bat
   py -3.13 --version
   ```

   You should see something like `Python 3.13.x`. If `py` is not found, reinstall Python with the launcher option enabled.

## Installation on Windows

The commands below work in **PowerShell**, **cmd.exe** and **Git Bash**. Run them from the project folder.

1. Create the virtual environment (the `.venv` folder is created inside the project):

   ```bat
   py -3.13 -m venv .venv
   ```

2. Activate it. Pick the command for your shell:

   ```bat
   :: PowerShell
   .\.venv\Scripts\Activate.ps1

   :: cmd.exe
   .venv\Scripts\activate.bat

   :: Git Bash
   source .venv/Scripts/activate
   ```

   After activation the prompt shows `(.venv)`.

   > **PowerShell note:** if activation fails with "running scripts is disabled on this system", allow scripts for the current user once:
   >
   > ```powershell
   > Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
   > ```
   >
   > Alternatively, skip activation entirely and call the interpreter by its path: `.venv\Scripts\python.exe -m pip ...`.

3. Install the dependencies:

   ```bat
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

   `PyQt6` is around 75 MB, so this step may take a few minutes.

4. Install the package itself (creates the `luciotech-service-manager` command):

   ```bat
   python -m pip install -e .
   ```

## Running the application

With the virtual environment activated, from the project folder:

```bat
python -m luciotech.main
```

## To run without installing the package

To run without installing the package, set the source path for the current command:

```bat
:: PowerShell
$env:PYTHONPATH = "src"; python -m luciotech.main

:: cmd.exe
set PYTHONPATH=src && python -m luciotech.main

:: Git Bash
PYTHONPATH=src python -m luciotech.main
```

Or use the installed command directly (no activation needed):

```bat
.venv\Scripts\luciotech-service-manager.exe
```

On startup the application creates the database if it does not exist and applies the migrations.

The main window opens maximized and adapts to the screen size. If you make it smaller, the minimum size is 800×560 pixels; forms have scroll bars so every field stays reachable.

## Trying the interface

### Use a temporary database

To keep test data apart from real data, start the application with a temporary database. On Windows, use a path inside the project or a temporary folder:

```bat
:: cmd.exe
set LUCIOTECH_DATABASE_URL=sqlite:///%TEMP%\luciotech-prueba.sqlite3
set PYTHONPATH=src
python -m luciotech.main

:: PowerShell
$env:LUCIOTECH_DATABASE_URL = "sqlite:///$env:TEMP/luciotech-prueba.sqlite3"
$env:PYTHONPATH = "src"
python -m luciotech.main

:: Git Bash
LUCIOTECH_DATABASE_URL=sqlite:///$TEMP/luciotech-prueba.sqlite3 PYTHONPATH=src python -m luciotech.main
```

> **Windows path format:** use forward slashes in the URL and four slashes before an absolute path (`sqlite:///C:/ruta/base.sqlite3`). Backslashes do not work in SQLAlchemy URLs.

To start from scratch, delete that file before starting:

```bat
:: cmd.exe
del "%TEMP%\luciotech-prueba.sqlite3"

:: PowerShell
Remove-Item "$env:TEMP/luciotech-prueba.sqlite3" -ErrorAction SilentlyContinue
```

### What you can try

1. **Home:** the cards show live counts. With an empty database they show 0 or `0.00 USD`.
2. **Clients:** click **Nuevo cliente** and try:
   - leaving the name empty (it must show "Campo obligatorio");
   - a 10-digit national ID with a wrong check digit, such as `1710034066` (it must be rejected);
   - the valid ID `1710034065`;
   - a phone number with letters, such as `099ABC4567` (it must be rejected);
   - saving a second client with the same phone in another format (`099 123-4567`): the application must ask for confirmation before saving.
3. **Equipment:** click **Nuevo equipo**. If there are no clients, you are asked to register one first. The password is hidden; the **Mostrar** button reveals it.
4. **Orders:** click **Nueva recepción**:
   - choose an existing client or **Cliente nuevo** (the fields appear in the same form);
   - tick accessories, describe the reported problem and, optionally, enter a deposit;
   - check that the planned order number is `OT-AAAA-000001` before saving;
   - after saving, a small dialog offers **Imprimir comprobante** (opens the reception receipt preview), **Abrir orden** and **Cerrar**;
   - register two devices with the same serial number: the application must warn and ask for confirmation;
   - in the list, try the search box and the filters for status, priority, equipment type and outstanding balance;
   - if the client already has a device registered, the **Equipo** field lists it. Select it and its data is locked: the order uses that same device and no new one is created.
   - select a row and click **Eliminar** to send the order to the trash. The application asks for confirmation first and the order can be restored afterwards.
5. **Order details:** double-click an order in the list. The window opens at the largest size that fits comfortably on the screen (up to 92 % of it, never wider than 1180 px) and cannot be shrunk below its own content, so the totals of the **Presupuesto y pagos** tab are never cut off. It has nine tabs:
   - **Resumen (Summary):** number, status, client, equipment, dates, total, deposit and balance.
   - **Cliente (Client):** contact details, other orders of the client and total outstanding balance (cancelled orders are excluded).
   - **Equipo (Equipment):** technical data. The password is hidden; **Mostrar contraseña** reveals it.
   - **Diagnóstico**, **Reparación** and **Recomendaciones** (Phase 2): rich-text editors for the technical diagnosis, the work performed and the recommendations to the client. Texts save automatically shortly after you stop typing and also when the dialog closes, so nothing is lost if you forget to click **Guardar textos**. Write some text with bold or lists, close the window, open it again and check that the text and formatting remain. The toolbar covers the full §8 set: bold, italic, underline, strikethrough, lists, indentation, alignment (including justify), font family and size, text and background colour, clear formatting, zoom, cut, copy, paste, paste as plain text, table, image, horizontal line, find and replace, print preview, predefined texts, undo and redo.
   - **Fotografías** (Phase 2): photographs of the equipment. Use **Importar…**, **Pegar** (button or `Ctrl+V` while this tab has the focus) or drag images from the file manager; JPEG, PNG, WEBP and BMP up to 20 MB are accepted (you can try with the samples in `Ordenadores-de-ejemplo/`). Each photo is copied into the application data folder with a new UUID name, so the original file can be moved or deleted. Double-click or **Ver** opens the viewer; **Rotar izquierda/derecha** turns the stored image; **Editar…** changes the description and type; **Quitar** deletes the record and its file; **Subir/Bajar** reorder the gallery.
   - **Presupuesto y pagos** (Phase 3): the money of the order, and the only place where money is recorded. The **Presupuesto** table lists the line items (type, description, quantity, unit price and subtotal); **Añadir línea**, **Editar línea** (or double-click) and **Quitar línea** work on the selected row. The **Totales** panel recalculates as soon as anything changes: subtotal, discount, tax, deposit and payments above the line, then **Total** and **Saldo pendiente** below it in a larger type. The balance is the biggest number on the screen and turns red while money is owed, green once it reaches zero. Type a **Descuento** and press Enter or leave the field to apply it. The **Pagos** table lists every payment and refund with its state; **Registrar pago** opens a dialog (type, method, amount, reference, notes) and **Anular pago** voids the selected one, asking for a reason. Voiding is logical: the payment stays in the list and in the history marked as *Anulado*, but it stops counting towards the balance. If you record a payment of type *Anticipo* on an order that already carries a deposit from reception, the application registers it and warns you that the deposit will be subtracted twice. The tab never writes SQL or does its own arithmetic: it goes through `budget_service`, `order_detail_service` and the single totals formula in `totals_service` (§5.3).
   - **Historial (History):** status changes and notes in chronological order.
   - From the bottom of the dialog you can change the status, add a note, mark the order as delivered, save the texts on demand, open **Documentos…** (choose which document to preview, print or save as PDF) and **send the order to the trash**. Payments are **not** recorded from here: there is a single **Registrar pago** button, in the **Presupuesto y pagos** tab, so the money always goes through the same door.
6. **Papelera (Trash):** the fifth tab lists the orders that were deleted. Deleting is *logical*: the row stays in the database with `activo = False` and a deletion date, so nothing is lost. Select a row and click **Restaurar** to bring the order back to the active list; **Abrir** (or a double-click) shows its details in read-only fashion, where the delete button is disabled. The **Órdenes** list never shows deleted orders, and the trash never shows active ones.
7. **Shortcuts:** `F5` refreshes every screen and `Ctrl+Q` quits.
8. **Restart:** close the application, open it again with the same database and check that the data is still there.

### Not implemented yet

- Page numbers, header and footer, configurable margins, A4/Letter selection and descriptive file names for the exported PDFs (§13.2). All five documents are laid out for A4 and the print dialog lets you change the paper size, but the app does not name the file for you.
- `costo_repuestos` and `costo_mano_obra` are always zero and are not editable: the detailed budget is the line items of the **Presupuesto y pagos** tab. The formula still adds them, so they must stay at zero to avoid counting the same amount twice.
- Webcam capture is not implemented yet (optional feature).
- Editing the terms and conditions, the retention months and the workshop data from a Settings window is pending (Phase 4). Today those values live in the `configuracion` table and are read through `settings_service`; see [Reception receipt and terms and conditions](#reception-receipt-and-terms-and-conditions) for the keys and their defaults.
- Editing the predefined text list from a Settings window is pending (Phase 4); today the list can only be changed by code or directly in the database.
- Images inserted in the rich-text editor point to the original file on disk. Photographs in the Fotografías tab are copied into the application data folder, but editor images are not.
- Backups from the interface (Phase 4).
- Transition rules for order statuses: any status can currently be set from any other.
- The trash only restores; it never empties itself. Permanently deleting a row from the database is deliberately not offered (§18).

### If something fails

There is no log file yet (ROADMAP §20). If something fails, run the program from a terminal and copy the full error message that appears there.

## Reception receipt and terms and conditions

The reception receipt (§13.1.1) is the document you hand to the client when the equipment is dropped off. It is built as HTML in `src/luciotech/ui/documents.py` and printed through Qt's preview dialog, so it works offline and on any printer the system knows about. It contains:

- the workshop header (name, phone, e-mail and address, taken from the configuration);
- the order number and the entry date and time;
- the client, the equipment (type, brand and model, serial number, colour, operating system), the accessories received, the physical condition and the reported problem;
- the estimated delivery date and the technician in charge;
- the full money breakdown: diagnosis fee, parts, labour, budget lines, subtotal, discount, tax, total, deposit received, payments received and outstanding balance. The figures come from the same formula as the **Presupuesto y pagos** tab (§5.3), so the paper and the screen never disagree; rows that are zero are omitted, but the total and the balance are always printed. Tax is only printed when it is switched on: by default it is off, because the workshop prices already include it;
- up to four photographs of the equipment, taken from the **Fotografías** tab;
- the terms and conditions;
- signature lines for the client and for the workshop.

The equipment password is **never** printed: the document is given to the customer.

**Documentos…** in the order window opens a chooser with the five documents of §13.1. All of them open in Qt's print preview, which opens at 90 % of the available screen (capped at 1500 × 1100 px and never below 760 × 620), so the page is readable without resizing the window by hand. From that same dialog you can send the document to a printer or save it as PDF.

| Document | When you hand it over | What it contains |
|---|---|---|
| **Comprobante de recepción** | When the equipment is dropped off | Client, equipment, accessories, physical condition, photographs, amounts, terms and both signatures |
| **Presupuesto** | Before starting the work | Concept, quantity, unit price and amount per line, subtotal, discount, tax (only if switched on) and total, validity (15 days from the entry date, `presupuesto_validez_dias`) and a space for the client's approval |
| **Informe técnico** | When the work is finished | Diagnosis, work performed, parts used, recommendations, photographs before and after, amounts and warranty |
| **Comprobante de entrega** | When the equipment is returned | Order data, work performed, every payment with its state, balance, warranty, declaration of conformity and both signatures |
| **Historial completo** | On request or for the file | Every status change, note and payment in chronological order |

The **Órdenes** list keeps its own **Imprimir comprobante** action, which prints the reception receipt directly.

The terms and conditions come from the `condiciones_servicio` configuration key. The default text states that an equipment that is not collected within the retention period is considered abandoned and may be written off:

> Si el equipo no es retirado dentro de **6** meses contados desde la fecha de ingreso, se considerará abandonado y el taller podrá darlo de baja y disponer de él.

The number of months is not hardcoded in the text: the placeholder `{meses}` is replaced at print time with the value of `retencion_meses`, so changing the retention period updates every document at once. Related keys:

| Key | Default | Meaning |
|---|---|---|
| `condiciones_servicio` | `DEFAULT_SERVICE_TERMS` in `config.py` | Terms printed on the receipt. `{meses}` is substituted. |
| `retencion_meses` | `6` | Months before an uncollected equipment can be written off. Must be greater than zero; an invalid or empty value falls back to the default. |
| `nombre_taller` | `Ing. Lucio` | Workshop name in the document header. |
| `telefono_taller`, `correo_taller`, `direccion_taller` | empty | Contact line of the header. Empty parts are omitted. |

Read and write them through `luciotech.services.settings_service` (`service_terms`, `service_conditions`, `retention_months`, `set_service_terms`, `set_retention_months`, `workshop_name`, `workshop_contact`), never by hand, because those helpers normalise the values and validate the retention period. A Settings screen for these fields is planned for Phase 4.

## Testing

With the virtual environment activated, from the project folder:

```bat
python -m pytest
```

The suite uses a temporary SQLite database for each test and runs the Qt interface offscreen, so it does not open windows. Interface tests use `pytest-qt`.

### Windows test status

Verified on Windows 11 with Python 3.13.15 and PyQt6 6.9.0: **322 of 322 tests pass** (about 4 minutes).

Previously one test failed on Windows only: `tests/test_rich_text_editor.py::test_toolbar_rows_are_compact_and_only_grow_when_scrolling_is_needed`. The cause was not a product bug but a platform-dependent assumption in the test. The test resized the rich-text editor to a fixed 900 px and expected both toolbar rows to fit without horizontal scrolling. On Windows the toolbar font metrics are wider, so the action row needs **976 px** and legitimately scrolls at 900 px — its height (47 px, toolbar plus scrollbar) was therefore correct, and only the format row (657 px) returned to the compact 33 px. On Linux the same row is narrower than 900 px, so the assumption held.

Two changes were made:

- The test now derives the widths from each row itself (`max(minimumWidth) + 8` for the wide case, half of the narrowest row for the narrow case) instead of hardcoding 900 px, so it no longer depends on platform font metrics.
- `_ToolbarArea` now recomputes its fixed height from the **real** scrollbar visibility (`horizontalScrollBar().isVisible()`) both on `resizeEvent` and on the scrollbar's `Show`/`Hide` events. Previously the height depended only on `Show`/`Hide`, so a missed `Hide` event would have left the row 14 px too tall; with the width as a second trigger the height always matches what is on screen.

The compact height (33 px) and the expanded height (47 px) are unchanged; the fix only removes the stale-height risk and makes the test platform-independent.

One harmless detail while the suite runs: pytest prints `Windows fatal exception: code 0x80040155` followed by a stack trace that ends in `render_to_pdf`. It comes from `QPrinter` being constructed under the offscreen platform, where there is no real print subsystem. It is a first-chance exception that Qt handles internally: the affected test (`test_render_to_pdf_creates_a_pdf`) still passes and the PDF is written correctly. The summary line (`322 passed`) is the one that counts.

If pytest stops with a permission error while removing an old folder under the system temp directory, pass a fresh base directory so it has nothing to clean up:

```bat
python -m pytest --basetemp="%TEMP%\luciotech-pytest-%RANDOM%"
```

Useful flags while developing:

```bat
:: stop at the first failure and show the exception
python -m pytest -x

:: run only the interface tests
python -m pytest tests/test_ui.py tests/test_reception_ui.py

:: a single test
python -m pytest "tests/test_rich_text_editor.py::test_toolbar_has_the_essential_actions"
```

## Project structure

```text
.
├── pyproject.toml
├── requirements.txt
├── README.md
├── ROADMAP.md
├── AGENTS.md
├── LICENSE
├── alembic.ini
├── src/
│   └── luciotech/
│       ├── main.py               # Entry point: migrations, then main window
│       ├── config.py             # Name, app_id, organization, version, defaults
│       ├── database/
│       │   ├── connection.py     # SQLite engine with foreign keys enabled
│       │   ├── enums.py          # Statuses, priorities and types (defined once)
│       │   ├── models.py         # SQLAlchemy models
│       │   ├── repositories.py   # CRUD per entity (flush only, no commit)
│       │   ├── migrate.py        # Applies Alembic migrations at startup
│       │   └── migrations/       # Alembic revisions
│       ├── services/             # Business rules; receive a session, never commit
│       ├── ui/
│       │   ├── main_window.py    # Main window with tabs
│       │   ├── documents.py      # Printable reception receipt (§13.1.1) and print preview
│       │   ├── pages/            # Home, orders, clients, equipment and trash pages
│       │   └── dialogs/          # Forms and order details
│       └── utils/
│           ├── paths.py          # Data and log paths (XDG on Linux, %APPDATA% on Windows)
│           └── validators.py     # Ecuadorian national ID (modulus 10), phone, email
└── tests/                        # pytest and pytest-qt
```

## Data location

The application stores everything locally. Paths are chosen per operating system.

On Windows:

| Content | Path |
|---|---|
| SQLite database | `%APPDATA%\luciotech-service-manager\database.sqlite3` |
| Photographs | `%APPDATA%\luciotech-service-manager\attachments\` |
| Logs (planned) | `%LOCALAPPDATA%\luciotech-service-manager\logs\` |

On Linux the application uses XDG paths:

| Content | Path |
|---|---|
| SQLite database | `~/.local/share/luciotech-service-manager/database.sqlite3` |
| Photographs | `~/.local/share/luciotech-service-manager/attachments/` |
| Logs (planned) | `~/.local/state/luciotech-service-manager/logs/` |

If you set `XDG_DATA_HOME` or `XDG_STATE_HOME`, the Linux paths change accordingly. On Windows you can open the data folder quickly by pasting `%APPDATA%\luciotech-service-manager` into the Explorer address bar.

## Password storage policy

Equipment passwords and PINs are stored **in plain text** in the local SQLite database. The system has no server, so protection depends on the file-system permissions. Therefore:

- do not share the data folder;
- protect your user account with a strong password;
- passwords are never written to logs.

## Troubleshooting

### Windows

- **`py` is not recognized**: Python's launcher is not installed or not on `PATH`. Reinstall Python from python.org with **Add python.exe to PATH** and **Install the py launcher** ticked.
- **`python` opens the Microsoft Store**: the Windows "App execution alias" is intercepting the command. Turn off *App Installer* / *python.exe* aliases in **Settings → Apps → Advanced app settings → App execution aliases**, or use `py` instead of `python`.
- **`Activate.ps1 cannot be loaded because running scripts is disabled`**: see the PowerShell note in [Installation on Windows](#installation-on-windows), or skip activation and call `.venv\Scripts\python.exe` directly.
- **`ModuleNotFoundError: No module named 'luciotech'`**: run `python -m pip install -e .` inside the activated `.venv`, or set `PYTHONPATH=src` for the current command.
- **`ModuleNotFoundError` for another module**: the virtual environment is not active. Check that the prompt shows `(.venv)`, or call `.venv\Scripts\python.exe` explicitly.
- **The window does not appear / Qt plugin error**: make sure you are not setting `QT_QPA_PLATFORM=offscreen`. That variable is only for automated tests and suppresses the window.
- **Photos or the database "disappear" after moving the project**: they are not stored in the project folder; on Windows they live in `%APPDATA%\luciotech-service-manager`.
- **Path with spaces or accents fails to run**: wrap the path in double quotes, e.g. `cd "C:\Mis Documentos\LucioTech-Service-Manager"`.

### Linux

- **`source: no such file`**: the `source` command must be on its own line or joined with `&&` on the same line. Type the commands exactly as shown above.
- **`ModuleNotFoundError: No module named 'luciotech'`**: the package is not installed. Run `pip install -e .` with the virtual environment activated, or use `PYTHONPATH=src` as shown above.
- **`ModuleNotFoundError` for another module**: check that the virtual environment is active; the prompt must show `(.venv)`.
- **No window appears in a remote or headless session**: run with `QT_QPA_PLATFORM=offscreen` only for automated tests; no window is shown.

## License

GNU General Public License v3.0. See [`LICENSE`](LICENSE).
