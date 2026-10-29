"""Pruebas de la pestaña «Presupuesto y pagos» (§9, §12 y §5.7)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from PyQt6.QtWidgets import QDialog, QInputDialog, QTabWidget
from pytestqt.qtbot import QtBot
from sqlalchemy.orm import Session, sessionmaker

from luciotech.database.enums import BudgetLineType
from luciotech.database.models import ServiceOrder
from luciotech.services.budget_service import add_line
from luciotech.services.customer_service import CustomerData
from luciotech.services.equipment_service import EquipmentData
from luciotech.services.reception_service import ReceptionData, register_reception
from luciotech.ui.dialogs.budget_payments_tab import (
    SALDO_CLEAR_COLOR,
    SALDO_DUE_COLOR,
    BudgetLineDialog,
    BudgetPaymentsTab,
    PaymentDialog,
)
from luciotech.ui.dialogs.order_detail_dialog import OrderDetailDialog

USER = "Ing. Lucio"


@pytest.fixture
def order_id(session_factory: sessionmaker[Session], tax_enabled: None) -> int:
    """Orden con diagnóstico de 100 y anticipo de 20, con IVA del 15 % encendido: total 115,
    saldo 95. La pestaña se prueba con impuesto para que el desglose tenga todas las filas."""
    with session_factory() as session:
        order = register_reception(
            session,
            ReceptionData(
                equipment=EquipmentData(cliente_id=None, tipo_equipo="Laptop"),
                new_customer=CustomerData(nombre_completo="Ana Torres",
                                          telefono_principal="0991234567"),
                costo_diagnostico=Decimal("100"),
                anticipo=Decimal("20"),
            ),
        )
        session.commit()
        return order.id


def _tab(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> BudgetPaymentsTab:
    tab = BudgetPaymentsTab(session_factory, usuario=USER)
    qtbot.addWidget(tab)
    tab.set_order(order_id)
    return tab


def _stored(session_factory: sessionmaker[Session], order_id: int) -> ServiceOrder:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        assert order is not None
        return order


def _add_line_directly(
    session_factory: sessionmaker[Session], order_id: int, quantity: str, price: str
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        assert order is not None
        add_line(
            session, order, tipo=BudgetLineType.REPUESTO, descripcion="SSD 480 GB",
            cantidad=Decimal(quantity), precio_unitario=Decimal(price),
        )
        session.commit()


def _fake_line_dialog(monkeypatch: pytest.MonkeyPatch, values: tuple) -> None:
    monkeypatch.setattr(BudgetLineDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(BudgetLineDialog, "values", lambda self: values)


def _fake_payment_dialog(monkeypatch: pytest.MonkeyPatch, values: tuple) -> None:
    monkeypatch.setattr(PaymentDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(PaymentDialog, "values", lambda self: values)


def test_totals_panel_says_when_tax_is_disabled(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    """Con el IVA desactivado (valor por defecto) no se suma nada y la pestaña lo explica."""
    with session_factory() as session:
        order = register_reception(
            session,
            ReceptionData(
                equipment=EquipmentData(cliente_id=None, tipo_equipo="Laptop"),
                new_customer=CustomerData(nombre_completo="Ana Torres",
                                          telefono_principal="0991234567"),
                costo_diagnostico=Decimal("100"),
                anticipo=Decimal("20"),
            ),
        )
        session.commit()
        order_id = order.id

    tab = _tab(qtbot, session_factory, order_id)
    assert "desactivado" in tab._totals_labels["iva"].text()
    assert tab._totals_values["iva"].text() == "0.00 USD"
    assert tab._totals_values["total"].text() == "100.00 USD"
    assert tab._totals_values["saldo"].text() == "80.00 USD"


def test_totals_panel_starts_from_the_reception(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    tab = _tab(qtbot, session_factory, order_id)
    assert tab._totals_values["subtotal"].text() == "100.00 USD"
    assert tab._totals_values["iva"].text() == "15.00 USD"
    assert tab._totals_values["total"].text() == "115.00 USD"
    assert tab._totals_values["anticipo"].text() == "20.00 USD"
    assert tab._totals_values["saldo"].text() == "95.00 USD"
    assert tab._discount.text() == "0.00"
    assert tab._lines.rowCount() == 0


def test_add_line_updates_table_and_totals_without_reopening(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tab = _tab(qtbot, session_factory, order_id)
    _fake_line_dialog(monkeypatch, ("Repuesto", "SSD 480 GB", Decimal("2"), Decimal("50")))

    tab._add_line()

    assert tab._lines.rowCount() == 1
    assert tab._lines.item(0, 0).text() == "Repuesto"
    assert tab._lines.item(0, 4).text() == "100.00 USD"
    # subtotal 200, IVA 30, total 230, saldo 210
    assert tab._totals_values["subtotal"].text() == "200.00 USD"
    assert tab._totals_values["total"].text() == "230.00 USD"
    assert tab._totals_values["saldo"].text() == "210.00 USD"
    assert _stored(session_factory, order_id).saldo_pendiente == Decimal("210.00")


def test_edit_line_recalculates_the_total(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _add_line_directly(session_factory, order_id, "2", "50")
    tab = _tab(qtbot, session_factory, order_id)
    assert tab._totals_values["total"].text() == "230.00 USD"

    tab._lines.selectRow(0)
    _fake_line_dialog(monkeypatch, ("Repuesto", "SSD 480 GB", Decimal("1"), Decimal("50")))
    tab._edit_line()

    assert tab._lines.item(0, 4).text() == "50.00 USD"
    assert tab._totals_values["total"].text() == "172.50 USD"


def test_remove_line_recalculates_the_total(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    _add_line_directly(session_factory, order_id, "2", "50")
    tab = _tab(qtbot, session_factory, order_id)

    tab._lines.selectRow(0)
    tab._remove_line()

    assert tab._lines.rowCount() == 0
    assert tab._totals_values["total"].text() == "115.00 USD"
    assert _stored(session_factory, order_id).total == Decimal("115.00")


def test_remove_without_selection_reports_it(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    tab = _tab(qtbot, session_factory, order_id)
    tab._remove_line()
    assert tab._message.text() == "Seleccione una línea."


def test_discount_field_recalculates_the_total(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    tab = _tab(qtbot, session_factory, order_id)
    tab._discount.setText("15")
    tab._apply_discount()

    # 100 - 15 + 15 = 100
    assert tab._totals_values["total"].text() == "100.00 USD"
    assert tab._totals_values["saldo"].text() == "80.00 USD"
    assert _stored(session_factory, order_id).descuento == Decimal("15.00")


def test_invalid_discount_is_reported_and_reverted(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    tab = _tab(qtbot, session_factory, order_id)
    tab._discount.setText("abc")
    tab._apply_discount()

    assert tab._message.text() == "Importe no válido. Use solo números y punto decimal."
    assert tab._discount.text() == "0.00"
    assert _stored(session_factory, order_id).descuento == Decimal("0.00")


def test_register_payment_lists_it_and_updates_the_balance(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tab = _tab(qtbot, session_factory, order_id)
    _fake_payment_dialog(monkeypatch, ("Abono", "Efectivo", Decimal("30"), "REC-1", ""))

    tab._register_payment()

    assert tab._payments.rowCount() == 1
    assert tab._payments.item(0, 1).text() == "Abono"
    assert tab._payments.item(0, 3).text() == "30.00 USD"
    assert tab._payments.item(0, 4).text() == "REC-1"
    assert tab._payments.item(0, 5).text() == "Vigente"
    assert tab._totals_values["saldo"].text() == "65.00 USD"
    assert _stored(session_factory, order_id).saldo_pendiente == Decimal("65.00")


def test_second_deposit_warns_without_blocking(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El anticipo de la recepción ya resta: se avisa, pero el pago se registra igual."""
    tab = _tab(qtbot, session_factory, order_id)
    _fake_payment_dialog(monkeypatch, ("Anticipo", "Efectivo", Decimal("10"), "", ""))

    tab._register_payment()

    assert "anticipo registrado en la recepción" in tab._message.text()
    assert tab._payments.rowCount() == 1
    assert tab._totals_values["saldo"].text() == "85.00 USD"


