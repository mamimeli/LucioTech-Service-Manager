"""Diálogo de buscar y reemplazar para el editor de texto enriquecido (§8)."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from luciotech.ui.widgets.rich_text_editor import RichTextEditor


class FindReplaceDialog(QDialog):
    def __init__(self, editor: RichTextEditor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._editor = editor
        self.setWindowTitle(self.tr("Buscar y reemplazar"))
        self.setMinimumWidth(380)

        self._find_field = QLineEdit()
        self._find_field.setPlaceholderText(self.tr("Texto a buscar"))
        self._replace_field = QLineEdit()
        self._replace_field.setPlaceholderText(self.tr("Reemplazar con"))
        self._case_check = QCheckBox(self.tr("Distinguir mayúsculas"))
        self._status = QLabel()

        find_button = QPushButton(self.tr("Buscar siguiente"))
        find_button.clicked.connect(self._on_find_next)
        replace_button = QPushButton(self.tr("Reemplazar"))
        replace_button.clicked.connect(self._on_replace)
        replace_all_button = QPushButton(self.tr("Reemplazar todo"))
        replace_all_button.clicked.connect(self._on_replace_all)
        close_button = QPushButton(self.tr("Cerrar"))
        close_button.clicked.connect(self.reject)

        form = QFormLayout()
        form.addRow(self.tr("Buscar"), self._find_field)
        form.addRow(self.tr("Reemplazar con"), self._replace_field)
        form.addRow(self._case_check)

        buttons = QHBoxLayout()
        buttons.addWidget(find_button)
        buttons.addWidget(replace_button)
        buttons.addWidget(replace_all_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._status)
        layout.addLayout(buttons)
        self._find_field.setFocus()

    def _case_sensitive(self) -> bool:
        return self._case_check.isChecked()

    def _on_find_next(self) -> None:
        found = self._editor.find_next(self._find_field.text(), self._case_sensitive())
        self._status.setText(
            self.tr("Coincidencia encontrada.") if found else self.tr("Sin más coincidencias.")
        )

    def _on_replace(self) -> None:
        done = self._editor.replace_current(
            self._find_field.text(), self._replace_field.text(), self._case_sensitive()
        )
        if done:
            self._status.setText(self.tr("Reemplazado."))
        else:
            self._on_find_next()

    def _on_replace_all(self) -> None:
        count = self._editor.replace_all(
            self._find_field.text(), self._replace_field.text(), self._case_sensitive()
        )
        self._status.setText(self.tr("%1 reemplazos.").replace("%1", str(count)))
