"""Soporte de impresión de los documentos (§13.2 y §13.3).

Dos responsabilidades:

1. **Tamaño de la vista previa.** `QPrintPreviewDialog` se abre con el tamaño que le parece a
   Qt, que en Windows queda pequeño: el documento se ve como una miniatura y hay que agrandar
   la ventana a mano para leer los importes. Aquí se decide una sola vez con cuánto espacio se
   abre y se centra.
2. **Mobiliario de página.** `QTextDocument` pagina solo, pero no numera las páginas ni repite
   encabezado y pie. Aquí se reserva una banda arriba y otra abajo, se dibuja el texto del
   documento entre ambas y se escribe el encabezado, el pie y «Página X de Y» en cada hoja.
   También se guarda el resultado en PDF con un nombre descriptivo (§13.2).
3. **Espaciados.** Qt escala las fuentes en puntos pero descarta los márgenes y rellenos con
   unidad física, así que las plantillas se pasan a píxeles antes de cargarlas (`scale_lengths`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import (
    QCoreApplication,
    QMarginsF,
    QPointF,
    QRect,
    QRectF,
    QSizeF,
    QStandardPaths,
    Qt,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QPageLayout,
    QPageSize,
    QPainter,
    QPen,
    QTextDocument,
)
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox, QToolBar, QWidget

from luciotech.config import DEFAULT_PAGE_MARGIN_MM, DEFAULT_PAPER_SIZE

PREVIEW_RATIO = 0.9
PREVIEW_MAX_WIDTH = 1500
PREVIEW_MAX_HEIGHT = 1100
PREVIEW_MIN_WIDTH = 760
PREVIEW_MIN_HEIGHT = 620

# Tamaños de hoja que entiende la aplicación. La clave es el valor guardado en configuración.
PAGE_SIZE_IDS: dict[str, QPageSize.PageSizeId] = {
    "A4": QPageSize.PageSizeId.A4,
    "Carta": QPageSize.PageSizeId.Letter,
}
_CONTEXT = "LucioTech"
FURNITURE_POINT_SIZE = 7
FURNITURE_COLOR = "#333333"
RULE_COLOR = "#AAAAAA"
PDF_FILTER = "Documento PDF (*.pdf)"
# Qt mide los px del HTML como píxeles CSS: 1 pt son 96/72 px, sin importar la impresora.
POINTS_TO_PIXELS = 96 / 72
# Márgenes y rellenos con unidad física; Qt los deja en cero si no se pasan a píxeles.
_LENGTH_PATTERN = re.compile(r"(margin(?:-[a-z]+)?|padding(?:-[a-z]+)?)\s*:\s*([^;\"]+)")
_PDF_SUFFIX = ".pdf"


@dataclass(frozen=True)
class PageFurniture:
    """Textos que se repiten en cada hoja (§13.2).

    El número de página no se guarda aquí: lo pone `render_document`, que es quien sabe
    cuántas hojas salieron.
    """

    header_left: str = ""
    header_right: str = ""
    footer_left: str = ""


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


def page_size_id(paper: str) -> QPageSize.PageSizeId:
    """Hoja para «A4» o «Carta»; si el valor no se reconoce, A4."""
    return PAGE_SIZE_IDS.get(paper.strip().title(), QPageSize.PageSizeId.A4)


def apply_page_setup(
    printer: QPrinter, paper: str = DEFAULT_PAPER_SIZE, margin_mm: int = DEFAULT_PAGE_MARGIN_MM
) -> None:
    """Fija la hoja, la orientación y los márgenes antes de abrir la vista previa (§13.2)."""
    printer.setPageLayout(
        QPageLayout(
            QPageSize(page_size_id(paper)),
            QPageLayout.Orientation.Portrait,
            QMarginsF(margin_mm, margin_mm, margin_mm, margin_mm),
            QPageLayout.Unit.Millimeter,
        )
    )


def build_document(html: str, printer: QPrinter) -> QTextDocument:
    """Documento listo para imprimir en ese dispositivo.

    El dispositivo se fija antes de cargar el HTML porque de él depende el tamaño real de la
    letra; los márgenes y rellenos se convierten aparte (ver `scale_lengths`).
    """
    document = QTextDocument()
    document.documentLayout().setPaintDevice(printer)
    document.setHtml(scale_lengths(html))
    return document


def scale_lengths(html: str) -> str:
    """Pasa a píxeles CSS los márgenes y rellenos expresados en puntos.

    Qt escala solo las fuentes: un `font-size: 10pt` sale del tamaño correcto en cualquier
    impresora, pero las unidades físicas de `margin` y `padding` las deja en cero. Con las
    plantillas en puntos, todas las secciones salían pegadas y las celdas sin aire. Qt mide
    los `px` del HTML como píxeles CSS de 96 ppp, de modo que la conversión es la de siempre
    (1 pt = 96/72 px) y no depende de la impresora.
    """
    def convert(property_name: str, value: str) -> str:
        parts = []
        for token in value.split():
            if token.endswith("pt"):
                try:
                    parts.append(f"{float(token[:-2]) * POINTS_TO_PIXELS:.2f}px")
                    continue
                except ValueError:
                    pass
            parts.append(token)
        return f"{property_name}: {' '.join(parts)}"

    return _LENGTH_PATTERN.sub(lambda match: convert(match.group(1), match.group(2)), html)


def render_document(
    printer: QPrinter,
    html: str,
    furniture: PageFurniture | None = None,
) -> None:
    """Imprime el documento en tantas hojas como haga falta, con encabezado, pie y numeración.

    Qt pagina el `QTextDocument` y no deja tocar el espacio entre páginas, así que se le da una
    altura de hoja menor que la imprimible (la que queda entre las dos bandas) y se desplaza el
    contenido para que caiga debajo del encabezado. Así el texto nunca se monta sobre el pie.
    """
    furniture = furniture or PageFurniture()
    printable = printer.pageRect(QPrinter.Unit.DevicePixel)
    width, height = printable.width(), printable.height()
    document = build_document(html, printer)
    if width <= 0 or height <= 0:
        document.print(printer)
        return

    font, metrics = _furniture_metrics(printer)
    band = metrics.height() * 2
    body = height - band * 2
    if body <= metrics.height():
        document.print(printer)
        return

    document.setPageSize(QSizeF(width, body))
    pages = max(1, document.pageCount())

    painter = QPainter(printer)
    if not painter.isActive():
        return
    try:
        for index in range(pages):
            if index:
                printer.newPage()
            painter.save()
            painter.translate(0, band - index * body)
            document.drawContents(painter, QRectF(0, index * body, width, body))
            painter.restore()
            _draw_furniture(
                painter, furniture, font, metrics, index + 1, pages, width, height, band
            )
    finally:
        painter.end()


def save_as_pdf(
    source: QPrinter,
    html: str,
    furniture: PageFurniture | None,
    path: str | Path,
) -> bool:
    """Escribe el documento en PDF con la hoja y los márgenes que tiene la vista previa."""
    target = Path(path)
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(target))
    printer.setPageLayout(source.pageLayout())
    render_document(printer, html, furniture)
    return target.exists() and target.stat().st_size > 0


def add_pdf_action(
    preview: QDialog,
    printer: QPrinter,
    html: str,
    furniture: PageFurniture | None,
    suggested_name: str,
) -> None:
    """Añade «Guardar como PDF» a la barra de herramientas de la vista previa (§13.2)."""
    # Las pruebas sustituyen el diálogo por un doble sin jerarquía de widgets: sin barra no
    # hay botón, pero la vista previa sigue abriéndose.
    if not hasattr(preview, "findChildren"):
        return
    toolbars = preview.findChildren(QToolBar)
    if not toolbars:
        return
    action = toolbars[0].addAction(_tr("Guardar como PDF"))
    action.setToolTip(_tr("Guardar el documento en un archivo PDF"))
    action.triggered.connect(
        lambda _checked=False: _save_pdf_dialog(
            preview, printer, html, furniture, suggested_name
        )
    )


def ask_pdf_path(parent: QWidget | None, suggested_name: str) -> Path | None:
    """Pregunta dónde guardar el PDF y devuelve la ruta con extensión .pdf."""
    folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    start = Path(folder) / suggested_name if folder else Path.home() / suggested_name
    chosen, _filter = QFileDialog.getSaveFileName(
        parent, _tr("Guardar como PDF"), str(start), PDF_FILTER
    )
    if not chosen:
        return None
    target = Path(chosen)
    return target if target.suffix.lower() == _PDF_SUFFIX else target.with_suffix(_PDF_SUFFIX)


def _save_pdf_dialog(
    preview: QDialog,
    printer: QPrinter,
    html: str,
    furniture: PageFurniture | None,
    suggested_name: str,
) -> None:
    target = ask_pdf_path(preview, suggested_name)
    if target is None:
        return
    if save_as_pdf(printer, html, furniture, target):
        QMessageBox.information(
            preview,
            _tr("Guardar como PDF"),
            _tr("El documento se guardó en:\n{0}").format(str(target)),
        )
        return
    QMessageBox.warning(
        preview,
        _tr("Guardar como PDF"),
        _tr("No se pudo escribir el archivo PDF."),
    )


def _furniture_metrics(printer: QPrinter) -> tuple[QFont, QFontMetricsF]:
    """Fuente y medidas del encabezado y el pie, en píxeles del dispositivo de impresión."""
    font = QFont()
    font.setPointSize(FURNITURE_POINT_SIZE)
    return font, QFontMetricsF(font, printer)


def _draw_furniture(
    painter: QPainter,
    furniture: PageFurniture,
    font: QFont,
    metrics: QFontMetricsF,
    page: int,
    pages: int,
    width: int,
    height: int,
    band: float,
) -> None:
    """Encabezado (con línea separadora), pie y «Página X de Y» de una hoja."""
    line = metrics.height()
    painter.setFont(font)
    painter.setPen(QPen(QColor(FURNITURE_COLOR)))

    top = QRectF(0, 0, width, line)
    if furniture.header_left:
        painter.drawText(
            top, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, furniture.header_left
        )
    if furniture.header_right:
        painter.drawText(
            top,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            furniture.header_right,
        )
    rule = band - line / 2
    painter.setPen(QPen(QColor(RULE_COLOR), max(1.0, line / 24)))
    painter.drawLine(QPointF(0, rule), QPointF(width, rule))

    bottom = QRectF(0, height - line, width, line)
    painter.setPen(QPen(QColor(FURNITURE_COLOR)))
    if furniture.footer_left:
        painter.drawText(
            bottom,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            furniture.footer_left,
        )
    painter.drawText(
        bottom,
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        f"Página {page} de {pages}",
    )


def _tr(text: str) -> str:
    """Traduce un texto de este módulo sin repetir el contexto en cada llamada."""
    return QCoreApplication.translate(_CONTEXT, text)
