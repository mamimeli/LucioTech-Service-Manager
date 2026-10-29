"""Pruebas del siguiente paso de una orden según su estado (§9)."""

from __future__ import annotations

import pytest

from luciotech.database.enums import OrderState
from luciotech.ui.documents import DocumentKind
from luciotech.ui.order_actions import NEXT_ACTIONS, next_action


def test_every_state_proposes_an_action() -> None:
    assert set(NEXT_ACTIONS) == set(OrderState)


@pytest.mark.parametrize("state", list(OrderState))
def test_every_action_has_a_label_and_a_hint(state: OrderState) -> None:
    action = next_action(state)

    assert action.label
    assert action.hint


def test_a_new_order_goes_to_the_diagnosis_queue() -> None:
    action = next_action(OrderState.RECIBIDO)

    assert action.label == "Iniciar diagnóstico"
    assert action.state == OrderState.PENDIENTE_DIAGNOSTICO
    assert action.document is None
    assert action.available


def test_handing_the_budget_over_moves_the_order_and_opens_the_budget() -> None:
    action = next_action(OrderState.DIAGNOSTICADO)

    assert action.state == OrderState.ESPERANDO_APROBACION
    assert action.document is DocumentKind.PRESUPUESTO


def test_finishing_the_repair_opens_the_technical_report() -> None:
    action = next_action(OrderState.EN_REPARACION)

    assert action.state == OrderState.REPARADO
    assert action.document is DocumentKind.INFORME


def test_delivering_closes_the_order_and_prints_the_delivery_note() -> None:
    action = next_action(OrderState.LISTO_PARA_ENTREGAR)

    assert action.delivers
    assert action.state is None
    assert action.document is DocumentKind.ENTREGA


def test_a_delivered_order_only_reprints_the_delivery_note() -> None:
    action = next_action(OrderState.ENTREGADO)

    assert action.state is None
    assert not action.delivers
    assert action.document is DocumentKind.ENTREGA


def test_a_cancelled_order_has_nothing_pending() -> None:
    action = next_action(OrderState.CANCELADO)

    assert not action.available
    assert action.state is None
    assert action.document is None


def test_an_unknown_state_falls_back_to_a_neutral_action() -> None:
    action = next_action("Estado que no existe")

    assert not action.available
    assert action.label == "Sin acciones pendientes"


def test_the_action_is_accepted_as_a_plain_string() -> None:
    """El estado llega como texto desde la base; la acción tiene que reconocerlo igual."""
    assert next_action("Recibido") == next_action(OrderState.RECIBIDO)
