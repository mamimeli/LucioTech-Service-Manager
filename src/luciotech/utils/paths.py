"""Rutas de datos, estado y registros según el sistema operativo (§5 y §20)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from luciotech.config import APP_CONFIG


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def data_dir() -> Path:
    """Directorio de datos: base de datos, adjuntos y logo.

    Linux: $XDG_DATA_HOME/<app_id> (por defecto ~/.local/share/<app_id>).
    Windows: %APPDATA%/<app_id>.
    """
    if _is_windows():
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_CONFIG.app_id


def state_dir() -> Path:
    """Directorio de estado: registros (logs).

    Linux: $XDG_STATE_HOME/<app_id> (por defecto ~/.local/state/<app_id>).
    Windows: %LOCALAPPDATA%/<app_id>.
    """
    if _is_windows():
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / APP_CONFIG.app_id


def database_path() -> Path:
    """Ruta por defecto del archivo SQLite."""
    return data_dir() / "database.sqlite3"


def attachments_dir() -> Path:
    """Carpeta base de adjuntos; cada orden usa una subcarpeta con su número."""
    return data_dir() / "attachments"


def log_dir() -> Path:
    """Carpeta de registros de la aplicación."""
    return state_dir() / "logs"
