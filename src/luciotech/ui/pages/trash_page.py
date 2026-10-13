"""Papelera: órdenes borradas lógicamente, con opción de restaurarlas (§18).

Las órdenes nunca se borran de la base de datos: al eliminarlas quedan con `activo = False` y
una fecha de eliminación. Esta página las lista y permite devolverlas a la lista activa.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from luciotech.database.models import ServiceOrder
from luciotech.services.order_query_service import OrderFilter, search_orders
from luciotech.services.order_service import restore_order
from luciotech.ui.dialogs.order_detail_dialog import OrderDetailDialog
from luciotech.ui.formatting import format_datetime, format_money

OPERATOR = "Ing. Lucio"
COLUMNS = (
    "Número de orden",
    "Fecha de ingreso",
    "Cliente",
    "Tipo de equipo",
    "Marca y modelo",
    "Estado",
    "Saldo",
    "Eliminada el",
)


class TrashPage(QWidget):
    data_changed = pyqtSignal()

    def __init__(
        self, session_factory: sessionmaker[Session], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory

        self._restore_button = QPushButton(self.tr("Restaurar"))
        self._restore_button.setToolTip(self.tr("Devuelve la orden seleccionada a la lista"))
        self._restore_button.clicked.connect(self.restore_selected)
        open_button = QPushButton(self.tr("Abrir"))
        open_button.clicked.connect(self.open_selected)

        self._hint = QLabel(
            self.tr(
                "Las órdenes eliminadas no se borran de la base de datos: quedan aquí hasta que "
                "las restaure."
            )
        )
        self._hint.setWordWrap(True)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self._hint, 1)
        toolbar.addWidget(open_button)
        toolbar.addWidget(self._restore_button)

        self._table = QTableWidget(0, len(COLUMNS))
        self._table.setHorizontalHeaderLabels([self.tr(c) for c in COLUMNS])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.doubleClicked.connect(lambda _index: self.open_selected())

        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addWidget(self._table)
        self.refresh()

    def refresh(self) -> None:
        with self._session_factory() as session:
            orders = search_orders(session, OrderFilter(solo_eliminadas=True))
            self._order_ids = [order.id for order in orders]
            rows = [
                [
                    order.numero_orden,
                    format_datetime(order.fecha_ingreso),
                    order.customer.nombre_completo,
                    order.equipment.tipo_equipo,
                    " ".join(part for part in (order.equipment.marca, order.equipment.modelo) if part),
                    order.estado,
                    format_money(order.saldo_pendiente),
                    format_datetime(order.fecha_eliminacion),
                ]
                for order in orders
            ]
        self._table.setRowCount(len(rows))
        for row, cells in enumerate(rows):
            for column, value in enumerate(cells):
                self._table.setItem(row, column, QTableWidgetItem(value))
        self._table.resizeColumnsToContents()
        self._restore_button.setEnabled(bool(rows))

    def visible_row_count(self) -> int:
        return self._table.rowCount()

    def order_number_at(self, row: int) -> str:
        item = self._table.item(row, 0)
        return item.text() if item is not None else ""

    def open_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        dialog = OrderDetailDialog(self._session_factory, self._order_ids[row], OPERATOR, parent=self)
        dialog.exec()
        self.refresh()
        self.data_changed.emit()

    def restore_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.information(
                self, self.windowTitle(), self.tr("Seleccione una orden de la papelera.")
            )
            return
        order_id = self._order_ids[row]
        try:
            with self._session_factory() as session:
                order = session.get(ServiceOrder, order_id)
                if order is None:
                    raise ValueError(self.tr("La orden ya no existe."))
                restore_order(session, order, usuario=OPERATOR)
                session.commit()
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        except SQLAlchemyError:
            QMessageBox.critical(
                self, self.windowTitle(), self.tr("No se pudo restaurar. Intente de nuevo.")
            )
            return
        self.refresh()
        self.data_changed.emit()
