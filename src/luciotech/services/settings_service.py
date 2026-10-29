"""Lectura y escritura de la configuración de negocio (tabla configuracion, §5.8)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from luciotech.config import (
    APP_CONFIG,
    DEFAULT_BUDGET_VALIDITY_DAYS,
    DEFAULT_EQUIPMENT_TYPES,
    DEFAULT_PAGE_MARGIN_MM,
    DEFAULT_PAPER_SIZE,
    DEFAULT_RETENTION_MONTHS,
    DEFAULT_SERVICE_TERMS,
    DEFAULT_TAX_ENABLED,
    DEFAULT_TAX_PERCENT,
    MAX_PAGE_MARGIN_MM,
    MIN_PAGE_MARGIN_MM,
    PAPER_SIZES,
)
from luciotech.database.models import Configuration

KEY_TAX_PERCENT = "impuesto_porcentaje"
KEY_TAX_ENABLED = "impuesto_activo"
KEY_EQUIPMENT_TYPES = "tipos_equipo"
KEY_SERVICE_TERMS = "condiciones_servicio"
KEY_RETENTION_MONTHS = "retencion_meses"
KEY_BUDGET_VALIDITY_DAYS = "presupuesto_validez_dias"
KEY_PAPER_SIZE = "tamano_papel"
KEY_PAGE_MARGIN_MM = "margen_pagina_mm"
KEY_WORKSHOP_NAME = "nombre_taller"
KEY_WORKSHOP_PHONE = "telefono_taller"
KEY_WORKSHOP_ADDRESS = "direccion_taller"
KEY_WORKSHOP_EMAIL = "correo_taller"


@dataclass(frozen=True)
class TaxSettings:
    percent: Decimal
    enabled: bool


def get_value(session: Session, clave: str, default: str | None = None) -> str | None:
    row = session.scalar(select(Configuration).where(Configuration.clave == clave))
    if row is None or row.valor is None:
        return default
    return row.valor


def set_value(session: Session, clave: str, valor: str) -> None:
    row = session.scalar(select(Configuration).where(Configuration.clave == clave))
    if row is None:
        session.add(Configuration(clave=clave, valor=valor))
    else:
        row.valor = valor
    session.flush()


def equipment_types(session: Session) -> list[str]:
    """Tipos de equipo: uno por línea en la configuración, o los valores por defecto."""
    raw = get_value(session, KEY_EQUIPMENT_TYPES)
    if raw is None:
        return list(DEFAULT_EQUIPMENT_TYPES)
    items = [line.strip() for line in raw.splitlines() if line.strip()]
    return items or list(DEFAULT_EQUIPMENT_TYPES)


def tax_settings(session: Session) -> TaxSettings:
    raw_percent = get_value(session, KEY_TAX_PERCENT, str(DEFAULT_TAX_PERCENT)) or ""
    try:
        percent = Decimal(raw_percent.strip())
    except InvalidOperation as exc:
        raise ValueError(f"Porcentaje de impuesto no válido: {raw_percent!r}") from exc
    if not Decimal("0") <= percent <= Decimal("100"):
        raise ValueError("El porcentaje de impuesto debe estar entre 0 y 100.")

    raw_enabled = get_value(session, KEY_TAX_ENABLED, str(DEFAULT_TAX_ENABLED).lower()) or ""
    return TaxSettings(percent=percent, enabled=raw_enabled.strip().lower() == "true")


def workshop_name(session: Session) -> str:
    return (get_value(session, KEY_WORKSHOP_NAME, APP_CONFIG.organization_name) or "").strip()


def workshop_phone(session: Session) -> str:
    return (get_value(session, KEY_WORKSHOP_PHONE, "") or "").strip()


def workshop_address(session: Session) -> str:
    return (get_value(session, KEY_WORKSHOP_ADDRESS, "") or "").strip()


def workshop_email(session: Session) -> str:
    return (get_value(session, KEY_WORKSHOP_EMAIL, "") or "").strip()


def workshop_contact(session: Session) -> str:
    """Línea de contacto del taller para los encabezados de los documentos."""
    return " · ".join(
        part
        for part in (
            workshop_phone(session),
            workshop_email(session),
            workshop_address(session),
        )
        if part
    )


def retention_months(session: Session) -> int:
    """Plazo en meses para retirar un equipo antes de darlo de baja (§5.8)."""
    raw = get_value(session, KEY_RETENTION_MONTHS)
    try:
        months = int(str(raw).strip())
    except (TypeError, ValueError):
        return DEFAULT_RETENTION_MONTHS
    return months if months > 0 else DEFAULT_RETENTION_MONTHS


def budget_validity_days(session: Session) -> int:
    """Días de validez del presupuesto impreso (§13.1.3)."""
    raw = get_value(session, KEY_BUDGET_VALIDITY_DAYS)
    try:
        days = int(str(raw).strip())
    except (TypeError, ValueError):
        return DEFAULT_BUDGET_VALIDITY_DAYS
    return days if days > 0 else DEFAULT_BUDGET_VALIDITY_DAYS


def paper_size(session: Session) -> str:
    """Hoja de los documentos: «A4» o «Carta» (§13.2)."""
    raw = (get_value(session, KEY_PAPER_SIZE, DEFAULT_PAPER_SIZE) or "").strip()
    for name in PAPER_SIZES:
        if name.lower() == raw.lower():
            return name
    return DEFAULT_PAPER_SIZE


def page_margin_mm(session: Session) -> int:
    """Márgenes de la hoja en milímetros; fuera de rango se usa el valor por defecto."""
    raw = get_value(session, KEY_PAGE_MARGIN_MM)
    try:
        margin = int(str(raw).strip())
    except (TypeError, ValueError):
        return DEFAULT_PAGE_MARGIN_MM
    return margin if MIN_PAGE_MARGIN_MM <= margin <= MAX_PAGE_MARGIN_MM else DEFAULT_PAGE_MARGIN_MM


def set_paper_size(session: Session, paper: str) -> None:
    name = paper.strip().title()
    if name not in PAPER_SIZES:
        raise ValueError(f"Tamaño de papel no válido: {paper!r}")
    set_value(session, KEY_PAPER_SIZE, name)


def set_page_margin_mm(session: Session, margin: int) -> None:
    if not MIN_PAGE_MARGIN_MM <= margin <= MAX_PAGE_MARGIN_MM:
        raise ValueError(
            f"Los márgenes deben estar entre {MIN_PAGE_MARGIN_MM} y {MAX_PAGE_MARGIN_MM} mm."
        )
    set_value(session, KEY_PAGE_MARGIN_MM, str(int(margin)))


def service_terms(session: Session) -> str:
    """Términos y condiciones tal como se guardaron, con `{meses}` sin sustituir."""
    text = (get_value(session, KEY_SERVICE_TERMS) or "").strip()
    return text or DEFAULT_SERVICE_TERMS


def service_conditions(session: Session) -> str:
    """Términos listos para mostrar: el plazo configurado sustituye a `{meses}`."""
    return service_terms(session).replace("{meses}", str(retention_months(session)))


def set_service_terms(session: Session, text: str) -> None:
    set_value(session, KEY_SERVICE_TERMS, text.strip())


def set_retention_months(session: Session, months: int) -> None:
    if months <= 0:
        raise ValueError("El plazo de retirada debe ser mayor que cero.")
    set_value(session, KEY_RETENTION_MONTHS, str(int(months)))
