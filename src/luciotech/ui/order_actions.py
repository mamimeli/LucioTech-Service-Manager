"""Siguiente paso de una orden según su estado (§9).

El técnico no debería tener que recordar qué toca después de cada cambio. Cada estado propone
una sola acción principal, y la ventana de la orden la ofrece como botón grande en el resumen.
Las transiciones siguen siendo libres (el ROADMAP aún no fija reglas, §5.6), así que esto es
una sugerencia: el selector «Cambiar estado» sigue estando para cualquier salto.
"""

from __future__ import annotations

from dataclasses import dataclass

from luciotech.database.enums import OrderState
from luciotech.ui.documents import DocumentKind


@dataclass(frozen=True)
class NextAction:
    """Acción que la ventana de la orden ofrece como «siguiente paso»."""

    label: str
    hint: str = ""
    state: OrderState | None = None
    document: DocumentKind | None = None
    delivers: bool = False

    @property
    def available(self) -> bool:
        """True si pulsar el botón hace algo (cambiar de estado, entregar o abrir un papel)."""
        return self.state is not None or self.delivers or self.document is not None


NEXT_ACTIONS: dict[OrderState, NextAction] = {
    OrderState.RECIBIDO: NextAction(
        label="Iniciar diagnóstico",
        hint="El equipo ya está en el taller: pásalo a la cola de diagnóstico.",
        state=OrderState.PENDIENTE_DIAGNOSTICO,
    ),
    OrderState.PENDIENTE_DIAGNOSTICO: NextAction(
        label="Marcar como diagnosticado",
        hint="Escribe antes el diagnóstico en la pestaña Diagnóstico.",
        state=OrderState.DIAGNOSTICADO,
    ),
    OrderState.DIAGNOSTICADO: NextAction(
        label="Entregar presupuesto al cliente",
        hint="La orden espera la aprobación y se abre el presupuesto para imprimir.",
        state=OrderState.ESPERANDO_APROBACION,
        document=DocumentKind.PRESUPUESTO,
    ),
    OrderState.ESPERANDO_APROBACION: NextAction(
        label="Iniciar reparación",
        hint="Con el presupuesto aprobado, empieza el trabajo en el equipo.",
        state=OrderState.EN_REPARACION,
    ),
    OrderState.ESPERANDO_REPUESTO: NextAction(
        label="Reanudar la reparación",
        hint="El repuesto llegó: vuelve al trabajo en el equipo.",
        state=OrderState.EN_REPARACION,
    ),
    OrderState.EN_REPARACION: NextAction(
        label="Marcar como reparado",
        hint="Cuando el equipo funcione, márcalo y entrega el informe técnico.",
        state=OrderState.REPARADO,
        document=DocumentKind.INFORME,
    ),
    OrderState.REPARADO: NextAction(
        label="Listo para entregar",
        hint="Avisa al cliente de que puede recoger el equipo.",
        state=OrderState.LISTO_PARA_ENTREGAR,
    ),
    OrderState.LISTO_PARA_ENTREGAR: NextAction(
        label="Entregar el equipo",
        hint="Cobra lo que falte y entrega el comprobante con la fecha de entrega.",
        delivers=True,
        document=DocumentKind.ENTREGA,
    ),
    OrderState.ENTREGADO: NextAction(
        label="Imprimir comprobante de entrega",
        hint="La orden está cerrada: reimprime el comprobante cuando haga falta.",
        document=DocumentKind.ENTREGA,
    ),
    OrderState.NO_REPARABLE: NextAction(
        label="Imprimir informe técnico",
        hint="El equipo no se repara: entrega el informe y devuélvelo al cliente.",
        document=DocumentKind.INFORME,
    ),
    OrderState.CANCELADO: NextAction(
        label="Sin acciones pendientes",
        hint="La orden está cancelada: solo queda el historial.",
    ),
}

FALLBACK = NextAction(label="Sin acciones pendientes")


def next_action(state: OrderState | str) -> NextAction:
    """Acción propuesta para ese estado; si el valor no se reconoce, una neutra."""
    try:
        return NEXT_ACTIONS[OrderState(state)]
    except ValueError:
        return FALLBACK
