"""Selector de documentos imprimibles de una orden (§13.1).

La ventana de la orden no imprime siempre lo mismo: primero se elige el documento y después
se abre su vista previa. Así el botón deja de llamarse «Imprimir comprobante» y pasa a ser
«Documentos».
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from luciotech.ui.documents import DocumentKind

DESCRIPTIONS: dict[DocumentKind, str] = {
    DocumentKind.RECEPCION: (
        "Se entrega al cliente cuando deja el equipo: datos, estado físico, accesorios, "
        "fotografías, valores y condiciones del servicio."
    ),
    DocumentKind.PRESUPUESTO: (
        "Detalle de los conceptos con cantidades y precios, total, validez y espacio para "
        "la aprobación del cliente."
    ),
    DocumentKind.INFORME: (
        "Diagnóstico, trabajo realizado, repuestos, recomendaciones, fotografías y garantía."
    ),
    DocumentKind.ENTREGA: (
        "Se entrega al devolver el equipo: trabajo realizado, pagos, saldo, garantía y "
        "declaración de conformidad."
    ),
    DocumentKind.HISTORIAL: (
        "Todos los cambios de estado, notas y pagos de la orden en orden cronológico."
    ),
}


class DocumentChooserDialog(QDialog):
    """Lista los documentos de la orden y devuelve el elegido."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Documentos de la orden"))
        self.setMinimumSize(520, 380)

        self._list = QListWidget()
        for kind in DocumentKind:
            item = QListWidgetItem(kind.value)
            item.setData(Qt.ItemDataRole.UserRole, kind.value)
            item.setToolTip(DESCRIPTIONS[kind])
            self._list.addItem(item)
        self._list.setCurrentRow(0)
        self._list.currentItemChanged.connect(self._show_description)
        self._list.itemDoubleClicked.connect(lambda _item: self.accept())

        self._description = QLabel()
        self._description.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.tr("Elija el documento que quiere imprimir o guardar:")))
        layout.addWidget(self._list, 1)
        layout.addWidget(self._description)
        layout.addWidget(buttons)
        self._show_description()

    def selected_kind(self) -> DocumentKind:
        item = self._list.currentItem()
        assert item is not None
        return DocumentKind(item.data(Qt.ItemDataRole.UserRole))

    def select(self, kind: DocumentKind) -> None:
        """Deja elegido un documento concreto (lo usan las pruebas y los atajos)."""
        for row in range(self._list.count()):
            if self._list.item(row).data(Qt.ItemDataRole.UserRole) == kind.value:
                self._list.setCurrentRow(row)
                return

    def _show_description(self, *_args: object) -> None:
        item = self._list.currentItem()
        if item is None:
            self._description.setText("")
            return
        self._description.setText(DESCRIPTIONS[DocumentKind(item.data(Qt.ItemDataRole.UserRole))])

    @classmethod
    def choose(cls, parent: QWidget | None = None) -> DocumentKind | None:
        """Abre el selector y devuelve el documento elegido, o None si se cancela."""
        dialog = cls(parent)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.selected_kind()
