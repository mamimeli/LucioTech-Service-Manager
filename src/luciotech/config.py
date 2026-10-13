"""Configuración centralizada de la aplicación (§1 y §2 del ROADMAP).

Cambiar el nombre, el app_id o la versión se hace únicamente aquí.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AppConfig:
    """Valores fijos de identidad de la aplicación."""

    app_name: str
    app_id: str
    organization_name: str
    application_version: str
    executable_name: str


APP_CONFIG = AppConfig(
    app_name="LucioTech Service Manager",
    app_id="luciotech-service-manager",
    organization_name="Ing. Lucio",
    application_version="0.1.0",
    executable_name="luciotech-service-manager",
)

APP_VERSION: str = APP_CONFIG.application_version

DEFAULT_TAX_PERCENT = Decimal("15")
DEFAULT_TAX_ENABLED = True
DEFAULT_CURRENCY = "USD"
DEFAULT_USER = "Ing. Lucio"

# Meses que se considera abandonado un equipo sin retirar antes de poder darlo de baja (§5.8).
DEFAULT_RETENTION_MONTHS = 6

# El marcador {meses} se sustituye por el plazo configurado al imprimir el comprobante.
DEFAULT_SERVICE_TERMS = (
    "1. El equipo se entrega únicamente contra presentación de este comprobante.\n"
    "2. El taller no responde por datos que el cliente no haya respaldado antes de dejarlo.\n"
    "3. La reparación se inicia solo con el presupuesto aprobado por el cliente.\n"
    "4. El equipo reparado queda con garantía sobre el trabajo realizado.\n"
    "5. Si el equipo no es retirado dentro de {meses} meses contados desde la fecha de ingreso, "
    "se considerará abandonado y el taller podrá darlo de baja y disponer de él."
)

DEFAULT_PREDEFINED_TEXTS: tuple[str, ...] = (
    "Se realizó inspección visual del equipo.",
    "Se realizaron pruebas de encendido.",
    "Se verificó el estado del almacenamiento.",
    "Se verificó la memoria RAM.",
    "Se recomienda realizar mantenimiento preventivo.",
    "Se recomienda reemplazar el componente defectuoso.",
    "El equipo fue probado y funciona correctamente.",
)

DEFAULT_EQUIPMENT_TYPES: tuple[str, ...] = (
    "Laptop",
    "Computadora de escritorio",
    "Impresora",
    "Cámara de seguridad",
    "DVR",
    "NVR",
    "Monitor",
    "Router",
    "Fuente de poder",
    "Otro",
)
