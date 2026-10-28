"""Configuración común de pruebas: base SQLite temporal y Qt sin pantalla."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from sqlalchemy import Engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from luciotech.database.connection import create_db_engine, create_session_factory  # noqa: E402
from luciotech.database.models import Base  # noqa: E402
from luciotech.services.settings_service import (  # noqa: E402
    KEY_TAX_ENABLED,
    set_value,
)


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    db_engine = create_db_engine(f"sqlite:///{tmp_path / 'test.sqlite3'}")
    Base.metadata.create_all(db_engine)
    yield db_engine
    db_engine.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)


@pytest.fixture
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Sesión abierta sobre la base temporal; se cierra al terminar la prueba."""
    with session_factory() as db_session:
        yield db_session


@pytest.fixture
def tax_enabled(session_factory: sessionmaker[Session]) -> None:
    """Activa el IVA del 15 % antes de crear la orden.

    El impuesto nace desactivado (`config.DEFAULT_TAX_ENABLED`), así que las pruebas que
    comprueban importes con IVA lo encienden a propósito. Debe pedirse antes que la orden.
    """
    with session_factory() as db_session:
        set_value(db_session, KEY_TAX_ENABLED, "true")
        db_session.commit()
