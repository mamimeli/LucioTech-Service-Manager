"""Traducción al español de los diálogos que pone Qt (§21).

La interfaz de la aplicación ya está en español, pero Qt trae sus propios textos en inglés:
la barra de la vista previa de impresión («Print», «Fit width», «Page setup»), la
configuración de página, los botones de los avisos («Yes»/«No») y los diálogos de archivo.
Los archivos `.qm` viajan con PyQt6, así que se cargan al arrancar. Si no estuvieran, la
aplicación sigue funcionando con esos textos en inglés: nunca se rompe por esto.
"""

from __future__ import annotations

from PyQt6.QtCore import QLibraryInfo, QTranslator
from PyQt6.QtWidgets import QApplication

TRANSLATION_FILES = ("qtbase_es", "qt_es")


def install_spanish_translations(app: QApplication) -> list[QTranslator]:
    """Carga las traducciones de Qt y devuelve las que se instalaron.

    La lista se devuelve para poder retirarlas (lo hacen las pruebas); en la aplicación se
    quedan puestas toda la sesión.
    """
    folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    installed: list[QTranslator] = []
    for name in TRANSLATION_FILES:
        translator = QTranslator(app)
        if translator.load(name, folder):
            app.installTranslator(translator)
            installed.append(translator)
    return installed
