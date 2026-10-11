"""Textos predefinidos para diagnóstico, trabajo y recomendaciones (§8 del ROADMAP).

Se guardan en la tabla configuracion, una frase por línea. Si nunca se han configurado,
se usan los valores por defecto de config.py.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from luciotech.config import DEFAULT_PREDEFINED_TEXTS
from luciotech.services.settings_service import get_value, set_value

KEY_PREDEFINED_TEXTS = "textos_predefinidos"


def predefined_texts(session: Session) -> list[str]:
    raw = get_value(session, KEY_PREDEFINED_TEXTS)
    if raw is None:
        return list(DEFAULT_PREDEFINED_TEXTS)
    items = [line.strip() for line in raw.splitlines() if line.strip()]
    return items or list(DEFAULT_PREDEFINED_TEXTS)


def save_predefined_texts(session: Session, texts: list[str]) -> None:
    """Reemplaza la lista completa. Descarta líneas vacías y no permite saltos de línea dentro de una frase."""
    cleaned = [" ".join(text.split()) for text in texts]
    cleaned = [text for text in cleaned if text]
    if not cleaned:
        raise ValueError("La lista de textos predefinidos no puede quedar vacía.")
    set_value(session, KEY_PREDEFINED_TEXTS, "\n".join(cleaned))
