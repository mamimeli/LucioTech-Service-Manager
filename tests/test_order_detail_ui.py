"""Pruebas de UI del paso 7: detalle de orden con pytest-qt."""

from __future__ import annotations

from decimal import Decimal

import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QDialog, QMessageBox, QPushButton, QTabWidget
from pytestqt.qtbot import QtBot
from sqlalchemy.orm import Session, sessionmaker

from luciotech.database.enums import OrderState, PaymentMethod, PaymentType
from luciotech.database.models import ServiceOrder
from luciotech.services.customer_service import CustomerData
from luciotech.services.equipment_service import EquipmentData
from luciotech.services.reception_service import ReceptionData, register_reception
from luciotech.ui.dialogs.budget_payments_tab import PaymentDialog
from luciotech.ui.dialogs import order_detail_dialog as detail_module
from luciotech.ui.dialogs import order_detail_dialog as detail_module
from luciotech.ui.dialogs.order_detail_dialog import OrderDetailDialog
from luciotech.ui.documents import DocumentKind
from luciotech.ui.documents import DocumentKind
from luciotech.ui.pages.orders_page import OrdersPage

USER = "Ing. Lucio"


@pytest.fixture
def order_id(session_factory: sessionmaker[Session], tax_enabled: None) -> int:
    with session_factory() as session:
        order = register_reception(
            session,
            ReceptionData(
                equipment=EquipmentData(cliente_id=None, tipo_equipo="Laptop", marca="HP",
                                        problema_reportado_cliente="No enciende"),
                new_customer=CustomerData(nombre_completo="Ana Torres",
                                          telefono_principal="0991234567"),
                costo_diagnostico=Decimal("100"),
                anticipo=Decimal("20"),
            ),
        )
        session.commit()
        return order.id


def _dialog(qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int) -> OrderDetailDialog:
    dialog = OrderDetailDialog(session_factory, order_id, USER)
    qtbot.addWidget(dialog)
    return dialog


def _stored(session_factory: sessionmaker[Session], order_id: int) -> ServiceOrder:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        assert order is not None
        return order


