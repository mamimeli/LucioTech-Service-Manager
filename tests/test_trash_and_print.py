"""Pruebas del bloque de papelera, borrado lógico e impresión del comprobante (§13, §18)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from PyQt6.QtWidgets import QDialog, QMessageBox
from pytestqt.qtbot import QtBot
from sqlalchemy.orm import Session, sessionmaker

from luciotech.config import DEFAULT_RETENTION_MONTHS
from luciotech.database.enums import (
    BudgetLineType,
    EventType,
    PaymentMethod,
    PaymentType,
    PhotoType,
)
from luciotech.database.models import Photograph, ServiceOrder
from luciotech.services.budget_service import add_line
from luciotech.services.customer_service import CustomerData
from luciotech.services.equipment_service import EquipmentData
from luciotech.services.order_detail_service import register_payment
from luciotech.services.order_query_service import OrderFilter, search_orders
from luciotech.services.order_service import restore_order, soft_delete_order
from luciotech.services.reception_service import ReceptionData, register_reception
from luciotech.services.settings_service import (
    KEY_RETENTION_MONTHS,
    KEY_SERVICE_TERMS,
    KEY_WORKSHOP_PHONE,
    retention_months,
    service_conditions,
    service_terms,
    set_retention_months,
    set_service_terms,
    set_value,
    tax_settings,
    workshop_contact,
    workshop_name,
)
from luciotech.services.totals_service import order_totals
from luciotech.ui import documents
from luciotech.ui.dialogs.order_detail_dialog import OrderDetailDialog
from luciotech.ui.formatting import format_money
from luciotech.ui.pages import orders_page as orders_page_module
from luciotech.ui.pages import trash_page as trash_page_module
from luciotech.ui.pages.orders_page import OrdersPage
from luciotech.ui.pages.trash_page import TrashPage


class _FakeMessageBox:
    """Reemplazo de QMessageBox para no abrir ventanas modales en las pruebas."""

    StandardButton = QMessageBox.StandardButton
    ButtonRole = QMessageBox.ButtonRole

    answer = QMessageBox.StandardButton.Yes
    warnings: list[str] = []
    infos: list[str] = []
    criticals: list[str] = []

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        self._buttons: list[tuple[str, object]] = []
        self._clicked: object | None = None
        self.text = ""

    def setWindowTitle(self, _title: str) -> None:
        return None

    def setText(self, text: str) -> None:
        self.text = text

    def addButton(self, label: str, role: object) -> object:
        handle = object()
        self._buttons.append((label, handle))
        if role == QMessageBox.ButtonRole.AcceptRole:
            self._clicked = handle
        return handle

    def exec(self) -> int:
        return 0

    def clickedButton(self) -> object | None:
        return self._clicked

    @classmethod
    def reset(cls) -> None:
        cls.answer = QMessageBox.StandardButton.Yes
        cls.warnings = []
        cls.infos = []
        cls.criticals = []

    @classmethod
    def warning(cls, _parent, _title, text, *_args) -> QMessageBox.StandardButton:  # noqa: ANN001
        cls.warnings.append(text)
        return cls.answer

    @classmethod
    def information(cls, _parent, _title, text) -> None:  # noqa: ANN001
        cls.infos.append(text)

    @classmethod
    def critical(cls, _parent, _title, text) -> None:  # noqa: ANN001
        cls.criticals.append(text)

    @classmethod
    def question(cls, _parent, _title, _text, *_args) -> QMessageBox.StandardButton:  # noqa: ANN001
        return cls.answer


@pytest.fixture(autouse=True)
def _clean_message_box() -> None:
    _FakeMessageBox.reset()


def _make_order(session: Session, *, serie: str | None = None) -> ServiceOrder:
    order = register_reception(
        session,
        ReceptionData(
            equipment=EquipmentData(
                cliente_id=None,
                tipo_equipo="Laptop",
                marca="Dell",
                modelo="Inspiron 1750",
                numero_serie=serie,
                contrasena_equipo="1234",
                accesorios_recibidos="cargador",
                estado_fisico="Rayón leve en la tapa",
                problema_reportado_cliente="No enciende",
                color="Negro",
                sistema_operativo="Windows 10",
            ),
            new_customer=CustomerData(
                nombre_completo="Jean Carlos",
                numero_identificacion="1301206320",
                telefono_principal="0978907244",
                correo_electronico="jc@correo.com",
            ),
            fecha_ingreso=datetime(2026, 3, 10, 9, 0),
            fecha_estimada_entrega=datetime(2026, 3, 17, 9, 0),
            tecnico_responsable="Ing. Lucio",
            costo_diagnostico=Decimal("100"),
            anticipo=Decimal("20"),
        ),
    )
    session.flush()
    return order


@pytest.fixture
def order_id(session_factory: sessionmaker[Session]) -> int:
    with session_factory() as session:
        order = _make_order(session, serie="SN-1")
        session.commit()
        return order.id


# Términos y condiciones y datos del taller (§5.8)


def test_default_terms_state_the_retention_deadline(session: Session) -> None:
    conditions = service_conditions(session)
    assert f"dentro de {DEFAULT_RETENTION_MONTHS} meses" in conditions
    assert "darlo de baja" in conditions


def test_configured_months_replace_the_placeholder(session: Session) -> None:
    set_retention_months(session, 3)
    assert retention_months(session) == 3
    assert "dentro de 3 meses" in service_conditions(session)
    # El texto guardado conserva el marcador para poder cambiar el plazo después.
    assert "{meses}" in service_terms(session)


def test_custom_terms_are_used(session: Session) -> None:
    set_service_terms(session, "Plazo de retiro: {meses} meses.")
    set_retention_months(session, 12)
    assert service_conditions(session) == "Plazo de retiro: 12 meses."


@pytest.mark.parametrize("raw", ["abc", "0", "-3", ""])
def test_invalid_retention_months_fall_back_to_default(session: Session, raw: str) -> None:
    set_value(session, KEY_RETENTION_MONTHS, raw)
    assert retention_months(session) == DEFAULT_RETENTION_MONTHS


def test_set_retention_months_rejects_zero(session: Session) -> None:
    with pytest.raises(ValueError):
        set_retention_months(session, 0)


def test_blank_terms_fall_back_to_default(session: Session) -> None:
    set_value(session, KEY_SERVICE_TERMS, "   ")
    assert service_terms(session).startswith("1. El taller no responde")


def test_default_terms_are_numbered_without_gaps(session: Session) -> None:
    """Al retirar una condición hay que renumerar las que quedan."""
    numbers = [
        line.split(".", 1)[0] for line in service_conditions(session).splitlines() if line.strip()
    ]
    assert numbers == ["1", "2", "3", "4"]


def test_terms_no_longer_require_the_receipt_to_release_the_equipment(session: Session) -> None:
    """La condición retirada el 2026-10-22 no debe reaparecer en el comprobante."""
    assert "contra presentación" not in service_conditions(session)


def test_workshop_identity_comes_from_configuration(session: Session) -> None:
    set_value(session, KEY_WORKSHOP_PHONE, "0999999999")
    assert workshop_name(session) == "Ing. Lucio"
    assert "0999999999" in workshop_contact(session)


# Filtro de la papelera (§18)


def test_solo_eliminadas_returns_only_deleted_orders(
    session: Session, order_id: int
) -> None:
    extra = _make_order(session)
    soft_delete_order(session, extra, when=datetime(2026, 3, 11, 8, 0))
    session.flush()

    deleted = search_orders(session, OrderFilter(solo_eliminadas=True))
    assert [order.id for order in deleted] == [extra.id]
    assert deleted[0].fecha_eliminacion == datetime(2026, 3, 11, 8, 0)

    active = search_orders(session, OrderFilter())
    assert [order.id for order in active] == [order_id]


def test_incluir_eliminadas_returns_both(session: Session, order_id: int) -> None:
    extra = _make_order(session)
    soft_delete_order(session, extra)
    session.flush()
    ids = {order.id for order in search_orders(session, OrderFilter(incluir_eliminadas=True))}
    assert ids == {order_id, extra.id}


# Borrado lógico con historial (§18)


def test_delete_and_restore_leave_a_trace_in_the_history(session: Session) -> None:
    order = _make_order(session)
    soft_delete_order(session, order, usuario="Ing. Lucio")
    restore_order(session, order, usuario="Ing. Lucio")
    session.flush()
    kinds = [event.tipo_evento for event in order.events]
    assert EventType.ORDEN_ELIMINADA.value in kinds
    assert EventType.ORDEN_RESTAURADA.value in kinds
    assert order.activo is True


def test_delete_without_user_does_not_write_history(session: Session) -> None:
    order = _make_order(session)
    soft_delete_order(session, order)
    session.flush()
    assert order.events == []


# Comprobante de recepción (§13.1.1)


def test_receipt_includes_reception_data_and_terms(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        html = documents.receipt_html(session, order)

    assert "Comprobante de recepción" in html
    assert order.numero_orden in html
    assert "Jean Carlos" in html
    assert "0978907244" in html
    assert "Dell Inspiron 1750" in html
    assert "SN-1" in html
    assert "No enciende" in html
    assert "Rayón leve en la tapa" in html
    assert "cargador" in html
    assert "10/03/2026 09:00" in html
    assert "17/03/2026 09:00" in html
    assert "100.00 USD" in html
    assert "20.00 USD" in html
    assert "95.00 USD" in html
    assert "Términos y condiciones" in html
    assert "dentro de 6 meses" in html
    assert "Firma del cliente" in html
    assert "Firma del taller" in html


def test_receipt_shows_the_same_numbers_as_the_budget_tab(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    """El comprobante y la pestaña «Presupuesto y pagos» salen de la misma fórmula (§5.3)."""
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        add_line(
            session,
            order,
            tipo=BudgetLineType.REPUESTO,
            descripcion="SSD 480 GB",
            cantidad=Decimal("2"),
            precio_unitario=Decimal("50"),
        )
        register_payment(
            session,
            order,
            tipo=PaymentType.ABONO,
            metodo=PaymentMethod.EFECTIVO,
            monto=Decimal("30"),
            usuario="Ing. Lucio",
        )
        session.commit()
        totals = order_totals(order, tax_settings(session))
        html = documents.receipt_html(session, order)

    # subtotal 100 + 100 = 200; IVA 30; total 230; anticipo 20 + abono 30 → saldo 180.
    assert totals.subtotal == Decimal("200.00")
    assert totals.total == Decimal("230.00")
    assert totals.saldo_pendiente == Decimal("180.00")
    assert "Líneas de presupuesto" in html
    assert "100.00 USD" in html
    assert "Pagos recibidos" in html
    assert "30.00 USD" in html
    for amount in (
        totals.subtotal,
        totals.impuestos,
        totals.total,
        totals.saldo_pendiente,
        order.anticipo,
    ):
        assert format_money(amount) in html


def test_receipt_ignores_a_stale_stored_balance(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    """Aunque la columna guardada quede desfasada, el documento muestra el saldo calculado."""
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        order.saldo_pendiente = Decimal("999.99")
        session.commit()
        html = documents.receipt_html(session, order)

    assert "999.99 USD" not in html
    assert "95.00 USD" in html


def test_receipt_always_shows_the_total_even_without_amounts(
    session_factory: sessionmaker[Session],
) -> None:
    """Una orden sin importes imprime el desglose completo con ceros, no una sección vacía."""
    with session_factory() as session:
        order = register_reception(
            session,
            ReceptionData(
                equipment=EquipmentData(cliente_id=None, tipo_equipo="Laptop"),
                new_customer=CustomerData(
                    nombre_completo="Sin Importes", telefono_principal="0991234567"
                ),
                fecha_ingreso=datetime(2026, 3, 10, 9, 0),
            ),
        )
        session.commit()
        html = documents.receipt_html(session, order)

    assert "Valores" in html
    assert "Subtotal" in html
    assert "Total" in html
    assert "Saldo pendiente" in html
    assert "0.00 USD" in html


def test_receipt_never_shows_the_equipment_password(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        html = documents.receipt_html(session, order)
    assert "1234" not in html
    assert "Contraseña" not in html


def test_receipt_escapes_customer_text(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        order = register_reception(
            session,
            ReceptionData(
                equipment=EquipmentData(
                    cliente_id=None,
                    tipo_equipo="Laptop",
                    problema_reportado_cliente="<b>no enciende</b>",
                ),
                new_customer=CustomerData(
                    nombre_completo="<i>Ana</i>", telefono_principal="0991234567"
                ),
                fecha_ingreso=datetime(2026, 3, 10, 9, 0),
            ),
        )
        session.commit()
        html = documents.receipt_html(session, order)
    assert "&lt;i&gt;Ana&lt;/i&gt;" in html
    assert "&lt;b&gt;no enciende&lt;/b&gt;" in html
    assert "<i>Ana</i>" not in html


def test_receipt_limits_photographs(
    session_factory: sessionmaker[Session], order_id: int, tmp_path
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        for index in range(documents.MAX_PHOTOS + 2):
            session.add(
                Photograph(
                    order=order,
                    ruta_archivo=str(tmp_path / f"foto-{index}.jpg"),
                    nombre_archivo=f"foto-{index}.jpg",
                    tipo_fotografia=PhotoType.ESTADO_AL_RECIBIR.value,
                    orden_visualizacion=index,
                )
            )
        session.flush()
        html = documents.receipt_html(session, order)

    assert html.count("<img") == documents.MAX_PHOTOS
    assert "Fotografías del equipo" in html


def test_receipt_without_photos_omits_the_section(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        html = documents.receipt_html(session, order)
    assert "<img" not in html
    assert "Fotografías del equipo" not in html


def test_print_order_receipt_warns_when_order_is_missing(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(documents, "print_document", lambda *_a, **_k: pytest.fail("no debe imprimir"))
    monkeypatch.setattr(documents, "QMessageBox", _FakeMessageBox)
    assert documents.print_order_receipt(session_factory, 999_999) is False
    assert _FakeMessageBox.warnings


# Botones de imprimir y eliminar en el detalle de la orden


def test_detail_dialog_print_button_opens_the_receipt_preview(
    qtbot: QtBot,
    session_factory: sessionmaker[Session],
    order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        documents,
        "print_document",
        lambda html, _parent, title: calls.append((html, title)),
    )
    dialog = OrderDetailDialog(session_factory, order_id, "Ing. Lucio")
    qtbot.addWidget(dialog)

    dialog._print_button.click()

    assert len(calls) == 1
    html, title = calls[0]
    assert title == "Comprobante de recepción"
    assert "Comprobante de recepción" in html
    assert dialog._message.text() == "Vista previa del comprobante de recepción."


def test_detail_dialog_delete_button_moves_order_to_the_trash(
    qtbot: QtBot,
    session_factory: sessionmaker[Session],
    order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "luciotech.ui.dialogs.order_detail_dialog.QMessageBox", _FakeMessageBox
    )
    dialog = OrderDetailDialog(session_factory, order_id, "Ing. Lucio")
    qtbot.addWidget(dialog)

    dialog._delete_button.click()

    assert _FakeMessageBox.warnings
    assert dialog.result() == QDialog.DialogCode.Rejected
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        assert order.activo is False
        assert order.fecha_eliminacion is not None


def test_detail_dialog_delete_button_can_be_cancelled(
    qtbot: QtBot,
    session_factory: sessionmaker[Session],
    order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeMessageBox.answer = QMessageBox.StandardButton.No
    monkeypatch.setattr(
        "luciotech.ui.dialogs.order_detail_dialog.QMessageBox", _FakeMessageBox
    )
    dialog = OrderDetailDialog(session_factory, order_id, "Ing. Lucio")
    qtbot.addWidget(dialog)

    dialog._delete_button.click()

    with session_factory() as session:
        assert session.get(ServiceOrder, order_id).activo is True


# Botón de eliminar en la lista de órdenes


def test_orders_page_delete_button_soft_deletes_the_selected_order(
    qtbot: QtBot,
    session_factory: sessionmaker[Session],
    order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(orders_page_module, "QMessageBox", _FakeMessageBox)
    page = OrdersPage(session_factory)
    qtbot.addWidget(page)
    assert page.visible_row_count() == 1

    page._table.setCurrentCell(0, 0)
    page._delete_button.click()

    assert _FakeMessageBox.warnings
    assert page.visible_row_count() == 0
    with session_factory() as session:
        assert session.get(ServiceOrder, order_id).activo is False


def test_orders_page_delete_without_selection_only_warns(
    qtbot: QtBot,
    session_factory: sessionmaker[Session],
    order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(orders_page_module, "QMessageBox", _FakeMessageBox)
    page = OrdersPage(session_factory)
    qtbot.addWidget(page)
    page._table.clearSelection()
    page._table.setCurrentCell(-1, -1)

    page._delete_button.click()

    assert _FakeMessageBox.infos
    with session_factory() as session:
        assert session.get(ServiceOrder, order_id).activo is True


def test_orders_page_follow_up_prints_the_receipt(
    qtbot: QtBot,
    session_factory: sessionmaker[Session],
    order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    printed: list[int] = []
    monkeypatch.setattr(orders_page_module, "QMessageBox", _FakeMessageBox)
    monkeypatch.setattr(
        orders_page_module, "print_order_receipt", lambda _f, oid, _p: printed.append(oid)
    )
    page = OrdersPage(session_factory)
    qtbot.addWidget(page)

    page._offer_follow_up(order_id, "OT-2026-000001")

    assert printed == [order_id]


# Papelera (§18)


def test_trash_page_lists_and_restores_orders(
    qtbot: QtBot,
    session_factory: sessionmaker[Session],
    order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with session_factory() as session:
        soft_delete_order(session, session.get(ServiceOrder, order_id), usuario="Ing. Lucio")
        session.commit()

    monkeypatch.setattr(trash_page_module, "QMessageBox", _FakeMessageBox)
    page = TrashPage(session_factory)
    qtbot.addWidget(page)

    assert page.visible_row_count() == 1
    assert page._restore_button.isEnabled()
    number = page.order_number_at(0)

    page._table.setCurrentCell(0, 0)
    page.restore_selected()

    assert page.visible_row_count() == 0
    assert not page._restore_button.isEnabled()
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        assert order.activo is True
        assert order.fecha_eliminacion is None
        assert order.numero_orden == number


def test_trash_page_without_orders_disables_restore(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    page = TrashPage(session_factory)
    qtbot.addWidget(page)
    assert page.visible_row_count() == 0
    assert not page._restore_button.isEnabled()


def test_trash_page_restore_without_selection_warns(
    qtbot: QtBot,
    session_factory: sessionmaker[Session],
    order_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with session_factory() as session:
        soft_delete_order(session, session.get(ServiceOrder, order_id))
        session.commit()

    monkeypatch.setattr(trash_page_module, "QMessageBox", _FakeMessageBox)
    page = TrashPage(session_factory)
    qtbot.addWidget(page)
    page._table.clearSelection()
    page._table.setCurrentCell(-1, -1)

    page.restore_selected()

    assert _FakeMessageBox.infos
    assert page.visible_row_count() == 1
