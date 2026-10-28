"""Tamaño de las ventanas de vista previa de impresión (§13.3).

`QPrintPreviewDialog` se abre con el tamaño que le parece a Qt, que en Windows queda
pequeño: el documento se ve como una miniatura y hay que agrandar la ventana a mano para
leer los importes. Aquí se decide una sola vez con cuánto espacio se abre y se centra.
"""

from __future__ import annotations

from PyQt6.QtCore import QRect
from PyQt6.QtWidgets import QApplication, QDialog, QWidget

PREVIEW_RATIO = 0.9
PREVIEW_MAX_WIDTH = 1500
PREVIEW_MAX_HEIGHT = 1100
PREVIEW_MIN_WIDTH = 760
PREVIEW_MIN_HEIGHT = 620


def preview_size(available: QRect) -> tuple[int, int]:
    """Tamaño de la vista previa: el 90 % de la pantalla, con topes y un mínimo usable."""
    width = min(PREVIEW_MAX_WIDTH, int(available.width() * PREVIEW_RATIO))
    height = min(PREVIEW_MAX_HEIGHT, int(available.height() * PREVIEW_RATIO))
    return max(PREVIEW_MIN_WIDTH, width), max(PREVIEW_MIN_HEIGHT, height)


def size_preview(preview: QDialog, parent: QWidget | None = None) -> None:
    """Abre la vista previa grande y centrada en la pantalla del padre."""
    screen = (parent.screen() if parent is not None else None) or QApplication.primaryScreen()
    if screen is None:
        preview.resize(PREVIEW_MIN_WIDTH, PREVIEW_MIN_HEIGHT)
        return
    available = screen.availableGeometry()
    width, height = preview_size(available)
    preview.setMinimumSize(PREVIEW_MIN_WIDTH, PREVIEW_MIN_HEIGHT)
    preview.resize(width, height)
    preview.move(
        available.x() + max(0, (available.width() - width) // 2),
        available.y() + max(0, (available.height() - height) // 2),
    )
