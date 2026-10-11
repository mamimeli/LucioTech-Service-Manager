"""Editor de texto enriquecido reutilizable para diagnóstico, trabajo y recomendaciones (§8).

Primera versión: negrita, cursiva, subrayado, listas, alineación, deshacer y rehacer.
El contenido se guarda y se carga como HTML compatible con QTextDocument.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QFont, QIcon, QKeySequence, QTextCharFormat, QTextCursor, QTextListFormat
from PyQt6.QtWidgets import QMenu, QScrollArea, QTextEdit, QToolBar, QToolButton, QVBoxLayout, QWidget

ICON_DIR = Path(__file__).resolve().parent.parent / "resources" / "icons"
ICON_FILES: dict[str, str] = {
    "bold": "format-text-bold.svg",
    "italic": "format-text-italic.svg",
    "underline": "format-text-underline.svg",
    "bullet": "format-list-unordered.svg",
    "numbered": "format-list-ordered.svg",
    "left": "format-justify-left.svg",
    "center": "format-justify-center.svg",
    "right": "format-justify-right.svg",
    "undo": "edit-undo.svg",
    "redo": "edit-redo.svg",
}


class RichTextEditor(QWidget):
    """Editor con barra de herramientas básica; `html()` devuelve el contenido guardable."""

    def __init__(self, parent: QWidget | None = None, predefined: list[str] | None = None) -> None:
        super().__init__(parent)
        self._editor = QTextEdit()
        self._editor.setAcceptRichText(True)
        self._toolbar = QToolBar()
        self._toolbar.setMovable(False)
        self._actions: dict[str, QAction] = {}
        self._predefined: list[str] = list(predefined or [])
        self._build_toolbar()

        toolbar_scroll = QScrollArea()
        toolbar_scroll.setWidget(self._toolbar)
        toolbar_scroll.setWidgetResizable(True)
        toolbar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        toolbar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        toolbar_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        toolbar_scroll.setFixedHeight(self._toolbar.sizeHint().height() + toolbar_scroll.horizontalScrollBar().sizeHint().height())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(toolbar_scroll)
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

        self._toolbar.addSeparator()
        self._add_action("bullet", self.tr("Lista con viñetas")).triggered.connect(self._bullet_list)
        self._add_action("numbered", self.tr("Lista numerada")).triggered.connect(self._numbered_list)

        self._toolbar.addSeparator()
        self._add_action("left", self.tr("Alinear a la izquierda")).triggered.connect(
            lambda: self._editor.setAlignment(Qt.AlignmentFlag.AlignLeft)
        )
        self._add_action("center", self.tr("Centrar")).triggered.connect(
            lambda: self._editor.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        )
        self._add_action("right", self.tr("Alinear a la derecha")).triggered.connect(
            lambda: self._editor.setAlignment(Qt.AlignmentFlag.AlignRight)
        )

        self._toolbar.addSeparator()
        self._toolbar.addWidget(self._build_predefined_menu())

        self._toolbar.addSeparator()
        undo = self._add_action("undo", self.tr("Deshacer"), QKeySequence.StandardKey.Undo)
        undo.triggered.connect(self._editor.undo)
        redo = self._add_action("redo", self.tr("Rehacer"), QKeySequence.StandardKey.Redo)
        redo.triggered.connect(self._editor.redo)

        self._editor.cursorPositionChanged.connect(self._sync_format_actions)
        self._editor.currentCharFormatChanged.connect(self._sync_format_actions)

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
        self._toolbar.addAction(action)
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
