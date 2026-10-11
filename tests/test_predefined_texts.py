"""Pruebas de los textos predefinidos: valores por defecto, guardado y validación."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session, sessionmaker

from luciotech.config import DEFAULT_PREDEFINED_TEXTS
from luciotech.services.predefined_text_service import (
    predefined_texts,
    save_predefined_texts,
)


def test_defaults_come_from_the_specification(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        assert predefined_texts(session) == list(DEFAULT_PREDEFINED_TEXTS)
    assert len(DEFAULT_PREDEFINED_TEXTS) == 7
    assert DEFAULT_PREDEFINED_TEXTS[0] == "Se realizó inspección visual del equipo."


def test_custom_list_is_saved_and_reloaded(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        save_predefined_texts(session, ["Cambio de pasta térmica.", "Limpieza interna."])
        session.commit()
    with session_factory() as session:
        assert predefined_texts(session) == ["Cambio de pasta térmica.", "Limpieza interna."]


def test_empty_lines_and_extra_spaces_are_cleaned(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        save_predefined_texts(session, ["  Uno   dos  ", "", "   ", "Tres"])
        session.commit()
        assert predefined_texts(session) == ["Uno dos", "Tres"]


def test_line_breaks_inside_a_text_are_not_kept(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        save_predefined_texts(session, ["Primera\nsegunda"])
        session.commit()
        assert predefined_texts(session) == ["Primera segunda"]


def test_list_cannot_be_emptied(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        with pytest.raises(ValueError):
            save_predefined_texts(session, ["  ", ""])