def _fake_payment_dialog(monkeypatch: pytest.MonkeyPatch, values: tuple | None) -> None:
    """Sustituye el diálogo de pago de la pestaña por uno que devuelve `values` sin abrirse."""
    monkeypatch.setattr(PaymentDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(PaymentDialog, "values", lambda self: values)


def test_summary_shows_balance_and_customer(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    dialog = _dialog(qtbot, session_factory, order_id)
    html = dialog._summary.text()
    assert "Ana Torres" in html
    assert "115.00 USD" in html
    assert "95.00 USD" in html


def test_the_order_dialog_opens_with_room_for_its_content(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    """La ventana no puede encogerse por debajo de lo que pide su propio contenido."""
    dialog = _dialog(qtbot, session_factory, order_id)
    needed = dialog.layout().minimumSize()
    assert dialog.minimumSize() == needed
    assert dialog.width() >= needed.width()
    assert dialog.height() >= needed.height()


def test_totals_are_fully_visible_in_the_budget_tab(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    """Con el tamaño con el que abre, el saldo y el total caben dentro de la pestaña."""
    dialog = _dialog(qtbot, session_factory, order_id)
    dialog.show()
    tabs = dialog.findChild(QTabWidget)
    assert tabs is not None
    labels = [tabs.tabText(index) for index in range(tabs.count())]
    tabs.setCurrentIndex(labels.index("Presupuesto y pagos"))
    qtbot.wait(20)

    tab = dialog._budget_payments
    assert tab.height() >= tab.minimumSizeHint().height()
    for key in ("total", "saldo"):
        label = tab._totals_values[key]
        bottom = label.mapTo(tab, QPoint(0, 0)).y() + label.height()
        assert bottom <= tab.height()


def test_change_state_records_history(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    dialog = _dialog(qtbot, session_factory, order_id)
    dialog._state_combo.setCurrentIndex(dialog._state_combo.findData(OrderState.EN_REPARACION.value))
    dialog._state_comment.setText("Se revisa la placa")
    dialog._change_state()

    stored = _stored(session_factory, order_id)
    assert stored.estado == OrderState.EN_REPARACION
    with session_factory() as session:
        session_order = session.get(ServiceOrder, order_id)
        comments = [change.comentario for change in session_order.state_changes]
    assert "Se revisa la placa" in comments
    assert dialog._history.rowCount() >= 2


def test_payment_updates_balance_and_summary(
    qtbot: QtBot,
    session_factory: sessionmaker[Session],
    order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El único sitio para cobrar es la pestaña; al guardar, el resumen del diálogo se actualiza."""
    dialog = _dialog(qtbot, session_factory, order_id)
    _fake_payment_dialog(
        monkeypatch,
        (PaymentType.ABONO.value, PaymentMethod.EFECTIVO.value, Decimal("30.50"), "", ""),
    )
    dialog._budget_payments._register_payment()

    stored = _stored(session_factory, order_id)
    assert stored.saldo_pendiente == Decimal("64.50")
    assert "64.50 USD" in dialog._summary.text()


def test_there_is_only_one_place_to_register_a_payment(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    """El cobro no se duplica: un solo botón «Registrar pago» en todo el detalle."""
    dialog = _dialog(qtbot, session_factory, order_id)
    buttons = [
        button for button in dialog.findChildren(QPushButton)
        if button.text() == "Registrar pago"
    ]
    assert len(buttons) == 1


def test_invalid_payment_amount_is_reported(
    qtbot: QtBot,
    session_factory: sessionmaker[Session],
    order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dialog = _dialog(qtbot, session_factory, order_id)
    _fake_payment_dialog(monkeypatch, None)
    dialog._budget_payments._register_payment()
    assert "Importe no válido" in dialog._budget_payments._message.text()
    assert _stored(session_factory, order_id).saldo_pendiente == Decimal("95.00")


def test_refund_above_paid_is_rejected(
    qtbot: QtBot,
    session_factory: sessionmaker[Session],
    order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dialog = _dialog(qtbot, session_factory, order_id)
    _fake_payment_dialog(
        monkeypatch,
        (PaymentType.REEMBOLSO.value, PaymentMethod.EFECTIVO.value, Decimal("10"), "", ""),
    )
    dialog._budget_payments._register_payment()
    assert "reembolsar más de lo pagado" in dialog._budget_payments._message.text()
    assert _stored(session_factory, order_id).saldo_pendiente == Decimal("95.00")


def test_note_is_added_to_history(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    dialog = _dialog(qtbot, session_factory, order_id)
    dialog._note_title.setText("Cliente llamó")
    dialog._note_body.setText("Pide llamada por la tarde")
    dialog._add_note()
    titles = [dialog._history.item(row, 1).text() for row in range(dialog._history.rowCount())]
    assert "Cliente llamó" in titles


def test_empty_note_title_is_rejected(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    dialog = _dialog(qtbot, session_factory, order_id)
    dialog._note_title.setText("   ")
    dialog._add_note()
    assert "título" in dialog._message.text().lower()


def test_delivery_requires_confirmation(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    dialog = _dialog(qtbot, session_factory, order_id)
    dialog._deliver()
    assert _stored(session_factory, order_id).estado == OrderState.RECIBIDO


def test_delivery_when_confirmed(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    dialog = _dialog(qtbot, session_factory, order_id)
    dialog._deliver()
    stored = _stored(session_factory, order_id)
    assert stored.estado == OrderState.ENTREGADO
    assert stored.fecha_entrega is not None


def test_orders_page_opens_detail_for_selected_row(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[int] = []

    def fake_exec(self: OrderDetailDialog) -> int:
        opened.append(self._order_id)
        return 0

    monkeypatch.setattr(OrderDetailDialog, "exec", fake_exec)
    page = OrdersPage(session_factory)
    qtbot.addWidget(page)
    page._table.selectRow(0)
    page.open_selected()
    assert opened == [order_id]


# Siguiente paso del resumen (§9)


def _set_state(
    session_factory: sessionmaker[Session], order_id: int, state: OrderState
) -> None:
    """Deja la orden en ese estado sin pasar por el historial: solo prepara la prueba."""
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        assert order is not None
        order.estado = state.value
        session.commit()


def _spy_documents(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, DocumentKind]]:
    """Evita abrir la vista previa y apunta qué documento se pidió."""
    opened: list[tuple[int, DocumentKind]] = []
    monkeypatch.setattr(
        detail_module,
        "print_order_document",
        lambda _factory, order_id, kind, _parent=None: opened.append((order_id, kind)) or True,
    )
    return opened


def test_the_summary_proposes_the_next_step_and_advances_the_order(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    dialog = _dialog(qtbot, session_factory, order_id)
    assert dialog._primary_button.text() == "Iniciar diagnóstico"

    dialog._primary_button.click()

    assert _stored(session_factory, order_id).estado == OrderState.PENDIENTE_DIAGNOSTICO
    assert dialog._primary_button.text() == "Marcar como diagnosticado"


def test_the_next_step_opens_the_budget_and_waits_for_approval(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = _spy_documents(monkeypatch)
    _set_state(session_factory, order_id, OrderState.DIAGNOSTICADO)
    dialog = _dialog(qtbot, session_factory, order_id)
    assert dialog._primary_button.text() == "Entregar presupuesto al cliente"

    dialog._primary_button.click()

    assert _stored(session_factory, order_id).estado == OrderState.ESPERANDO_APROBACION
    assert opened == [(order_id, DocumentKind.PRESUPUESTO)]
    assert "Presupuesto" in dialog._message.text()


def test_delivering_from_the_next_step_asks_for_confirmation(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = _spy_documents(monkeypatch)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    _set_state(session_factory, order_id, OrderState.LISTO_PARA_ENTREGAR)
    dialog = _dialog(qtbot, session_factory, order_id)

    dialog._primary_button.click()

    assert _stored(session_factory, order_id).estado == OrderState.LISTO_PARA_ENTREGAR
    assert opened == []


def test_delivering_from_the_next_step_closes_the_order_and_opens_the_note(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = _spy_documents(monkeypatch)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    _set_state(session_factory, order_id, OrderState.LISTO_PARA_ENTREGAR)
    dialog = _dialog(qtbot, session_factory, order_id)

    dialog._primary_button.click()

    stored = _stored(session_factory, order_id)
    assert stored.estado == OrderState.ENTREGADO
    assert stored.fecha_entrega is not None
    assert opened == [(order_id, DocumentKind.ENTREGA)]
    assert dialog._primary_button.text() == "Imprimir comprobante de entrega"


def test_a_delivered_order_only_reprints_the_delivery_note(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = _spy_documents(monkeypatch)
    _set_state(session_factory, order_id, OrderState.ENTREGADO)
    dialog = _dialog(qtbot, session_factory, order_id)

    dialog._primary_button.click()

    assert _stored(session_factory, order_id).estado == OrderState.ENTREGADO
    assert opened == [(order_id, DocumentKind.ENTREGA)]


def test_a_cancelled_order_offers_no_action(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    _set_state(session_factory, order_id, OrderState.CANCELADO)
    dialog = _dialog(qtbot, session_factory, order_id)

    assert not dialog._primary_button.isEnabled()
    assert dialog._primary_button.text() == "Sin acciones pendientes"


def test_the_summary_shows_the_technician_in_charge(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        assert order is not None
        order.tecnico_responsable = "Ing. Lucio"
        session.commit()

    dialog = _dialog(qtbot, session_factory, order_id)

    assert "Técnico responsable" in dialog._summary.text()
    assert "Ing. Lucio" in dialog._summary.text()


# Siguiente paso del resumen (§9)


def _set_state(
    session_factory: sessionmaker[Session], order_id: int, state: OrderState
) -> None:
    """Deja la orden en ese estado sin pasar por el historial: solo prepara la prueba."""
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        assert order is not None
        order.estado = state.value
        session.commit()


def _spy_documents(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, DocumentKind]]:
    """Evita abrir la vista previa y apunta qué documento se pidió."""
    opened: list[tuple[int, DocumentKind]] = []
    monkeypatch.setattr(
        detail_module,
        "print_order_document",
        lambda _factory, order_id, kind, _parent=None: opened.append((order_id, kind)) or True,
    )
    return opened


def test_the_summary_proposes_the_next_step_and_advances_the_order(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    dialog = _dialog(qtbot, session_factory, order_id)
    assert dialog._primary_button.text() == "Iniciar diagnóstico"

    dialog._primary_button.click()

    assert _stored(session_factory, order_id).estado == OrderState.PENDIENTE_DIAGNOSTICO
    assert dialog._primary_button.text() == "Marcar como diagnosticado"


def test_the_next_step_opens_the_budget_and_waits_for_approval(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = _spy_documents(monkeypatch)
    _set_state(session_factory, order_id, OrderState.DIAGNOSTICADO)
    dialog = _dialog(qtbot, session_factory, order_id)
    assert dialog._primary_button.text() == "Entregar presupuesto al cliente"

    dialog._primary_button.click()

    assert _stored(session_factory, order_id).estado == OrderState.ESPERANDO_APROBACION
    assert opened == [(order_id, DocumentKind.PRESUPUESTO)]
    assert "Presupuesto" in dialog._message.text()


def test_delivering_from_the_next_step_asks_for_confirmation(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = _spy_documents(monkeypatch)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    _set_state(session_factory, order_id, OrderState.LISTO_PARA_ENTREGAR)
    dialog = _dialog(qtbot, session_factory, order_id)

    dialog._primary_button.click()

    assert _stored(session_factory, order_id).estado == OrderState.LISTO_PARA_ENTREGAR
    assert opened == []


def test_delivering_from_the_next_step_closes_the_order_and_opens_the_note(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = _spy_documents(monkeypatch)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    _set_state(session_factory, order_id, OrderState.LISTO_PARA_ENTREGAR)
    dialog = _dialog(qtbot, session_factory, order_id)

    dialog._primary_button.click()

    stored = _stored(session_factory, order_id)
    assert stored.estado == OrderState.ENTREGADO
    assert stored.fecha_entrega is not None
    assert opened == [(order_id, DocumentKind.ENTREGA)]
    assert dialog._primary_button.text() == "Imprimir comprobante de entrega"


def test_a_delivered_order_only_reprints_the_delivery_note(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = _spy_documents(monkeypatch)
    _set_state(session_factory, order_id, OrderState.ENTREGADO)
    dialog = _dialog(qtbot, session_factory, order_id)

    dialog._primary_button.click()

    assert _stored(session_factory, order_id).estado == OrderState.ENTREGADO
    assert opened == [(order_id, DocumentKind.ENTREGA)]


def test_a_cancelled_order_offers_no_action(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    _set_state(session_factory, order_id, OrderState.CANCELADO)
    dialog = _dialog(qtbot, session_factory, order_id)

    assert not dialog._primary_button.isEnabled()
    assert dialog._primary_button.text() == "Sin acciones pendientes"


def test_the_summary_shows_the_technician_in_charge(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        assert order is not None
        order.tecnico_responsable = "Ing. Lucio"
        session.commit()

    dialog = _dialog(qtbot, session_factory, order_id)

    assert "Técnico responsable" in dialog._summary.text()
    assert "Ing. Lucio" in dialog._summary.text()


def test_choosing_delivered_in_the_state_combo_records_the_delivery(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """«Entregado» en el selector pasa por la entrega real: fecha de entrega y evento."""
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    dialog = _dialog(qtbot, session_factory, order_id)
    dialog._state_combo.setCurrentIndex(
        dialog._state_combo.findData(OrderState.ENTREGADO.value)
    )

    dialog._change_state()

    stored = _stored(session_factory, order_id)
    assert stored.estado == OrderState.ENTREGADO
    assert stored.fecha_entrega is not None
