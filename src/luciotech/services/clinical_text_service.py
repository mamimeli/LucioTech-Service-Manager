"""Textos clínicos de la orden: diagnóstico, trabajo realizado y recomendaciones (§8 del ROADMAP).

Los textos se guardan como HTML en las columnas diagnostico_html, trabajo_realizado_html
y recomendaciones_html. El servicio no interpreta el HTML: el editor es quien lo genera.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from luciotech.database.models import ServiceOrder


@dataclass(frozen=True)
class ClinicalTexts:
    diagnostico_html: str
    trabajo_realizado_html: str
    recomendaciones_html: str


def get_clinical_texts(order: ServiceOrder) -> ClinicalTexts:
    return ClinicalTexts(
        diagnostico_html=order.diagnostico_html or "",
        trabajo_realizado_html=order.trabajo_realizado_html or "",
        recomendaciones_html=order.recomendaciones_html or "",
    )


def save_clinical_texts(session: Session, order: ServiceOrder, texts: ClinicalTexts) -> None:
    """Reemplaza los tres textos de la orden. El llamador decide el commit."""
    order.diagnostico_html = texts.diagnostico_html
    order.trabajo_realizado_html = texts.trabajo_realizado_html
    order.recomendaciones_html = texts.recomendaciones_html
    session.flush()
