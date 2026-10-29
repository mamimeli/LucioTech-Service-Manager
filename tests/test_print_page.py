"""Pruebas de la hoja, el encabezado, el pie y el PDF de los documentos (§13.2)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPageLayout, QPageSize
from PyQt6.QtPrintSupport import QPrintPreviewDialog, QPrinter
from PyQt6.QtWidgets import QApplication
from sqlalchemy.orm import Session, sessionmaker

from luciotech.config import (
    DEFAULT_PAGE_MARGIN_MM,
    DEFAULT_PAPER_SIZE,
    MAX_PAGE_MARGIN_MM,
    MIN_PAGE_MARGIN_MM,
)
from luciotech.database.models import ServiceOrder
from luciotech.services.customer_service import CustomerData
from luciotech.services.equipment_service import EquipmentData
from luciotech.services.reception_service import ReceptionData, register_reception
from luciotech.services.settings_service import (
    KEY_PAGE_MARGIN_MM,
    page_margin_mm,
    paper_size,
    set_page_margin_mm,
    set_paper_size,
    set_value,
)
from luciotech.ui import documents
from luciotech.ui.documents import DocumentKind
from luciotech.ui.print_support import (
    PageFurniture,
    apply_page_setup,
    page_size_id,
    save_as_pdf,
    scale_lengths,
    size_preview,
)

ENTRY = datetime(2026, 3, 10, 9, 0)
USER = "Ing. Lucio"
# 120 párrafos no caben en una hoja A4: sirven para comprobar que el documento se parte.
LONG_DOCUMENT = "".join(
    f"<p>Línea {index} del informe técnico con texto suficiente para ocupar un renglón.</p>"
    for index in range(120)
)


@pytest.fixture(autouse=True)
def _qt_app(qapp: QApplication) -> QApplication:
    """QPrinter necesita una QApplication viva: sin ella el proceso muere al instante."""
    return qapp


@pytest.fixture(autouse=True)
def _qt_app(qapp: QApplication) -> QApplication:
    """QPrinter necesita una QApplication viva: sin ella el proceso muere al instante."""
    return qapp


@pytest.fixture
def order_id(session_factory: sessionmaker[Session]) -> int:
    """Orden con nombre acentuado, para probar el nombre del archivo."""
    with session_factory() as session:
        order = register_reception(
            session,
            ReceptionData(
                equipment=EquipmentData(cliente_id=None, tipo_equipo="Laptop", marca="Dell"),
                new_customer=CustomerData(
                    nombre_completo="José Núñez", numero_identificacion="1301206320"
                ),
                fecha_ingreso=ENTRY,
                tecnico_responsable=USER,
                costo_diagnostico=Decimal("100"),
            ),
        )
        session.commit()
        return order.id


def _pdf_pages(path: Path) -> int:
    """Cuenta las hojas leyendo los objetos del PDF (no hay lector de PDF en el entorno)."""
    data = path.read_bytes()
    assert data.startswith(b"%PDF")
    return data.count(b"/Type /Page") - data.count(b"/Type /Pages")


def _printer(paper: str = DEFAULT_PAPER_SIZE, margin_mm: int = DEFAULT_PAGE_MARGIN_MM) -> QPrinter:
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    apply_page_setup(printer, paper, margin_mm)
    return printer


# Hoja y márgenes (§13.2)


def test_page_setup_defaults_to_a4_with_fifteen_millimetres() -> None:
    printer = _printer()

    layout = printer.pageLayout()
    margins = layout.margins(QPageLayout.Unit.Millimeter)

    assert layout.pageSize().id() == QPageSize.PageSizeId.A4
    assert layout.orientation() == QPageLayout.Orientation.Portrait
    assert round(margins.left()) == DEFAULT_PAGE_MARGIN_MM
    assert round(margins.top()) == DEFAULT_PAGE_MARGIN_MM


def test_page_setup_accepts_letter_and_custom_margins() -> None:
    layout = _printer("Carta", 22).pageLayout()

    assert layout.pageSize().id() == QPageSize.PageSizeId.Letter
    assert round(layout.margins(QPageLayout.Unit.Millimeter).right()) == 22


def test_an_unknown_paper_falls_back_to_a4() -> None:
    assert page_size_id("Oficio") == QPageSize.PageSizeId.A4
    assert page_size_id("carta") == QPageSize.PageSizeId.Letter


def test_paper_size_defaults_to_a4(session: Session) -> None:
    assert paper_size(session) == DEFAULT_PAPER_SIZE


def test_paper_size_is_saved_regardless_of_the_case(session: Session) -> None:
    set_paper_size(session, "carta")

    assert paper_size(session) == "Carta"


def test_an_unknown_paper_is_rejected(session: Session) -> None:
    with pytest.raises(ValueError):
        set_paper_size(session, "Oficio")


def test_page_margin_defaults_to_fifteen_millimetres(session: Session) -> None:
    assert page_margin_mm(session) == DEFAULT_PAGE_MARGIN_MM


def test_page_margin_is_saved(session: Session) -> None:
    set_page_margin_mm(session, 20)

    assert page_margin_mm(session) == 20


def test_a_stored_margin_out_of_range_falls_back_to_the_default(session: Session) -> None:
    set_value(session, KEY_PAGE_MARGIN_MM, str(MAX_PAGE_MARGIN_MM + 100))

    assert page_margin_mm(session) == DEFAULT_PAGE_MARGIN_MM


def test_a_margin_out_of_range_is_rejected(session: Session) -> None:
    for value in (MIN_PAGE_MARGIN_MM - 1, MAX_PAGE_MARGIN_MM + 1):
        with pytest.raises(ValueError):
            set_page_margin_mm(session, value)


# Encabezado y pie (§13.2)


def test_furniture_repeats_the_workshop_the_document_and_the_order(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        assert order is not None
        furniture = documents._furniture(session, order, DocumentKind.PRESUPUESTO)

    assert furniture.header_left.startswith("Ing. Lucio")
    assert furniture.header_right == f"Presupuesto · {order.numero_orden}"
    assert furniture.footer_left.startswith("Generado el ")
    assert "10/03/2026" not in furniture.footer_left


# Nombre descriptivo del PDF (§13.2)


def test_pdf_name_is_descriptive_and_has_no_accents(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        assert order is not None
        name = documents.pdf_filename(order, DocumentKind.INFORME)

    assert name == f"{order.numero_orden}_Jose-Nunez_Informe-Tecnico.pdf"


def test_every_document_has_its_own_file_stem() -> None:
    stems = {kind.file_stem for kind in DocumentKind}

    assert len(stems) == len(DocumentKind)
    assert all(stem and " " not in stem for stem in stems)


def test_an_empty_customer_name_still_gives_a_file_name(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        assert order is not None
        order.customer.nombre_completo = "  "
        name = documents.pdf_filename(order, DocumentKind.ENTREGA)

    assert name.endswith("_Cliente_Comprobante-Entrega.pdf")


# Impresión desde la orden


def test_print_order_document_sends_the_paper_the_furniture_and_the_name(
    session_factory: sessionmaker[Session], order_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def fake_print(html: str, _parent: object, title: str, **options: object) -> None:
        captured["title"] = title
        captured.update(options)

    monkeypatch.setattr(documents, "print_document", fake_print)

    assert documents.print_order_document(
        session_factory, order_id, DocumentKind.PRESUPUESTO
    )

    assert captured["title"] == "Presupuesto"
    assert captured["paper"] == DEFAULT_PAPER_SIZE
    assert captured["margin_mm"] == DEFAULT_PAGE_MARGIN_MM
    assert str(captured["pdf_name"]).endswith("_Jose-Nunez_Presupuesto.pdf")
    furniture = captured["furniture"]
    assert isinstance(furniture, PageFurniture)
    assert furniture.header_right.startswith("Presupuesto · OT-")


def test_print_order_document_uses_the_configured_paper(
    session_factory: sessionmaker[Session], order_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    with session_factory() as session:
        set_paper_size(session, "Carta")
        set_page_margin_mm(session, 20)
        session.commit()

    captured: dict[str, object] = {}
    monkeypatch.setattr(
        documents,
        "print_document",
        lambda _html, _parent, _title, **options: captured.update(options),
    )

    assert documents.print_order_document(session_factory, order_id, DocumentKind.INFORME)
    assert captured["paper"] == "Carta"
    assert captured["margin_mm"] == 20


# PDF (§13.2)


def test_save_as_pdf_writes_a_one_page_file(tmp_path: Path) -> None:
    target = tmp_path / "OT-2026-000001_Ana-Torres_Presupuesto.pdf"

    assert save_as_pdf(
        _printer(), "<p>Presupuesto del equipo</p>", PageFurniture(), target
    )
    assert _pdf_pages(target) == 1


def test_save_as_pdf_splits_a_long_document_and_keeps_the_letterhead(
    tmp_path: Path,
) -> None:
    target = tmp_path / "informe.pdf"
    furniture = PageFurniture(
        header_left="Ing. Lucio",
        header_right="Informe técnico · OT-2026-000001",
        footer_left="Generado el 10/03/2026 09:00",
    )

    assert save_as_pdf(_printer(), LONG_DOCUMENT, furniture, target)
    assert _pdf_pages(target) >= 2
    assert target.stat().st_size > 0


# Espaciados de las plantillas


def test_margins_and_paddings_in_points_are_scaled_to_pixels() -> None:
    """Qt deja en cero los márgenes en puntos: sin esta conversión las secciones se pegan."""
    html = '<p style="margin: 10pt 0 2pt 0;"><b>Título</b></p><td style="padding: 2pt 4pt;">x</td>'

    scaled = scale_lengths(html)

    assert "margin: 13.33px 0 2.67px 0" in scaled
    assert "padding: 2.67px 5.33px" in scaled
    assert "10pt" not in scaled


def test_scaling_keeps_pixel_values_and_font_sizes() -> None:
    html = '<p style="margin-top: 40px; font-size: 15pt;">Hola</p>'

    assert scale_lengths(html) == html


# Espaciados de las plantillas


def test_margins_and_paddings_in_points_are_scaled_to_pixels() -> None:
    """Qt deja en cero los márgenes en puntos: sin esta conversión las secciones se pegan."""
    html = '<p style="margin: 10pt 0 2pt 0;"><b>Título</b></p><td style="padding: 2pt 4pt;">x</td>'

    scaled = scale_lengths(html)

    assert "margin: 13.33px 0 2.67px 0" in scaled
    assert "padding: 2.67px 5.33px" in scaled
    assert "10pt" not in scaled


def test_scaling_keeps_pixel_values_and_font_sizes() -> None:
    html = '<p style="margin-top: 40px; font-size: 15pt;">Hola</p>'

    assert scale_lengths(html) == html


def test_the_preview_offers_minimise_and_maximise_buttons() -> None:
    """Un QDialog sale solo con la cruz de cerrar; la vista previa necesita los tres botones."""
    preview = QPrintPreviewDialog(_printer(), None)

    size_preview(preview, None)

    flags = preview.windowFlags()
    assert flags & Qt.WindowType.WindowMinMaxButtonsHint
    assert flags & Qt.WindowType.WindowCloseButtonHint


def test_the_preview_offers_minimise_and_maximise_buttons() -> None:
    """Un QDialog sale solo con la cruz de cerrar; la vista previa necesita los tres botones."""
    preview = QPrintPreviewDialog(_printer(), None)

    size_preview(preview, None)

    flags = preview.windowFlags()
    assert flags & Qt.WindowType.WindowMinMaxButtonsHint
    assert flags & Qt.WindowType.WindowCloseButtonHint
