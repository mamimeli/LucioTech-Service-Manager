# LucioTech Service Manager

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-41cd52.svg)](https://riverbankcomputing.com/software/pyqt/)
[![Tests](https://img.shields.io/badge/tests-172%20passing-brightgreen.svg)](#testing)
[![Status](https://img.shields.io/badge/status-Phase%202%20in%20progress-orange.svg)](ROADMAP.md)

A desktop application written in Python 3 and PyQt6 to record the intake, diagnosis, repair and delivery of electronic equipment at the technical service of **Ing. Lucio**.

The application works fully offline and does not send data to any external server.

> **Status:** Phase 1 (runnable core) is closed. Phase 2 is in progress: order details now include diagnosis, repair and recommendation tabs with a basic rich-text editor. Photographs, PDF documents and quotes are not implemented yet. See [`ROADMAP.md`](ROADMAP.md) for details.

> **Language note:** the application's user interface is in Spanish, because it is made for a Spanish-speaking service technician. This README is in English for developers. Translations of the interface are planned for Phase 4.

## Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Running the application](#running-the-application)
- [Trying the interface](#trying-the-interface)
- [Testing](#testing)
- [Project structure](#project-structure)
- [Data location](#data-location)
- [Password storage policy](#password-storage-policy)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Requirements

- Debian, Ubuntu, MX Linux or a derivative distribution. Windows is planned but not yet tested.
- Python 3.11 or newer.
- System packages required by PyQt6 on Linux, if your distribution does not provide them. See the PyQt6 documentation.

## Installation

Run these commands from the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the application

With the virtual environment activated, from the project folder:

```bash
pip install -e .
python -m luciotech.main
```

To run without installing the package:

```bash
PYTHONPATH=src python -m luciotech.main
```

On startup the application creates the database if it does not exist and applies the migrations.

The main window opens maximized and adapts to the screen size. If you make it smaller, the minimum size is 800×560 pixels; forms have scroll bars so every field stays reachable.

## Trying the interface

### Use a temporary database

To keep test data apart from real data, start the application with a temporary database:

```bash
LUCIOTECH_DATABASE_URL=sqlite:////tmp/luciotech-prueba.sqlite3 PYTHONPATH=src python -m luciotech.main
```

To start from scratch, delete that file before starting:

```bash
rm -f /tmp/luciotech-prueba.sqlite3
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
   - register two devices with the same serial number: the application must warn and ask for confirmation;
   - in the list, try the search box and the filters for status, priority, equipment type and outstanding balance;
   - if the client already has a device registered, the **Equipo** field lists it. Select it and its data is locked: the order uses that same device and no new one is created.
5. **Order details:** double-click an order in the list. It has four tabs:
   - **Resumen (Summary):** number, status, client, equipment, dates, total, deposit and balance.
   - **Cliente (Client):** contact details, other orders of the client and total outstanding balance (cancelled orders are excluded).
   - **Equipo (Equipment):** technical data. The password is hidden; **Mostrar contraseña** reveals it.
   - **Historial (History):** status changes and notes in chronological order.
   - **Diagnóstico** and **Reparación** (Phase 2): rich-text editors for the technical diagnosis, the recommendations to the client, and the work performed. Write some text with bold or lists, click **Guardar textos**, close the window, open it again and check that the text and formatting remain. The editor has a basic toolbar: bold, italic, underline, lists, alignment, undo and redo.
   - From the bottom of the dialog you can change the status, record a payment or refund, add a note, and mark the order as delivered (this asks for confirmation).
6. **Shortcuts:** `F5` refreshes every screen and `Ctrl+Q` quits.
7. **Restart:** close the application, open it again with the same database and check that the data is still there.

### Not implemented yet

- Attaching photographs (Phase 2) and generating PDF documents (Phase 3).
- Quotes with line items (Phase 3).
- The rich-text editor has only the basic toolbar; the full toolbar and predefined texts are pending (Phase 2).
- Backups from the interface (Phase 4).
- Transition rules for order statuses: any status can currently be set from any other.

### If something fails

There is no log file yet (ROADMAP §20). If something fails, run the program from a terminal and copy the full error message that appears there.

## Testing

With the virtual environment activated, from the project folder:

```bash
pytest
```

The suite uses a temporary SQLite database for each test and runs the Qt interface offscreen, so it does not open windows. Interface tests use `pytest-qt`.

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
│       │   ├── pages/            # Home, orders, clients and equipment pages
│       │   └── dialogs/          # Forms and order details
│       └── utils/
│           ├── paths.py          # XDG data and log paths
│           └── validators.py     # Ecuadorian national ID (modulus 10), phone, email
└── tests/                        # pytest and pytest-qt
```

## Data location

On Linux the application uses XDG paths:

| Content | Path |
|---|---|
| SQLite database | `~/.local/share/luciotech-service-manager/database.sqlite3` |
| Photographs (planned) | `~/.local/share/luciotech-service-manager/attachments/` |
| Logs (planned) | `~/.local/state/luciotech-service-manager/logs/` |

If you set `XDG_DATA_HOME` or `XDG_STATE_HOME`, the paths change accordingly.

## Password storage policy

Equipment passwords and PINs are stored **in plain text** in the local SQLite database. The system has no server, so protection depends on the file-system permissions. Therefore:

- do not share the data folder;
- protect your user account with a strong password;
- passwords are never written to logs.

## Troubleshooting

- **`source: no such file`**: the `source` command must be on its own line or joined with `&&` on the same line. Type the commands exactly as shown above.
- **`ModuleNotFoundError: No module named 'luciotech'`**: the package is not installed. Run `pip install -e .` with the virtual environment activated, or use `PYTHONPATH=src` as shown above.
- **`ModuleNotFoundError` for another module**: check that the virtual environment is active; the prompt must show `(.venv)`.
- **No window appears in a remote or headless session**: run with `QT_QPA_PLATFORM=offscreen` only for automated tests; no window is shown.

## License

GNU General Public License v3.0. See [`LICENSE`](LICENSE).