def test_invalid_payment_amount_is_reported(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tab = _tab(qtbot, session_factory, order_id)
    _fake_payment_dialog(monkeypatch, ("Abono", "Efectivo", Decimal("-1"), "", ""))

    tab._register_payment()

    assert tab._message.text() == "El importe debe ser mayor que cero."
    assert tab._payments.rowCount() == 0


def test_void_payment_marks_the_row_and_restores_the_balance(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tab = _tab(qtbot, session_factory, order_id)
    _fake_payment_dialog(monkeypatch, ("Abono", "Efectivo", Decimal("30"), "", ""))
    tab._register_payment()
    monkeypatch.setattr(
        QInputDialog, "getText", lambda *args, **kwargs: ("Cobro duplicado", True)
    )

    tab._payments.selectRow(0)
    tab._void_payment()

    assert tab._payments.item(0, 5).text() == "Anulado"
    assert tab._totals_values["saldo"].text() == "95.00 USD"
    with session_factory() as session:
        stored = session.get(ServiceOrder, order_id)
        assert stored is not None
        assert stored.saldo_pendiente == Decimal("95.00")
        assert stored.payments[0].motivo_anulacion == "Cobro duplicado"


def test_cancelling_the_void_keeps_the_payment(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tab = _tab(qtbot, session_factory, order_id)
    _fake_payment_dialog(monkeypatch, ("Abono", "Efectivo", Decimal("30"), "", ""))
    tab._register_payment()
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("", False))

    tab._payments.selectRow(0)
    tab._void_payment()

    assert tab._payments.item(0, 5).text() == "Vigente"
    assert tab._totals_values["saldo"].text() == "65.00 USD"


def test_tab_is_present_in_the_order_detail_dialog(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    dialog = OrderDetailDialog(session_factory, order_id, USER)
    qtbot.addWidget(dialog)
    labels = [dialog._tabs.tabText(index) for index in range(dialog._tabs.count())]
    assert "Dinero" in labels
    assert dialog._tabs.widget(labels.index("Dinero")) is dialog._budget_payments


def test_budget_change_refreshes_the_dialog_summary(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    """Al cambiar el presupuesto, el resumen y el historial del diálogo se actualizan solos."""
    dialog = OrderDetailDialog(session_factory, order_id, USER)
    qtbot.addWidget(dialog)
    assert "115.00 USD" in dialog._summary.text()

    dialog._budget_payments._discount.setText("15")
    dialog._budget_payments._apply_discount()

    assert "100.00 USD" in dialog._summary.text()
    assert "80.00 USD" in dialog._summary.text()


def test_the_balance_stands_out_in_the_totals_panel(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    """El saldo es el número más grande del panel, por encima del total y del subtotal."""
    tab = _tab(qtbot, session_factory, order_id)
    saldo = tab._totals_values["saldo"].font().pointSizeF()
    total = tab._totals_values["total"].font().pointSizeF()
    subtotal = tab._totals_values["subtotal"].font().pointSizeF()
    assert saldo > total > subtotal
    assert tab._totals_values["saldo"].text() == "95.00 USD"


def test_the_balance_warns_while_money_is_owed(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    tab = _tab(qtbot, session_factory, order_id)
    assert SALDO_DUE_COLOR in tab._totals_values["saldo"].styleSheet()


def test_the_balance_turns_calm_when_everything_is_paid(
    qtbot: QtBot,
    session_factory: sessionmaker[Session],
    order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tab = _tab(qtbot, session_factory, order_id)
    _fake_payment_dialog(
        monkeypatch, ("Pago final", "Efectivo", Decimal("95"), "", "")
    )
    tab._register_payment()

    assert tab._totals_values["saldo"].text() == "0.00 USD"
    assert SALDO_CLEAR_COLOR in tab._totals_values["saldo"].styleSheet()
