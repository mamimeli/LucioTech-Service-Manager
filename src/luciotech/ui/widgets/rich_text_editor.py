"""Editor de texto enriquecido reutilizable para diagnóstico, trabajo y recomendaciones (§8).

Primera versión: negrita, cursiva, subrayado, listas, alineación, deshacer y rehacer.
El contenido se guarda y se carga como HTML compatible con QTextDocument.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEvent, QObject, QSize, Qt
from PyQt6.QtGui import (
    QAction,
    QFont,
    QGuiApplication,
    QIcon,
    QImage,
    QKeySequence,
    QResizeEvent,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextListFormat,
)
from PyQt6.QtPrintSupport import QPrintPreviewDialog, QPrinter
from PyQt6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFontComboBox,
    QHBoxLayout,
    QInputDialog,
    QMenu,
    QMessageBox,
    QScrollArea,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

ICON_DIR = Path(__file__).resolve().parent.parent / "resources" / "icons"
FONT_SIZES: tuple[int, ...] = (8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 36)
ZOOM_STEP = 1
ICON_SIZE = 18

FORMAT_ACTIONS = frozenset(
    {"bold", "italic", "underline", "strike", "bullet", "numbered", "indent_more", "indent_less",
     "left", "center", "right", "justify", "text_color", "background_color", "clear_format"}
)

ICON_FILES: dict[str, str] = {
    "bold": "format-text-bold.svg",
    "italic": "format-text-italic.svg",
    "underline": "format-text-underline.svg",
    "strike": "format-text-strikethrough.svg",
    "bullet": "format-list-unordered.svg",
    "numbered": "format-list-ordered.svg",
    "indent_more": "format-indent-more.svg",
    "indent_less": "format-indent-less.svg",
    "left": "format-justify-left.svg",
    "center": "format-justify-center.svg",
    "right": "format-justify-right.svg",
    "justify": "format-justify-fill.svg",
    "text_color": "format-text-color.svg",
    "background_color": "format-fill-color.svg",
    "clear_format": "edit-clear.svg",
    "cut": "edit-cut.svg",
    "copy": "edit-copy.svg",
    "paste": "edit-paste.svg",
    "hline": "insert-horizontal-rule.svg",
    "table": "insert-table.svg",
    "image": "insert-image.svg",
    "find_replace": "edit-find-replace.svg",
    "print_preview": "document-print-preview.svg",
    "undo": "edit-undo.svg",
    "redo": "edit-redo.svg",
}


class _ToolbarArea(QScrollArea):
    """Área desplazable para una fila de barra: su altura fija es la de la barra, más la de la
    barra de desplazamiento horizontal solo cuando esta es visible."""

    def __init__(self, bar: QToolBar) -> None:
        super().__init__()
        self._bar_height = bar.sizeHint().height()
        self._scrollbar_height = self.horizontalScrollBar().sizeHint().height()
        self.setWidget(bar)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        bar.setMinimumWidth(bar.sizeHint().width())
        self._fit_height()
        self.horizontalScrollBar().installEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self.horizontalScrollBar() and event.type() in (QEvent.Type.Show, QEvent.Type.Hide):
            self._fit_height()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._fit_height()

    def _fit_height(self) -> None:
        """Ajusta la altura a la visibilidad real de la barra de desplazamiento. Los eventos
        Show/Hide no bastan por sí solos: al ensanchar, la barra puede quedar oculta sin emitir
        Hide, así que el ancho también sirve de disparador."""
        extra = self._scrollbar_height if self.horizontalScrollBar().isVisible() else 0
        target = self._bar_height + extra
        if target != self.minimumHeight():
            self.setFixedHeight(target)


class RichTextEditor(QWidget):
    """Editor con barra de herramientas básica; `html()` devuelve el contenido guardable."""

    def __init__(self, parent: QWidget | None = None, predefined: list[str] | None = None) -> None:
        super().__init__(parent)
        self._editor = QTextEdit()
        self._editor.setAcceptRichText(True)
        self._format_toolbar = QToolBar()
        self._actions_toolbar = QToolBar()
        for bar in (self._format_toolbar, self._actions_toolbar):
            bar.setMovable(False)
            bar.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self._actions: dict[str, QAction] = {}
        self._predefined: list[str] = list(predefined or [])
        self._build_toolbar()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_ToolbarArea(self._format_toolbar))
        layout.addWidget(_ToolbarArea(self._actions_toolbar))
        layout.addWidget(self._editor)

    @property
    def editor(self) -> QTextEdit:
        return self._editor

    def action(self, name: str) -> QAction:
        return self._actions[name]

    def html(self) -> str:
        return self._editor.toHtml()

    def set_html(self, html: str) -> None:
        self._editor.setHtml(html)

    def is_empty(self) -> bool:
        return self._editor.document().isEmpty()

    def predefined_texts(self) -> list[str]:
        return list(self._predefined)

    def set_predefined_texts(self, texts: list[str]) -> None:
        self._predefined = list(texts)

    def insert_predefined(self, text: str) -> None:
        """Añade una frase predefinida al final del texto, en un párrafo nuevo si ya hay contenido."""
        cursor = self._editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if not self._editor.document().isEmpty() and cursor.positionInBlock() > 0:
            cursor.insertBlock()
        cursor.insertText(text)
        self._editor.setTextCursor(cursor)

    def _build_toolbar(self) -> None:
        bold = self._add_action("bold", self.tr("Negrita"), QKeySequence("Ctrl+B"), checkable=True)
        bold.toggled.connect(self._apply_bold)
        italic = self._add_action("italic", self.tr("Cursiva"), QKeySequence("Ctrl+I"), checkable=True)
        italic.toggled.connect(self._apply_italic)
        underline = self._add_action("underline", self.tr("Subrayado"), QKeySequence("Ctrl+U"), checkable=True)
        underline.toggled.connect(self._apply_underline)

        strike = self._add_action("strike", self.tr("Tachado"), checkable=True)
        strike.toggled.connect(self._apply_strikethrough)

        self._format_toolbar.addSeparator()
        self._add_action("bullet", self.tr("Lista con viñetas")).triggered.connect(self._bullet_list)
        self._add_action("numbered", self.tr("Lista numerada")).triggered.connect(self._numbered_list)
        self._add_action("indent_more", self.tr("Aumentar sangría")).triggered.connect(
            lambda: self._change_indent(1)
        )
        self._add_action("indent_less", self.tr("Disminuir sangría")).triggered.connect(
            lambda: self._change_indent(-1)
        )

        self._format_toolbar.addSeparator()
        self._add_action("left", self.tr("Alinear a la izquierda")).triggered.connect(
            lambda: self._editor.setAlignment(Qt.AlignmentFlag.AlignLeft)
        )
        self._add_action("center", self.tr("Centrar")).triggered.connect(
            lambda: self._editor.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        )
        self._add_action("right", self.tr("Alinear a la derecha")).triggered.connect(
            lambda: self._editor.setAlignment(Qt.AlignmentFlag.AlignRight)
        )
        self._add_action("justify", self.tr("Justificar")).triggered.connect(
            lambda: self._editor.setAlignment(Qt.AlignmentFlag.AlignJustify)
        )

        self._format_toolbar.addSeparator()
        self._format_toolbar.addWidget(self._build_font_family())
        self._format_toolbar.addWidget(self._build_font_size())
        self._add_action("text_color", self.tr("Color del texto")).triggered.connect(self._choose_text_color)
        self._add_action("background_color", self.tr("Color de fondo")).triggered.connect(
            self._choose_background_color
        )
        self._add_action("clear_format", self.tr("Quitar formato")).triggered.connect(self._clear_formatting)

        self._actions_toolbar.addWidget(self._build_zoom_control())
        self._add_action("cut", self.tr("Cortar"), QKeySequence.StandardKey.Cut).triggered.connect(
            self._editor.cut
        )
        self._add_action("copy", self.tr("Copiar"), QKeySequence.StandardKey.Copy).triggered.connect(
            self._editor.copy
        )
        self._add_action("paste", self.tr("Pegar"), QKeySequence.StandardKey.Paste).triggered.connect(
            self._editor.paste
        )
        self._add_action("paste_plain", self.tr("Pegar como texto sin formato")).triggered.connect(
            self._paste_plain_text
        )
        self._add_action("hline", self.tr("Insertar línea horizontal")).triggered.connect(
            self._insert_horizontal_rule
        )
        self._add_action("table", self.tr("Insertar tabla")).triggered.connect(self._insert_table_dialog)
        self._add_action("image", self.tr("Insertar imagen")).triggered.connect(self._insert_image_dialog)
        self._add_action(
            "find_replace", self.tr("Buscar y reemplazar"), QKeySequence("Ctrl+F")
        ).triggered.connect(self.open_find_replace)
        self._add_action(
            "print_preview", self.tr("Vista previa de impresión"), QKeySequence("Ctrl+Shift+P")
        ).triggered.connect(self.print_preview)

        self._actions_toolbar.addSeparator()
        self._actions_toolbar.addWidget(self._build_predefined_menu())

        self._actions_toolbar.addSeparator()
        undo = self._add_action("undo", self.tr("Deshacer"), QKeySequence.StandardKey.Undo)
        undo.triggered.connect(self._editor.undo)
        redo = self._add_action("redo", self.tr("Rehacer"), QKeySequence.StandardKey.Redo)
        redo.triggered.connect(self._editor.redo)

        self._editor.cursorPositionChanged.connect(self._sync_format_actions)
        self._editor.currentCharFormatChanged.connect(self._sync_format_actions)

    def _build_font_family(self) -> QFontComboBox:
        combo = QFontComboBox()
        combo.setToolTip(self.tr("Fuente"))
        combo.setMaximumWidth(180)
        combo.currentFontChanged.connect(self._apply_font_family)
        return combo

    def _build_font_size(self) -> QComboBox:
        combo = QComboBox()
        combo.setToolTip(self.tr("Tamaño"))
        combo.setEditable(True)
        for size in FONT_SIZES:
            combo.addItem(str(size))
        combo.setCurrentText("11")
        combo.activated.connect(lambda _index: self._apply_font_size(combo.currentText()))
        combo.lineEdit().editingFinished.connect(lambda: self._apply_font_size(combo.currentText()))
        return combo

    def _build_zoom_control(self) -> QWidget:
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        zoom_out = QToolButton()
        zoom_out.setIcon(QIcon(str(ICON_DIR / "zoom-out.svg")))
        zoom_out.setToolTip(self.tr("Alejar"))
        zoom_out.clicked.connect(lambda: self._editor.zoomOut(ZOOM_STEP))
        zoom_in = QToolButton()
        zoom_in.setIcon(QIcon(str(ICON_DIR / "zoom-in.svg")))
        zoom_in.setToolTip(self.tr("Acercar"))
        zoom_in.clicked.connect(lambda: self._editor.zoomIn(ZOOM_STEP))
        layout.addWidget(zoom_out)
        layout.addWidget(zoom_in)
        return box

    def _apply_font_family(self, font: QFont) -> None:
        fmt = QTextCharFormat()
        fmt.setFontFamilies([font.family()])
        self._apply_format(fmt)

    def _apply_font_size(self, text: str) -> None:
        try:
            size = float(text)
        except ValueError:
            return
        if size <= 0:
            return
        fmt = QTextCharFormat()
        fmt.setFontPointSize(size)
        self._apply_format(fmt)

    def _apply_strikethrough(self, checked: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(checked)
        self._apply_format(fmt)

    def _choose_text_color(self) -> None:
        color = QColorDialog.getColor(self._editor.textColor(), self, self.tr("Color del texto"))
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            self._apply_format(fmt)

    def _choose_background_color(self) -> None:
        color = QColorDialog.getColor(Qt.GlobalColor.white, self, self.tr("Color de fondo"))
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setBackground(color)
            self._apply_format(fmt)

    def _clear_formatting(self) -> None:
        cursor = self._editor.textCursor()
        if not cursor.hasSelection():
            return
        cursor.setCharFormat(QTextCharFormat())
        self._editor.setTextCursor(cursor)

    def _change_indent(self, delta: int) -> None:
        cursor = self._editor.textCursor()
        block_format = cursor.blockFormat()
        block_format.setIndent(max(0, block_format.indent() + delta))
        cursor.setBlockFormat(block_format)

    def _paste_plain_text(self) -> None:
        text = QGuiApplication.clipboard().text()
        if text:
            self._editor.textCursor().insertText(text)

    def _insert_horizontal_rule(self) -> None:
        cursor = self._editor.textCursor()
        cursor.insertHtml("<hr/>")
        self._editor.setTextCursor(cursor)

    def insert_table(self, rows: int, columns: int) -> None:
        """Inserta una tabla vacía en la posición del cursor y deja el cursor dentro de ella."""
        if rows < 1 or columns < 1:
            return
        cursor = self._editor.textCursor()
        cursor.insertTable(rows, columns)
        self._editor.setTextCursor(cursor)

    def _insert_table_dialog(self) -> None:
        rows, ok = QInputDialog.getInt(self, self.tr("Insertar tabla"), self.tr("Filas:"), 3, 1, 50)
        if not ok:
            return
        columns, ok = QInputDialog.getInt(
            self, self.tr("Insertar tabla"), self.tr("Columnas:"), 3, 1, 50
        )
        if not ok:
            return
        self.insert_table(rows, columns)

    def insert_image(self, path: str) -> bool:
        """Inserta una imagen desde un archivo local; el HTML guarda la ruta del archivo."""
        image = QImage(path)
        if image.isNull():
            return False
        name = str(Path(path).resolve())
        cursor = self._editor.textCursor()
        cursor.insertImage(image, name)
        self._editor.setTextCursor(cursor)
        return True

    def _insert_image_dialog(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            self.tr("Insertar imagen"),
            "",
            self.tr("Imágenes (*.jpg *.jpeg *.png *.webp *.bmp)"),
        )
        if not path:
            return
        if not self.insert_image(path):
            QMessageBox.warning(self, self.tr("Insertar imagen"), self.tr("No se pudo cargar la imagen."))

    def open_find_replace(self) -> None:
        from luciotech.ui.dialogs.find_replace_dialog import FindReplaceDialog

        dialog = FindReplaceDialog(self, parent=self)
        dialog.exec()

    def find_next(self, needle: str, case_sensitive: bool = False) -> bool:
        if not needle:
            return False
        flags = (
            QTextDocument.FindFlag.FindCaseSensitively
            if case_sensitive
            else QTextDocument.FindFlag(0)
        )
        cursor = self._editor.document().find(needle, self._editor.textCursor(), flags)
        if cursor.isNull():
            return False
        self._editor.setTextCursor(cursor)
        return True

    def replace_current(self, needle: str, replacement: str, case_sensitive: bool = False) -> bool:
        cursor = self._editor.textCursor()
        if not cursor.hasSelection():
            return False
        selected = cursor.selectedText()
        same = selected == needle if case_sensitive else selected.casefold() == needle.casefold()
        if not same:
            return False
        cursor.insertText(replacement)
        self._editor.setTextCursor(cursor)
        return True

    def replace_all(self, needle: str, replacement: str, case_sensitive: bool = False) -> int:
        if not needle:
            return 0
        document = self._editor.document()
        flags = (
            QTextDocument.FindFlag.FindCaseSensitively
            if case_sensitive
            else QTextDocument.FindFlag(0)
        )
        position = 0
        count = 0
        while count < 10_000:
            cursor = QTextCursor(document)
            cursor.setPosition(position)
            found = document.find(needle, cursor, flags)
            if found.isNull():
                break
            if found.selectionStart() < position:
                position += 1
                continue
            found.insertText(replacement)
            position = found.position()
            count += 1
        return count

    def print_preview(self) -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintPreviewDialog(printer, self)
        dialog.paintRequested.connect(self._print_document)
        dialog.exec()

    def render_to_pdf(self, path: str) -> bool:
        """Renderiza el contenido del editor a un archivo PDF."""
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)
        self._print_document(printer)
        return Path(path).exists()

    def _print_document(self, printer: QPrinter) -> None:
        self._editor.document().print(printer)

    def _build_predefined_menu(self) -> QToolButton:
        button = QToolButton()
        button.setText(self.tr("Textos predefinidos"))
        button.setToolTip(self.tr("Insertar una frase predefinida"))
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._predefined_menu = QMenu(button)
        button.setMenu(self._predefined_menu)
        self._predefined_menu.aboutToShow.connect(self._fill_predefined_menu)
        return button

    def _fill_predefined_menu(self) -> None:
        self._predefined_menu.clear()
        if not self._predefined:
            disabled = self._predefined_menu.addAction(self.tr("(No hay textos configurados)"))
            disabled.setEnabled(False)
            return
        for text in self._predefined:
            action = self._predefined_menu.addAction(text)
            action.triggered.connect(lambda _checked=False, value=text: self.insert_predefined(value))

    def _add_action(
        self,
        name: str,
        text: str,
        shortcut: QKeySequence | None = None,
        checkable: bool = False,
    ) -> QAction:
        action = QAction(text, self)
        action.setCheckable(checkable)
        if shortcut is not None:
            action.setShortcut(shortcut)
        action.setToolTip(text)
        icon_file = ICON_FILES.get(name)
        if icon_file is not None:
            action.setIcon(QIcon(str(ICON_DIR / icon_file)))
        (self._format_toolbar if name in FORMAT_ACTIONS else self._actions_toolbar).addAction(action)
        self._actions[name] = action
        return action

    def _apply_format(self, fmt: QTextCharFormat) -> None:
        cursor = self._editor.textCursor()
        if not cursor.hasSelection():
            self._editor.mergeCurrentCharFormat(fmt)
            return
        cursor.mergeCharFormat(fmt)
        self._editor.mergeCurrentCharFormat(fmt)

    def _apply_bold(self, checked: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold if checked else QFont.Weight.Normal)
        self._apply_format(fmt)

    def _apply_italic(self, checked: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontItalic(checked)
        self._apply_format(fmt)

    def _apply_underline(self, checked: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontUnderline(checked)
        self._apply_format(fmt)

    def _bullet_list(self) -> None:
        self._toggle_list(QTextListFormat.Style.ListDisc)

    def _numbered_list(self) -> None:
        self._toggle_list(QTextListFormat.Style.ListDecimal)

    def _toggle_list(self, style: QTextListFormat.Style) -> None:
        cursor = self._editor.textCursor()
        current = cursor.currentList()
        if current is not None and current.format().style() == style:
            block_format = cursor.blockFormat()
            block_format.setIndent(0)
            cursor.setBlockFormat(block_format)
            current.remove(cursor.block())
            return
        list_format = QTextListFormat()
        list_format.setStyle(style)
        cursor.createList(list_format)

    def _sync_format_actions(self, *_args: object) -> None:
        fmt = self._editor.currentCharFormat()
        self._set_checked_silently("bold", fmt.fontWeight() >= QFont.Weight.Bold)
        self._set_checked_silently("italic", fmt.fontItalic())
        self._set_checked_silently("underline", fmt.fontUnderline())

    def _set_checked_silently(self, name: str, checked: bool) -> None:
        action = self._actions[name]
        action.blockSignals(True)
        action.setChecked(checked)
        action.blockSignals(False)
