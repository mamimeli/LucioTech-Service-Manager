"""Pruebas de las traducciones de Qt al español (§21)."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QApplication

from luciotech.ui.translations import install_spanish_translations


def test_the_print_preview_and_the_page_setup_speak_spanish(qapp: QApplication) -> None:
    translators = install_spanish_translations(qapp)
    if not translators:
        pytest.skip("PyQt6 no trae los archivos .qm en este entorno")
    try:
        assert QCoreApplication.translate("QPrintPreviewDialog", "Print") == "Imprimir"
        assert (
            QCoreApplication.translate("QPrintPreviewDialog", "Page setup")
            == "Configuración de página"
        )
        assert QCoreApplication.translate("QPlatformTheme", "&Yes") == "&Sí"
    finally:
        for translator in translators:
            qapp.removeTranslator(translator)


def test_without_the_translations_qt_keeps_its_own_text(qapp: QApplication) -> None:
    assert QCoreApplication.translate("QPrintPreviewDialog", "Print") == "Print"
