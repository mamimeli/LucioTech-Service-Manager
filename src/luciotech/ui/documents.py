"""Documentos imprimibles de una orden (§13.1).

Cinco documentos: comprobante de recepción, presupuesto, informe técnico, comprobante de
entrega e historial completo. Se arman como HTML y se imprimen con los diálogos de Qt
(§13.3). La contraseña del equipo nunca aparece: los documentos se entregan al cliente (§5.2).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtPrintSupport import QPrintPreviewDialog, QPrinter
from PyQt6.QtWidgets import QMessageBox, QWidget
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from luciotech.config import DEFAULT_PAGE_MARGIN_MM, DEFAULT_PAPER_SIZE
from luciotech.database.enums import BudgetLineType, PhotoType
from luciotech.database.models import Photograph, ServiceOrder
from luciotech.services.order_detail_service import order_timeline, payments_for_order
from luciotech.services.settings_service import (
    budget_validity_days,
    page_margin_mm,
    paper_size,
    service_conditions,
    tax_settings,
    workshop_contact,
    workshop_name,
)
from luciotech.services.totals_service import OrderTotals, order_totals
from luciotech.ui.formatting import format_datetime, format_money
from luciotech.ui.print_support import (
    PageFurniture,
    add_pdf_action,
    apply_page_setup,
    render_document,
    size_preview,
)

MAX_PHOTOS = 4
EMPTY = "—"
SIGNATURE = "____________________________"
ZERO = Decimal("0.00")
_CONTEXT = "LucioTech"
_BEFORE = (
    PhotoType.ESTADO_AL_RECIBIR,
    PhotoType.DANO_FISICO,
    PhotoType.ACCESORIOS,
    PhotoType.NUMERO_DE_SERIE,
)
_AFTER = (PhotoType.PROCESO_DE_REPARACION, PhotoType.EQUIPO_REPARADO)
_HEAD_CELL = "padding: 1pt 4pt; border-bottom: 1pt solid #000000;"
_CELL = "padding: 0.5pt 4pt; vertical-align: top;"
_RIGHT = " text-align: right;"


class DocumentKind(StrEnum):
    """Tipos de documento que se pueden imprimir de una orden (§13.1)."""

    RECEPCION = "Comprobante de recepción"
    PRESUPUESTO = "Presupuesto"
    INFORME = "Informe técnico"
    ENTREGA = "Comprobante de entrega"
    HISTORIAL = "Historial completo"

    @property
    def file_stem(self) -> str:
        """Parte descriptiva del nombre del PDF: «Informe-Tecnico» (§13.2)."""
        return _FILE_STEMS[self]


_FILE_STEMS: dict[DocumentKind, str] = {
    DocumentKind.RECEPCION: "Comprobante-Recepcion",
    DocumentKind.PRESUPUESTO: "Presupuesto",
    DocumentKind.INFORME: "Informe-Tecnico",
    DocumentKind.ENTREGA: "Comprobante-Entrega",
    DocumentKind.HISTORIAL: "Historial",
}


def pdf_filename(order: ServiceOrder, kind: DocumentKind | str) -> str:
    """Nombre descriptivo del PDF: «OT-2026-000001_Ana-Torres_Informe-Tecnico.pdf»."""
    document = DocumentKind(kind)
    return f"{order.numero_orden}_{_slug(order.customer.nombre_completo)}_{document.file_stem}.pdf"


def document_html(session: Session, order: ServiceOrder, kind: DocumentKind | str) -> str:
    """HTML del documento pedido. Lanza ValueError si el tipo no existe."""
    builders = {
        DocumentKind.RECEPCION: receipt_html,
        DocumentKind.PRESUPUESTO: budget_html,
        DocumentKind.INFORME: technical_report_html,
        DocumentKind.ENTREGA: delivery_html,
        DocumentKind.HISTORIAL: history_html,
    }
    try:
        build = builders[DocumentKind(kind)]
    except ValueError as exc:
        raise ValueError(f"Documento desconocido: {kind!r}") from exc
    return build(session, order)


def receipt_html(session: Session, order: ServiceOrder) -> str:
    """Comprobante de recepción listo para imprimir (§13.1.1)."""
    customer = order.customer
    equipment = order.equipment

    parts = [_header(session, order, DocumentKind.RECEPCION)]
    parts.append(
        _section(
            "Cliente",
            [
                ("Nombre", customer.nombre_completo),
                ("Identificación", customer.numero_identificacion or EMPTY),
                ("Teléfono", customer.telefono_principal or EMPTY),
                ("Correo", customer.correo_electronico or EMPTY),
            ],
        )
    )
    parts.append(
        _section(
            "Equipo recibido",
            [
                ("Tipo", equipment.tipo_equipo),
                ("Marca y modelo", _brand_model(order) or EMPTY),
                ("Número de serie", equipment.numero_serie or EMPTY),
                ("Color", equipment.color or EMPTY),
                ("Sistema operativo", equipment.sistema_operativo or EMPTY),
                ("Accesorios recibidos", equipment.accesorios_recibidos or EMPTY),
                ("Estado físico", equipment.estado_fisico or EMPTY),
            ],
        )
    )
    parts.append(
        _section(
            "Recepción",
            [
                ("Fecha de ingreso", format_datetime(order.fecha_ingreso)),
                ("Entrega estimada", format_datetime(order.fecha_estimada_entrega) or EMPTY),
                ("Técnico responsable", order.tecnico_responsable or EMPTY),
                (
                    "Problema reportado",
                    order.problema_reportado or equipment.problema_reportado_cliente or EMPTY,
                ),
                ("Observaciones de ingreso", equipment.observaciones_ingreso or EMPTY),
            ],
        )
    )
    parts.append(_values_html(session, order))
    parts.append(_photos_html(order))
    parts.append(
        '<p style="margin: 10pt 0 2pt 0;"><b>Términos y condiciones</b></p>'
        f'<p style="margin: 0;">{_lines(service_conditions(session))}</p>'
    )
    parts.append(_signatures("Firma del cliente", "Firma del taller"))
    parts.append("</div>")
    return "".join(parts)


def budget_html(session: Session, order: ServiceOrder) -> str:
    """Presupuesto con las líneas, los totales, la validez y el espacio de aprobación (§13.1.3)."""
    tax = tax_settings(session)
    totals = order_totals(order, tax)
    days = budget_validity_days(session)

    parts = [_header(session, order, DocumentKind.PRESUPUESTO)]
    parts.append(
        _section(
            "Cliente",
            [
                ("Nombre", order.customer.nombre_completo),
                ("Identificación", order.customer.numero_identificacion or EMPTY),
                ("Teléfono", order.customer.telefono_principal or EMPTY),
            ],
        )
    )
    parts.append(
        _section(
            "Equipo",
            [
                ("Tipo", order.equipment.tipo_equipo),
                ("Marca y modelo", _brand_model(order) or EMPTY),
                ("Número de serie", order.equipment.numero_serie or EMPTY),
                ("Problema reportado", order.problema_reportado or EMPTY),
            ],
        )
    )

    rows = _concept_rows(order)
    if rows:
        parts.append(
            _table_section(
                "Detalle del presupuesto",
                ("Concepto", "Cant.", "Precio unitario", "Importe"),
                rows,
                widths=("46%", "8%", "23%", "23%"),
                align_right=(1, 2, 3),
            )
        )
    else:
        parts.append(
            '<p style="margin: 10pt 0 2pt 0;"><b>Detalle del presupuesto</b></p>'
            f'<p style="margin: 0;">{EMPTY}</p>'
        )

    parts.append(_totals_section(totals, order, tax, with_payments=False))
    parts.append(
        f'<p style="margin: 12pt 0 0 0;">Presupuesto válido por {days} días desde el '
        f"{format_datetime(order.fecha_ingreso)}. El trabajo se inicia una vez aprobado.</p>"
    )
    parts.append(
        '<p style="margin: 18pt 0 2pt 0;"><b>Aprobación del cliente</b></p>'
        f'<p style="margin: 0;">Nombre: {SIGNATURE} &nbsp;&nbsp; Fecha: ______________</p>'
        f'<p style="margin: 14pt 0 0 0;">Firma: {SIGNATURE}</p>'
    )
    parts.append("</div>")
    return "".join(parts)


def technical_report_html(session: Session, order: ServiceOrder) -> str:
    """Informe técnico: diagnóstico, trabajo, repuestos, fotos, costos y garantía (§13.1.2)."""
    equipment = order.equipment
    tax = tax_settings(session)
    totals = order_totals(order, tax)

    parts = [_header(session, order, DocumentKind.INFORME)]
    parts.append(
        _section(
            "Cliente",
            [
                ("Nombre", order.customer.nombre_completo),
                ("Identificación", order.customer.numero_identificacion or EMPTY),
                ("Teléfono", order.customer.telefono_principal or EMPTY),
            ],
        )
    )
    parts.append(
        _section(
            "Equipo",
            [
                ("Tipo", equipment.tipo_equipo),
                ("Marca y modelo", _brand_model(order) or EMPTY),
                ("Número de serie", equipment.numero_serie or EMPTY),
                ("Estado físico al recibir", equipment.estado_fisico or EMPTY),
                ("Accesorios recibidos", equipment.accesorios_recibidos or EMPTY),
            ],
        )
    )
    parts.append(
        _section(
            "Orden",
            [
                ("Fecha de ingreso", format_datetime(order.fecha_ingreso)),
                ("Estado actual", order.estado),
                ("Técnico responsable", order.tecnico_responsable or EMPTY),
                ("Problema reportado", order.problema_reportado or EMPTY),
            ],
        )
    )
    parts.append(_rich_section("Diagnóstico técnico", order.diagnostico_html))
    parts.append(_rich_section("Trabajo realizado", order.trabajo_realizado_html))
    parts.append(_rich_section("Repuestos utilizados", _lines(_parts_used(order))))
    parts.append(_rich_section("Recomendaciones", order.recomendaciones_html))
    parts.append(_photos_html(order, only=_BEFORE, title="Fotografías del equipo al recibir"))
    parts.append(_photos_html(order, only=_AFTER, title="Fotografías del equipo reparado"))
    parts.append(_totals_section(totals, order, tax))
    parts.append(_section("Garantía", [("Garantía", _warranty(order))]))
    parts.append(_signatures("Firma del técnico", "Firma del cliente"))
    parts.append("</div>")
    return "".join(parts)


def delivery_html(session: Session, order: ServiceOrder) -> str:
    """Comprobante de entrega: trabajo, pagos, saldo, garantía y conformidad (§13.1.4)."""
    tax = tax_settings(session)
    totals = order_totals(order, tax)

    parts = [_header(session, order, DocumentKind.ENTREGA)]
    parts.append(
        _section(
            "Orden",
            [
                ("Fecha de ingreso", format_datetime(order.fecha_ingreso)),
                ("Fecha de entrega", format_datetime(order.fecha_entrega) or EMPTY),
                ("Estado final", order.estado),
                ("Técnico responsable", order.tecnico_responsable or EMPTY),
            ],
        )
    )
    parts.append(
        _section(
            "Cliente",
            [
                ("Nombre", order.customer.nombre_completo),
                ("Identificación", order.customer.numero_identificacion or EMPTY),
                ("Teléfono", order.customer.telefono_principal or EMPTY),
            ],
        )
    )
    parts.append(
        _section(
            "Equipo",
            [
                ("Tipo", order.equipment.tipo_equipo),
                ("Marca y modelo", _brand_model(order) or EMPTY),
                ("Número de serie", order.equipment.numero_serie or EMPTY),
            ],
        )
    )
    parts.append(_rich_section("Trabajo realizado", order.trabajo_realizado_html))
    parts.append(_payments_section(order))
    parts.append(_totals_section(totals, order, tax))
    parts.append(
        _section(
            "Garantía",
            [
                ("Cobertura", _warranty(order)),
                ("Alcance", "Cubre únicamente el trabajo realizado y los repuestos facturados."),
            ],
        )
    )
    parts.append(
        '<p style="margin: 12pt 0 0 0;"><b>Declaración de conformidad</b></p>'
        '<p style="margin: 0;">Recibí el equipo en las condiciones descritas, probado y '
        "funcionando, y acepto el alcance de la garantía indicada.</p>"
    )
    parts.append(_signatures("Firma del cliente", "Firma del taller"))
    parts.append("</div>")
    return "".join(parts)


def history_html(session: Session, order: ServiceOrder) -> str:
    """Historial completo: todos los movimientos de la orden en orden cronológico (§13.1.5)."""
    parts = [_header(session, order, DocumentKind.HISTORIAL)]
    parts.append(
        _section(
            "Orden",
            [
                ("Cliente", order.customer.nombre_completo),
                ("Equipo", f"{order.equipment.tipo_equipo} {_brand_model(order)}".strip()),
                ("Fecha de ingreso", format_datetime(order.fecha_ingreso)),
                ("Estado actual", order.estado),
            ],
        )
    )
    rows = [
        (
            format_datetime(entry.fecha),
            "Estado" if entry.kind == "estado" else "Evento",
            f"{entry.titulo}. {entry.detalle}".strip(),
            entry.usuario,
        )
        for entry in order_timeline(order)
    ]
    if rows:
        parts.append(
            _table_section(
                "Movimientos",
                ("Fecha", "Tipo", "Detalle", "Usuario"),
                rows,
                widths=("16%", "10%", "56%", "18%"),
            )
        )
    else:
        parts.append(
            '<p style="margin: 10pt 0 2pt 0;"><b>Movimientos</b></p>'
            f'<p style="margin: 0;">{EMPTY}</p>'
        )
    parts.append("</div>")
    return "".join(parts)


def print_document(
    html: str,
    parent: QWidget | None,
    title: str,
    furniture: PageFurniture | None = None,
    pdf_name: str | None = None,
    paper: str = DEFAULT_PAPER_SIZE,
    margin_mm: int = DEFAULT_PAGE_MARGIN_MM,
) -> None:
    """Vista previa, impresión y guardado en PDF del documento (§13.2 y §13.3).

    El propio diálogo de Qt aporta impresora, orientación, tamaño de hoja, márgenes, rango de
    páginas y copias. Encima se añade el encabezado y el pie con la numeración, y un botón
    «Guardar como PDF» que propone el nombre descriptivo de la orden.
    """
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    apply_page_setup(printer, paper, margin_mm)
    preview = QPrintPreviewDialog(printer, parent)
    preview.setWindowTitle(title)
    size_preview(preview, parent)
    preview.paintRequested.connect(lambda target: render_document(target, html, furniture))
    add_pdf_action(preview, printer, html, furniture, pdf_name or f"{title}.pdf")
    preview.exec()


def print_order_document(
    session_factory: sessionmaker[Session],
    order_id: int,
    kind: DocumentKind | str,
    parent: QWidget | None = None,
    title: str | None = None,
) -> bool:
    """Abre la vista previa del documento pedido.

    Devuelve True si el documento se pudo preparar; si la orden ya no existe o falla la
    consulta, avisa al usuario y devuelve False.
    """
    document = DocumentKind(kind)
    window_title = title or QCoreApplication.translate(_CONTEXT, str(document))
    try:
        with session_factory() as session:
            order = session.get(ServiceOrder, order_id)
            if order is None:
                QMessageBox.warning(
                    parent,
                    window_title,
                    QCoreApplication.translate(_CONTEXT, "La orden ya no existe."),
                )
                return False
            html = document_html(session, order, document)
            furniture = _furniture(session, order, document)
            pdf_name = pdf_filename(order, document)
            paper = paper_size(session)
            margin = page_margin_mm(session)
    except SQLAlchemyError:
        QMessageBox.critical(
            parent,
            window_title,
            QCoreApplication.translate(
                _CONTEXT, "No se pudo preparar el documento. Intente de nuevo."
            ),
        )
        return False
    print_document(
        html,
        parent,
        window_title,
        furniture=furniture,
        pdf_name=pdf_name,
        paper=paper,
        margin_mm=margin,
    )
    return True


def print_order_receipt(
    session_factory: sessionmaker[Session],
    order_id: int,
    parent: QWidget | None = None,
    title: str | None = None,
) -> bool:
    """Atajo del comprobante de recepción, que es el documento de la lista de órdenes."""
    return print_order_document(
        session_factory, order_id, DocumentKind.RECEPCION, parent, title
    )


def _furniture(
    session: Session, order: ServiceOrder, kind: DocumentKind | str
) -> PageFurniture:
    """Encabezado y pie que se repiten en cada hoja (§13.2).

    El encabezado lleva el taller y el documento con su número de orden; el pie, la fecha de
    generación. La numeración la pone `render_document`, que es quien cuenta las hojas.
    """
    name = workshop_name(session)
    contact = workshop_contact(session)
    return PageFurniture(
        header_left=f"{name} · {contact}" if contact else name,
        header_right=f"{kind} · {order.numero_orden}",
        footer_left=f"Generado el {format_datetime(datetime.now())}",
    )


def _header(session: Session, order: ServiceOrder, title: DocumentKind | str) -> str:
    parts = [
        '<div style="font-size: 10pt;">',
        '<p style="font-size: 15pt; font-weight: bold; margin: 0;">'
        f"{_escape(workshop_name(session))}</p>",
    ]
    contact = workshop_contact(session)
    if contact:
        parts.append(f'<p style="margin: 0;">{_escape(contact)}</p>')
    parts.append(
        '<p style="margin: 10pt 0 4pt 0; font-size: 12pt;">'
        f"<b>{_escape(str(title))}</b> &nbsp;&nbsp; {_escape(order.numero_orden)}</p>"
    )
    return "".join(parts)


def _values_html(session: Session, order: ServiceOrder) -> str:
    """Sección «Valores» del comprobante.

    Se arma con `order_totals`, la misma fórmula que usa la pestaña «Presupuesto y pagos»
    (§5.3), para que el papel y la pantalla nunca muestren cifras distintas. Las filas que
    pueden ser cero (repuestos, mano de obra, líneas, descuento, pagos) solo aparecen cuando
    tienen importe; el total y el saldo salen siempre. El IVA solo se imprime si está activo:
    al cliente no se le muestra una línea de impuesto en cero.
    """
    tax = tax_settings(session)
    totals = order_totals(order, tax)
    rows: list[tuple[str, str]] = [
        ("Costo de diagnóstico", format_money(order.costo_diagnostico)),
    ]
    if _positive(order.costo_repuestos):
        rows.append(("Repuestos", format_money(order.costo_repuestos)))
    if _positive(order.costo_mano_obra):
        rows.append(("Mano de obra", format_money(order.costo_mano_obra)))
    if _positive(totals.lineas_presupuesto):
        rows.append(("Líneas de presupuesto", format_money(totals.lineas_presupuesto)))
    rows.append(("Subtotal", format_money(totals.subtotal)))
    if _positive(order.descuento):
        rows.append(("Descuento", format_money(order.descuento)))
    if tax.enabled:
        rows.append((f"IVA ({tax.percent}%)", format_money(totals.impuestos)))
    rows.append(("Total", format_money(totals.total)))
    rows.append(("Anticipo recibido", format_money(order.anticipo)))
    if totals.pagos_realizados != ZERO:
        rows.append(("Pagos recibidos", format_money(totals.pagos_realizados)))
    rows.append(("Saldo pendiente", format_money(totals.saldo_pendiente)))
    return _section("Valores", rows, bold=("Total", "Saldo pendiente"))


def _totals_section(
    totals: OrderTotals, order: ServiceOrder, tax, with_payments: bool = True
) -> str:
    """Bloque de importes compartido por el presupuesto, el informe y la entrega.

    El presupuesto no imprime anticipos ni pagos: es una oferta, no un estado de cuenta.
    """
    rows = [("Subtotal", format_money(totals.subtotal))]
    if _positive(order.descuento):
        rows.append(("Descuento", format_money(order.descuento)))
    if tax.enabled:
        rows.append((f"IVA ({tax.percent}%)", format_money(totals.impuestos)))
    rows.append(("Total", format_money(totals.total)))
    if with_payments:
        if _positive(order.anticipo):
            rows.append(("Anticipo recibido", format_money(order.anticipo)))
        if totals.pagos_realizados != ZERO:
            rows.append(("Pagos recibidos", format_money(totals.pagos_realizados)))
        rows.append(("Saldo pendiente", format_money(totals.saldo_pendiente)))
        return _section("Importes", rows, bold=("Total", "Saldo pendiente"))
    return _section("Importes", rows, bold=("Total",))


def _concept_rows(order: ServiceOrder) -> list[tuple[str, str, str, str]]:
    """Conceptos del presupuesto: los tres costos fijos (si tienen importe) y las líneas."""
    rows: list[tuple[str, str, str, str]] = []
    fixed = (
        ("Costo de diagnóstico", order.costo_diagnostico),
        ("Costo de repuestos", order.costo_repuestos),
        ("Mano de obra", order.costo_mano_obra),
    )
    for label, amount in fixed:
        if _positive(amount):
            rows.append((label, "1", format_money(amount), format_money(amount)))
    for line in order.budget_lines:
        amount = line.cantidad * line.precio_unitario
        rows.append(
            (
                f"{line.tipo_linea}: {line.descripcion}",
                _quantity(line.cantidad),
                format_money(line.precio_unitario),
                format_money(amount),
            )
        )
    return rows


def _payments_section(order: ServiceOrder) -> str:
    rows = [
        (
            format_datetime(payment.fecha),
            payment.tipo_pago,
            payment.metodo_pago,
            format_money(payment.monto),
            "Anulado" if payment.anulado else "Vigente",
        )
        for payment in payments_for_order(order)
    ]
    if not rows:
        return _section("Pagos", [("Pagos recibidos", EMPTY)])
    return _table_section(
        "Pagos",
        ("Fecha", "Tipo", "Método", "Importe", "Estado"),
        rows,
        widths=("18%", "18%", "30%", "20%", "14%"),
        align_right=(3,),
    )


def _parts_used(order: ServiceOrder) -> str:
    """Repuestos: el texto libre si existe; si no, las líneas de tipo Repuesto."""
    if (order.repuestos_utilizados or "").strip():
        return order.repuestos_utilizados.strip()
    parts = [
        f"{_quantity(line.cantidad)} × {line.descripcion}"
        for line in order.budget_lines
        if line.tipo_linea == BudgetLineType.REPUESTO.value
    ]
    return ", ".join(parts) or EMPTY


def _warranty(order: ServiceOrder) -> str:
    days = order.garantia_dias or 0
    return f"{days} días" if days > 0 else "Sin garantía registrada"


def _brand_model(order: ServiceOrder) -> str:
    return " ".join(part for part in (order.equipment.marca, order.equipment.modelo) if part)


def _positive(value: Decimal | None) -> bool:
    return value is not None and value > ZERO


def _quantity(value: Decimal) -> str:
    """Cantidad sin ceros de relleno y sin notación científica: 2.00 → «2»."""
    return format(value.normalize(), "f")


def _section(
    title: str,
    rows: list[tuple[str, str]],
    bold: tuple[str, ...] = (),
) -> str:
    body = "".join(
        f'<tr><td style="{_CELL}"><b>{_escape(label)}</b></td>'
        f'<td style="{_CELL}">{_cell(label, value, bold)}</td></tr>'
        for label, value in rows
    )
    return (
        f'<p style="margin: 6pt 0 1pt 0;"><b>{_escape(title)}</b></p>'
        f'<table width="100%" cellspacing="0" cellpadding="0">{body}</table>'
    )


def _rich_section(title: str, html: str | None) -> str:
    """Bloque de texto enriquecido: diagnóstico, trabajo realizado o recomendaciones."""
    body = (html or "").strip()
    return (
        f'<p style="margin: 6pt 0 1pt 0;"><b>{_escape(title)}</b></p>'
        f'<p style="margin: 0;">{body or EMPTY}</p>'
    )


def _table_section(
    title: str,
    headers: tuple[str, ...],
    rows: list[tuple[str, ...]],
    widths: tuple[str, ...] | None = None,
    align_right: tuple[int, ...] = (),
) -> str:
    """Tabla con encabezado y borde inferior, para líneas, pagos e historial."""
    spans = widths or tuple("" for _ in headers)

    def cell(text: str, index: int, style: str) -> str:
        align = _RIGHT if index in align_right else ""
        width = f' width="{spans[index]}"' if spans[index] else ""
        return f'<td{width} style="{style}{align}">{_escape(text)}</td>'

    head = "".join(cell(header, index, _HEAD_CELL) for index, header in enumerate(headers))
    body = "".join(
        "<tr>"
        + "".join(cell(value, index, _CELL) for index, value in enumerate(row))
        + "</tr>"
        for row in rows
    )
    return (
        f'<p style="margin: 6pt 0 1pt 0;"><b>{_escape(title)}</b></p>'
        f'<table width="100%" cellspacing="0" cellpadding="0"><tr>{head}</tr>{body}</table>'
    )


def _cell(label: str, value: str, bold: tuple[str, ...]) -> str:
    escaped = _escape(value)
    return f"<b>{escaped}</b>" if label in bold else escaped


def _photos_html(
    order: ServiceOrder,
    only: tuple[PhotoType, ...] | None = None,
    title: str = "Fotografías del equipo",
) -> str:
    photos = _photos(order, only)
    if not photos:
        return ""
    cells = "".join(
        f'<td style="padding: 0 6pt 0 0;">'
        f'<img src="{_escape(_file_uri(photo.ruta_archivo))}" width="110"></td>'
        for photo in photos
    )
    return (
        f'<p style="margin: 6pt 0 1pt 0;"><b>{_escape(title)}</b></p>'
        f'<table cellspacing="0" cellpadding="0"><tr>{cells}</tr></table>'
    )


def _photos(
    order: ServiceOrder, only: tuple[PhotoType, ...] | None = None
) -> list[Photograph]:
    photos = list(order.photographs)
    if only is not None:
        wanted = {kind.value for kind in only}
        photos = [photo for photo in photos if photo.tipo_fotografia in wanted]
    return photos[:MAX_PHOTOS]


def _signatures(*labels: str) -> str:
    cells = "".join(
        f'<td style="padding-right: 20pt;">{SIGNATURE}<br/>{_escape(label)}</td>'
        for label in labels
    )
    return (
        '<table width="100%" cellspacing="0" cellpadding="0" style="margin-top: 18pt;">'
        f"<tr>{cells}</tr></table>"
    )


def _file_uri(path: str) -> str:
    try:
        return Path(path).resolve().as_uri()
    except (OSError, ValueError):
        return path


def _slug(text: str) -> str:
    """Nombre del cliente apto para un archivo: «Ana Torres» → «Ana-Torres»."""
    plain = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(char for char in plain if not unicodedata.combining(char))
    return re.sub(r"[^A-Za-z0-9]+", "-", ascii_text).strip("-") or "Cliente"


def _lines(text: str) -> str:
    return _escape(text).replace("\n", "<br/>")


def _escape(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
