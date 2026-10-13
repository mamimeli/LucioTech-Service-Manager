"""Pruebas de tamaño y apertura de la ventana principal (maximizada y adaptable)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from pytestqt.qtbot import QtBot
from sqlalchemy.orm import Session, sessionmaker

from luciotech.ui.main_window import MIN_HEIGHT, MIN_WIDTH, MainWindow


def test_main_window_opens_maximized(qtbot: QtBot, session_factory: sessionmaker[Session]) -> None:
    window = MainWindow(session_factory)
    qtbot.addWidget(window)
    assert window.windowState() & Qt.WindowState.WindowMaximized


def test_main_window_has_minimum_size_for_small_screens(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    window = MainWindow(session_factory)
    qtbot.addWidget(window)
    assert window.minimumWidth() == MIN_WIDTH
    assert window.minimumHeight() == MIN_HEIGHT


def test_main_window_shows_all_five_tabs(qtbot: QtBot, session_factory: sessionmaker[Session]) -> None:
    window = MainWindow(session_factory)
    qtbot.addWidget(window)
    tabs = [window._tabs.tabText(index) for index in range(window._tabs.count())]
    assert tabs == ["Inicio", "Órdenes", "Clientes", "Equipos", "Papelera"]
