"""Documentos imprimibles de una orden: comprobante de recepción (§7.5 y §13.1.1).

El comprobante se arma como HTML y se imprime con los diálogos de Qt (§13.3). La contraseña
del equipo nunca aparece: el documento se entrega al cliente (§5.2).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtGui import QPageSize, QTextDocument
from PyQt6.QtPrintSupport import QPrintPreviewDialog, QPrinter
from PyQt6.QtWidgets import QMessageBox, QWidget
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from luciotech.database.models import ServiceOrder
from luciotech.services.settings_service import (
    service_conditions,
    tax_settings,
    workshop_contact,
    workshop_name,
)
from luciotech.services.totals_service import order_totals
from luciotech.ui.formatting import format_datetime, format_money

MAX_PHOTOS = 4
EMPTY = "—"
SIGNATURE = "____________________________"
ZERO = Decimal("0.00")
_CONTEXT = "LucioTech"


def receipt_html(session: Session, order: ServiceOrder) -> str:
    """Comprobante de recepción listo para imprimir."""
    customer = order.customer
    equipment = order.equipment
    brand_model = " ".join(
        part for part in (equipment.marca, equipment.modelo) if part
    )

    parts = ['<div style="font-size: 10pt;">']
    parts.append(
        f'<p style="font-size: 15pt; font-weight: bold; margin: 0;">'
        f"{_escape(workshop_name(session))}</p>"
    )
    contact = workshop_contact(session)
    if contact:
        parts.append(f'<p style="margin: 0;">{_escape(contact)}</p>')
    parts.append(
        f'<p style="margin: 14pt 0 6pt 0; font-size: 12pt;">'
        f"<b>Comprobante de recepción</b> &nbsp;&nbsp; {_escape(order.numero_orden)}</p>"
    )

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
                ("Marca y modelo", brand_model or EMPTY),
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
        '<p style="margin: 12pt 0 2pt 0;"><b>Términos y condiciones</b></p>'
        f'<p style="margin: 0;">{_lines(service_conditions(session))}</p>'
    )
    parts.append(
        '<table width="100%" cellspacing="0" cellpadding="0" style="margin-top: 30pt;"><tr>'
        f'<td style="padding-right: 20pt;">{SIGNATURE}<br/>Firma del cliente</td>'
        f"<td>{SIGNATURE}<br/>Firma del taller</td>"
        "</tr></table>"
    )
    parts.append("</div>")
    return "".join(parts)


def print_document(html: str, parent: QWidget | None, title: str) -> None:
    """Vista previa e impresión del documento con los diálogos de Qt (§13.3)."""
    document = QTextDocument()
    document.setHtml(html)
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    preview = QPrintPreviewDialog(printer, parent)
    preview.setWindowTitle(title)
    preview.paintRequested.connect(document.print)
    preview.exec()


def print_order_receipt(
    session_factory: sessionmaker[Session],
    order_id: int,
    parent: QWidget | None = None,
    title: str | None = None,
) -> bool:
    """Abre la vista previa del comprobante de recepción de una orden.

    Devuelve True si el documento se pudo preparar; si la orden ya no existe o falla la consulta,
    avisa al usuario y devuelve False.
    """
    window_title = title or QCoreApplication.translate(_CONTEXT, "Comprobante de recepción")
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
            html = receipt_html(session, order)
    except SQLAlchemyError:
        QMessageBox.critical(
            parent,
            window_title,
            QCoreApplication.translate(
                _CONTEXT, "No se pudo preparar el comprobante. Intente de nuevo."
            ),
        )
        return False
    print_document(html, parent, window_title)
    return True


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


def _positive(value: Decimal | None) -> bool:
    return value is not None and value > ZERO


def _section(
    title: str,
    rows: list[tuple[str, str]],
    bold: tuple[str, ...] = (),
) -> str:
    body = "".join(
        '<tr><td style="padding: 1pt 10pt 1pt 0; vertical-align: top;">'
        f"<b>{_escape(label)}</b></td>"
        f'<td style="padding: 1pt 0;">{_cell(label, value, bold)}</td></tr>'
        for label, value in rows
    )
    return (
        f'<p style="margin: 10pt 0 2pt 0;"><b>{_escape(title)}</b></p>'
        f'<table width="100%" cellspacing="0" cellpadding="0">{body}</table>'
    )


def _cell(label: str, value: str, bold: tuple[str, ...]) -> str:
    escaped = _escape(value)
    return f"<b>{escaped}</b>" if label in bold else escaped


def _photos_html(order: ServiceOrder) -> str:
    photos = list(order.photographs)[:MAX_PHOTOS]
    if not photos:
        return ""
    cells = "".join(
        f'<td style="padding: 0 6pt 0 0;">'
        f'<img src="{_escape(_file_uri(photo.ruta_archivo))}" width="150"></td>'
        for photo in photos
    )
    return (
        '<p style="margin: 10pt 0 2pt 0;"><b>Fotografías del equipo</b></p>'
        f'<table cellspacing="0" cellpadding="0"><tr>{cells}</tr></table>'
    )


def _file_uri(path: str) -> str:
    try:
        return Path(path).resolve().as_uri()
    except (OSError, ValueError):
        return path


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
