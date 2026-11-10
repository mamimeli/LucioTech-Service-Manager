"""Pruebas de los documentos imprimibles de una orden (§13.1)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from PyQt6.QtCore import QRect, Qt
from PyQt6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot
from sqlalchemy.orm import Session, sessionmaker

from luciotech.database.enums import (
    BudgetLineType,
    OrderState,
    PaymentMethod,
    PaymentType,
    PhotoType,
)
from luciotech.database.models import Photograph, ServiceOrder
from luciotech.services.budget_service import add_line
from luciotech.services.clinical_text_service import ClinicalTexts, save_clinical_texts
from luciotech.services.customer_service import CustomerData
from luciotech.services.equipment_service import EquipmentData
from luciotech.services.order_detail_service import register_payment
from luciotech.services.reception_service import ReceptionData, register_reception
from luciotech.services.settings_service import (
    KEY_TAX_ENABLED,
    set_retention_months,
    set_service_terms,
    set_value,
    set_warranty_days,
    set_warranty_terms,
    tax_settings,
)
from luciotech.services.state_service import change_order_state
from luciotech.services.totals_service import order_totals
from luciotech.ui import documents
from luciotech.ui.dialogs.document_chooser_dialog import DESCRIPTIONS, DocumentChooserDialog
from luciotech.ui.documents import DocumentKind
from luciotech.ui.formatting import format_money
from luciotech.ui.print_support import PREVIEW_MIN_HEIGHT, PREVIEW_MIN_WIDTH, preview_size

ENTRY = datetime(2026, 3, 10, 9, 0)
USER = "Ing. Lucio"


class _FakeMessageBox:
    warnings: list[str] = []

    @classmethod
    def warning(cls, _parent: object, _title: str, text: str) -> None:
        cls.warnings.append(text)


class _Signal:
    def connect(self, _slot: object) -> None:
        pass


class _FakePreview:
    """Vista previa de mentira: apunta el tamaño y el título en vez de abrir una ventana."""

    instances: list["_FakePreview"] = []

    def __init__(self, _printer: object, _parent: object = None) -> None:
        self.title = ""
        self.size: tuple[int, int] | None = None
        self.minimum: tuple[int, int] | None = None
        self.position: tuple[int, int] | None = None
        self.executed = False
        self.maximizable = False
        self.maximized = False
        self.paintRequested = _Signal()
        type(self).instances.append(self)

    def setWindowFlag(self, flag: object, on: bool = True) -> None:
        if flag == Qt.WindowType.WindowMinMaxButtonsHint:
            self.maximizable = on

    def setWindowState(self, state: object) -> None:
        self.maximized = bool(state & Qt.WindowState.WindowMaximized)

    def windowState(self) -> Qt.WindowState:
        return Qt.WindowState.WindowMaximized if self.maximized else Qt.WindowState.WindowNoState

    def findChild(self, *_args: object) -> None:
        """La vista previa de mentira no tiene el widget de Qt: el zoom no se toca."""
        return None

    def setWindowTitle(self, title: str) -> None:
        self.title = title

    def setMinimumSize(self, width: int, height: int) -> None:
        self.minimum = (width, height)

    def resize(self, width: int, height: int) -> None:
        self.size = (width, height)

    def move(self, x: int, y: int) -> None:
        self.position = (x, y)

    def exec(self) -> int:
        self.executed = True
        return 0


@pytest.fixture
def order_id(session_factory: sessionmaker[Session]) -> int:
    """Orden con diagnóstico 100, anticipo 20, dos líneas y 30 días de garantía.

    Subtotal 215.00 (100 + 100 de repuestos + 15 de mano de obra), sin IVA, saldo 195.00.
    """
    with session_factory() as session:
        order = register_reception(
            session,
            ReceptionData(
                equipment=EquipmentData(
                    cliente_id=None, tipo_equipo="Laptop", marca="Dell", modelo="Inspiron 1750",
                    numero_serie="SN-1", estado_fisico="Rayón leve", accesorios_recibidos="cargador",
                ),
                new_customer=CustomerData(
                    nombre_completo="Ana Torres", numero_identificacion="1301206320",
                    telefono_principal="0991234567",
                ),
                fecha_ingreso=ENTRY,
                tecnico_responsable=USER,
                costo_diagnostico=Decimal("100"),
                anticipo=Decimal("20"),
            ),
        )
        add_line(
            session, order, tipo=BudgetLineType.REPUESTO, descripcion="SSD 480 GB",
            cantidad=Decimal("2"), precio_unitario=Decimal("50"),
        )
        add_line(
            session, order, tipo=BudgetLineType.MANO_OBRA, descripcion="Cambio de disco",
            cantidad=Decimal("1"), precio_unitario=Decimal("15"),
        )
        order.garantia_dias = 30
        session.commit()
        return order.id


def _html(session_factory: sessionmaker[Session], order_id: int, build) -> str:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        assert order is not None
        return build(session, order)


def _edit(session_factory: sessionmaker[Session], order_id: int, change) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        assert order is not None
        change(session, order)
        session.commit()


# Presupuesto (§13.1.3)


def test_budget_lists_every_concept_with_quantity_and_price(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    html = _html(session_factory, order_id, documents.budget_html)

    assert "Presupuesto" in html
    assert "Detalle del presupuesto" in html
    assert "Costo de diagnóstico" in html
    assert "Repuesto: SSD 480 GB" in html
    assert "Mano de obra: Cambio de disco" in html
    # Los dos costos fantasma de la Fase 1 se eliminaron en la migración 0004: el detalle de
    # repuestos y mano de obra son las líneas de presupuesto, no dos columnas de la orden.
    assert "Costo de repuestos" not in html
    assert ">Mano de obra</td>" not in html
    # 2 unidades a 50.00 son 100.00; la línea de mano de obra es 1 a 15.00.
    assert "50.00 USD" in html
    assert "100.00 USD" in html
    assert "15.00 USD" in html


def test_budget_totals_come_from_the_shared_formula(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        totals = order_totals(order, tax_settings(session))
        html = documents.budget_html(session, order)

    assert totals.subtotal == Decimal("215.00")
    assert totals.total == Decimal("215.00")
    for amount in (totals.subtotal, totals.total):
        assert format_money(amount) in html


def test_budget_is_a_quote_and_does_not_list_payments(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    """El presupuesto es una oferta: no imprime anticipos, pagos ni saldo."""
    html = _html(session_factory, order_id, documents.budget_html)

    assert "Pagos recibidos" not in html
    assert "Saldo pendiente" not in html
    assert "Anticipo recibido" not in html


def test_budget_states_its_validity_and_leaves_room_for_approval(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    html = _html(session_factory, order_id, documents.budget_html)

    assert "válido por 15 días desde el 10/03/2026 09:00" in html
    assert "Aprobación del cliente" in html
    assert documents.SIGNATURE in html


def test_budget_prints_the_tax_only_when_it_is_switched_on(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    assert "IVA" not in _html(session_factory, order_id, documents.budget_html)

    _edit(session_factory, order_id, lambda session, _order: set_value(session, KEY_TAX_ENABLED, "true"))
    html = _html(session_factory, order_id, documents.budget_html)

    assert "IVA (15%)" in html
    assert "32.25 USD" in html


# Informe técnico (§13.1.2)


def test_technical_report_includes_the_clinical_texts(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    def write(session: Session, order: ServiceOrder) -> None:
        save_clinical_texts(
            session,
            order,
            ClinicalTexts(
                diagnostico_html="<p>Disco con sectores defectuosos.</p>",
                trabajo_realizado_html="<p>Se reemplazó el disco por un SSD.</p>",
                recomendaciones_html="<p>Respaldar la información cada mes.</p>",
            ),
        )

    _edit(session_factory, order_id, write)
    html = _html(session_factory, order_id, documents.technical_report_html)

    assert "Informe técnico" in html
    assert "Diagnóstico técnico" in html
    assert "Disco con sectores defectuosos." in html
    assert "Trabajo realizado" in html
    assert "Se reemplazó el disco por un SSD." in html
    assert "Recomendaciones" in html
    assert "Respaldar la información cada mes." in html


def test_technical_report_lists_the_parts_of_the_budget(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    html = _html(session_factory, order_id, documents.technical_report_html)

    assert "Repuestos utilizados" in html
    assert "2 × SSD 480 GB" in html


def test_technical_report_keeps_the_free_text_of_parts_when_present(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    _edit(
        session_factory,
        order_id,
        lambda _session, order: setattr(order, "repuestos_utilizados", "Teclado en español"),
    )
    html = _html(session_factory, order_id, documents.technical_report_html)

    assert "Teclado en español" in html
    assert "2 × SSD 480 GB" not in html


def test_technical_report_separates_before_and_after_photographs(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    def add_photos(session: Session, order: ServiceOrder) -> None:
        for index, kind in enumerate(
            (PhotoType.ESTADO_AL_RECIBIR, PhotoType.EQUIPO_REPARADO), start=1
        ):
            session.add(
                Photograph(
                    orden_id=order.id,
                    ruta_archivo=f"C:/fotos/{kind.name.lower()}.jpg",
                    nombre_archivo=f"{kind.name.lower()}.jpg",
                    tipo_fotografia=kind.value,
                    orden_visualizacion=index,
                )
            )

    _edit(session_factory, order_id, add_photos)
    html = _html(session_factory, order_id, documents.technical_report_html)

    assert "Fotografías del equipo al recibir" in html
    assert "Fotografías del equipo reparado" in html
    assert "estado_al_recibir.jpg" in html
    assert "equipo_reparado.jpg" in html


def test_technical_report_shows_the_warranty_and_the_amounts(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    html = _html(session_factory, order_id, documents.technical_report_html)

    assert "30 días" in html
    assert "215.00 USD" in html
    assert "195.00 USD" in html


# Comprobante de entrega (§13.1.4)


def test_delivery_lists_payments_and_balance(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    def pay(session: Session, order: ServiceOrder) -> None:
        register_payment(
            session, order, tipo=PaymentType.ABONO, metodo=PaymentMethod.EFECTIVO,
            monto=Decimal("30"), usuario=USER,
        )

    _edit(session_factory, order_id, pay)
    html = _html(session_factory, order_id, documents.delivery_html)

    assert "Comprobante de entrega" in html
    assert "Pagos" in html
    assert "30.00 USD" in html
    assert "Vigente" in html
    assert "165.00 USD" in html  # saldo: 215 - 20 de anticipo - 30 de abono
    assert "Declaración de conformidad" in html
    assert "Firma del cliente" in html


def test_delivery_marks_voided_payments(session_factory: sessionmaker[Session], order_id: int) -> None:
    def pay_and_void(session: Session, order: ServiceOrder) -> None:
        payment = register_payment(
            session, order, tipo=PaymentType.ABONO, metodo=PaymentMethod.EFECTIVO,
            monto=Decimal("30"), usuario=USER,
        )
        payment.anulado = True

    _edit(session_factory, order_id, pay_and_void)
    html = _html(session_factory, order_id, documents.delivery_html)

    assert "Anulado" in html


def test_delivery_says_when_the_workshop_disables_the_warranty(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    """Cero días en la configuración es la única forma de no dar garantía."""
    _edit(session_factory, order_id, lambda session, _order: set_warranty_days(session, 0))
    html = _html(session_factory, order_id, documents.delivery_html)

    assert "Sin garantía registrada" in html


# Historial completo (§13.1.5)


def test_history_lists_the_movements_in_chronological_order(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    def move(session: Session, order: ServiceOrder) -> None:
        change_order_state(session, order, OrderState.EN_REPARACION, usuario=USER)
        change_order_state(session, order, OrderState.REPARADO, usuario=USER)

    _edit(session_factory, order_id, move)
    html = _html(session_factory, order_id, documents.history_html)

    assert "Historial completo" in html
    assert "Movimientos" in html
    table = html[html.index("Movimientos") :]
    first = table.index(OrderState.EN_REPARACION.value)
    second = table.index(OrderState.REPARADO.value)
    assert first < second


# Textos legales configurables (§5.8 y §13.1)

CUSTOMER_DOCUMENTS = (
    documents.receipt_html,
    documents.budget_html,
    documents.technical_report_html,
    documents.delivery_html,
)


@pytest.mark.parametrize("build", CUSTOMER_DOCUMENTS, ids=lambda build: build.__name__)
def test_every_customer_document_prints_the_terms_and_the_warranty(
    session_factory: sessionmaker[Session], order_id: int, build
) -> None:
    html = _html(session_factory, order_id, build)

    assert "Términos y condiciones" in html
    assert "Condiciones de garantía" in html
    assert "30 días" in html


def test_the_internal_history_does_not_print_the_legal_texts(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    html = _html(session_factory, order_id, documents.history_html)

    assert "Términos y condiciones" not in html
    assert "Condiciones de garantía" not in html


@pytest.mark.parametrize("build", CUSTOMER_DOCUMENTS, ids=lambda build: build.__name__)
def test_the_legal_texts_come_from_the_configuration(
    session_factory: sessionmaker[Session], order_id: int, build
) -> None:
    with session_factory() as session:
        set_service_terms(session, "Condición única del taller")
        set_warranty_terms(session, "Garantía escrita por el taller")
        session.commit()

    html = _html(session_factory, order_id, build)

    assert "Condición única del taller" in html
    assert "Garantía escrita por el taller" in html
    assert "La reparación se inicia" not in html


def test_the_legal_placeholders_are_replaced_when_printing(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        set_service_terms(session, "Retirar en {meses} meses.")
        set_retention_months(session, 9)
        set_warranty_terms(session, "Cubre {dias} días de la orden {orden}.")
        session.commit()
        order = session.get(ServiceOrder, order_id)
        assert order is not None
        number = order.numero_orden

    html = _html(session_factory, order_id, documents.technical_report_html)

    assert "Retirar en 9 meses." in html
    assert f"Cubre 30 días de la orden {number}." in html
    assert "{dias}" not in html
    assert "{meses}" not in html
    assert "{orden}" not in html


def test_a_multiline_legal_text_keeps_its_lines(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        set_service_terms(session, "Primera línea\nSegunda línea")
        session.commit()

    html = _html(session_factory, order_id, documents.receipt_html)

    assert "Primera línea<br/>Segunda línea" in html


def test_the_legal_texts_are_escaped_before_printing(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        set_service_terms(session, "Acepto <script>alerta</script> & todo")
        set_warranty_terms(session, "Cubre <b>30</b> días")
        session.commit()

    html = _html(session_factory, order_id, documents.delivery_html)

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&amp; todo" in html
    assert "&lt;b&gt;30&lt;/b&gt;" in html


def test_a_blank_warranty_text_removes_only_that_block(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        set_warranty_terms(session, "  ")
        session.commit()

    html = _html(session_factory, order_id, documents.delivery_html)

    assert "Condiciones de garantía" not in html
    assert "Términos y condiciones" in html
    assert "30 días" in html


def test_a_workshop_with_zero_warranty_days_prints_no_warranty_conditions(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    _edit(session_factory, order_id, lambda session, _order: set_warranty_days(session, 0))

    html = _html(session_factory, order_id, documents.technical_report_html)

    assert "Condiciones de garantía" not in html
    assert "Sin garantía registrada" in html
    assert "Términos y condiciones" in html


def test_an_old_order_without_its_own_days_uses_the_workshop_warranty(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    """Las órdenes guardadas antes de la configuración tienen 0 días y deben imprimir la garantía."""
    _edit(session_factory, order_id, lambda _session, order: setattr(order, "garantia_dias", 0))

    html = _html(session_factory, order_id, documents.technical_report_html)

    assert "Sin garantía registrada" not in html
    assert ">30 días<" in html
    assert "Condiciones de garantía" in html
    assert "durante 30 días" in html


@pytest.mark.parametrize("build", CUSTOMER_DOCUMENTS, ids=lambda build: build.__name__)
def test_the_workshop_warranty_reaches_every_document_of_an_old_order(
    session_factory: sessionmaker[Session], order_id: int, build
) -> None:
    _edit(session_factory, order_id, lambda _session, order: setattr(order, "garantia_dias", 0))

    html = _html(session_factory, order_id, build)

    assert "Condiciones de garantía" in html
    assert "durante 30 días" in html
    assert "Sin garantía registrada" not in html


def test_a_specific_order_keeps_its_own_warranty_days(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        set_warranty_days(session, 90)
        session.commit()

    html = _html(session_factory, order_id, documents.technical_report_html)

    assert ">30 días<" in html
    assert "90 días" not in html


# Selector y despacho


def test_document_html_rejects_an_unknown_kind(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        with pytest.raises(ValueError):
            documents.document_html(session, order, "Carta al cliente")


def test_document_html_serves_every_kind(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        for kind in DocumentKind:
            html = documents.document_html(session, order, kind)
            assert kind.value in html


def test_chooser_lists_every_document_and_returns_the_selected_one(qtbot: QtBot) -> None:
    dialog = DocumentChooserDialog()
    qtbot.addWidget(dialog)

    assert dialog._list.count() == len(DocumentKind)
    assert dialog.selected_kind() == DocumentKind.RECEPCION
    assert dialog._description.text() == DESCRIPTIONS[DocumentKind.RECEPCION]

    dialog.select(DocumentKind.INFORME)
    assert dialog.selected_kind() == DocumentKind.INFORME
    assert "Diagnóstico" in dialog._description.text()


def test_print_order_document_warns_when_the_order_is_missing(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(documents, "print_document", lambda *_a, **_k: pytest.fail("no debe imprimir"))
    monkeypatch.setattr(documents, "QMessageBox", _FakeMessageBox)
    _FakeMessageBox.warnings.clear()

    assert documents.print_order_document(session_factory, 999_999, DocumentKind.ENTREGA) is False
    assert _FakeMessageBox.warnings


# Vista previa de impresión (§13.3)


def test_preview_size_uses_most_of_a_large_screen() -> None:
    assert preview_size(QRect(0, 0, 1920, 1080)) == (1500, 972)


def test_preview_size_keeps_a_usable_minimum_on_a_small_screen() -> None:
    assert preview_size(QRect(0, 0, 800, 600)) == (PREVIEW_MIN_WIDTH, PREVIEW_MIN_HEIGHT)


def test_print_document_opens_the_preview_large_and_centred(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La vista previa de Qt se abre pequeña; aquí se le fija el tamaño de la pantalla."""
    created: list[_FakePreview] = []
    monkeypatch.setattr(documents, "QPrintPreviewDialog", _FakePreview)
    monkeypatch.setattr(_FakePreview, "instances", created, raising=False)

    documents.print_document("<p>Presupuesto</p>", None, "Presupuesto")

    preview = created[0]
    screen = QApplication.primaryScreen()
    assert screen is not None
    assert preview.title == "Presupuesto"
    assert preview.size == preview_size(screen.availableGeometry())
    assert preview.minimum == (PREVIEW_MIN_WIDTH, PREVIEW_MIN_HEIGHT)
    assert preview.position is not None
    assert preview.maximizable
    assert preview.maximized
    assert preview.executed
