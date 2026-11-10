"""Pruebas de la configuración de negocio: claves, marcadores y garantía (§5.8 y §13.1)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from luciotech.config import (
    DEFAULT_EQUIPMENT_TYPES,
    DEFAULT_SERVICE_TERMS,
    DEFAULT_WARRANTY_DAYS,
    DEFAULT_WARRANTY_TERMS,
)
from luciotech.database.models import ServiceOrder
from luciotech.services import settings_service as settings
from luciotech.services.customer_service import CustomerData
from luciotech.services.equipment_service import EquipmentData
from luciotech.services.reception_service import ReceptionData, register_reception
from luciotech.services.settings_service import TaxSettings

ENTRY = datetime(2026, 3, 10, 9, 0)


def _order(session: Session) -> ServiceOrder:
    """Una recepción mínima, para comprobar la garantía que hereda la orden."""
    return register_reception(
        session,
        ReceptionData(
            equipment=EquipmentData(cliente_id=None, tipo_equipo="Laptop", numero_serie="SN-1"),
            new_customer=CustomerData(
                nombre_completo="Ana Torres",
                numero_identificacion="1301206320",
                telefono_principal="0991234567",
            ),
            fecha_ingreso=ENTRY,
        ),
    )


# Términos y condiciones


def test_service_terms_keep_the_marker_until_the_document_is_printed(session: Session) -> None:
    assert settings.service_terms(session) == DEFAULT_SERVICE_TERMS
    assert "{meses}" in settings.service_terms(session)
    assert "dentro de 6 meses" in settings.service_conditions(session)


def test_retention_months_change_every_printed_condition(session: Session) -> None:
    settings.set_service_terms(session, "Plazo de {meses} meses para retirar el equipo.")
    settings.set_retention_months(session, 9)

    assert settings.service_conditions(session) == "Plazo de 9 meses para retirar el equipo."


def test_an_empty_service_terms_value_falls_back_to_the_default(session: Session) -> None:
    settings.set_service_terms(session, "   ")
    assert settings.service_conditions(session) == DEFAULT_SERVICE_TERMS.replace("{meses}", "6")


# Texto de garantía


def test_warranty_terms_fall_back_to_the_default_text(session: Session) -> None:
    assert settings.warranty_terms(session) == DEFAULT_WARRANTY_TERMS
    assert "{dias}" in settings.warranty_terms(session)


def test_warranty_terms_can_be_replaced_and_left_blank(session: Session) -> None:
    settings.set_warranty_terms(session, "  Garantía propia del taller  ")
    assert settings.warranty_terms(session) == "Garantía propia del taller"

    settings.set_warranty_terms(session, "   ")
    assert settings.warranty_terms(session) == ""


def test_warranty_days_default_and_saved_values(session: Session) -> None:
    assert settings.warranty_days(session) == DEFAULT_WARRANTY_DAYS

    settings.set_warranty_days(session, 90)
    assert settings.warranty_days(session) == 90

    settings.set_warranty_days(session, 0)
    assert settings.warranty_days(session) == 0


def test_invalid_warranty_days_are_rejected_or_ignored(session: Session) -> None:
    with pytest.raises(ValueError):
        settings.set_warranty_days(session, -1)

    settings.set_value(session, settings.KEY_WARRANTY_DAYS, "no es un número")
    assert settings.warranty_days(session) == DEFAULT_WARRANTY_DAYS

    settings.set_value(session, settings.KEY_WARRANTY_DAYS, "-4")
    assert settings.warranty_days(session) == DEFAULT_WARRANTY_DAYS


def test_new_orders_take_the_configured_warranty_days(session: Session) -> None:
    settings.set_warranty_days(session, 60)
    order = _order(session)

    assert order.garantia_dias == 60


def test_warranty_conditions_replace_every_marker(session: Session) -> None:
    order = _order(session)
    settings.set_retention_months(session, 8)
    settings.set_warranty_terms(
        session, "Cubre {dias} días de la orden {orden}; retirada en {meses} meses."
    )

    text = settings.warranty_conditions(session, order)

    assert text == (
        f"Cubre 30 días de la orden {order.numero_orden}; retirada en 8 meses."
    )


def test_warranty_conditions_are_empty_without_warranty_or_without_text(
    session: Session,
) -> None:
    order = _order(session)

    order.garantia_dias = 0
    assert settings.warranty_conditions(session, order) == ""

    order.garantia_dias = 30
    settings.set_warranty_terms(session, "")
    assert settings.warranty_conditions(session, order) == ""


# Resto de la configuración que edita la pantalla


def test_workshop_details_and_tax_settings_are_saved_together(session: Session) -> None:
    settings.set_workshop_details(
        session,
        name="Taller Central",
        phone="0991234567",
        email="taller@ejemplo.com",
        address="Av. 1",
    )
    settings.set_tax_settings(session, Decimal("12"), True)

    assert settings.workshop_name(session) == "Taller Central"
    assert settings.workshop_contact(session) == "0991234567 · taller@ejemplo.com · Av. 1"
    assert settings.tax_settings(session) == TaxSettings(percent=Decimal("12"), enabled=True)


def test_an_invalid_tax_percent_cannot_be_saved(session: Session) -> None:
    with pytest.raises(ValueError):
        settings.set_tax_settings(session, Decimal("101"), False)

    assert settings.tax_settings(session).percent == Decimal("15")


def test_equipment_types_and_budget_validity_round_trip(session: Session) -> None:
    settings.set_equipment_types(session, "Laptop\nImpresora\n\n")
    settings.set_budget_validity_days(session, 20)

    assert settings.equipment_types(session) == ["Laptop", "Impresora"]
    assert settings.budget_validity_days(session) == 20

    with pytest.raises(ValueError):
        settings.set_budget_validity_days(session, 0)


def test_an_empty_equipment_list_falls_back_to_the_defaults(session: Session) -> None:
    settings.set_equipment_types(session, "  \n  ")
    assert settings.equipment_types(session) == list(DEFAULT_EQUIPMENT_TYPES)
