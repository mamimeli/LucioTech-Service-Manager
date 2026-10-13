"""Textos visibles para errores de validación y nombres de campos."""

from __future__ import annotations

from PyQt6.QtCore import QCoreApplication

_CONTEXT = "LucioTech"

_ERROR_TEXTS = {
    "required": "Campo obligatorio.",
    "cedula.length": "La cédula debe tener 10 dígitos.",
    "cedula.not_digits": "La cédula solo puede contener números.",
    "cedula.province": "Código de provincia no válido (01 a 24, o 30).",
    "cedula.third_digit": "El tercer dígito debe estar entre 0 y 5 para personas naturales.",
    "cedula.check_digit": "La cédula no es válida (dígito verificador).",
    "phone.invalid_chars": "El teléfono solo puede tener números, espacios, +, - y paréntesis.",
    "phone.length": "El teléfono debe tener entre 7 y 15 dígitos.",
    "email.invalid": "Correo electrónico no válido.",
    "invalid_type": "Seleccione un tipo de equipo de la lista.",
    "not_found": "El cliente seleccionado ya no existe.",
    "customer.required": "Seleccione un cliente existente o complete los datos de cliente nuevo.",
    "amount.negative": "El importe no puede ser negativo.",
    "amount.invalid": "Importe no válido. Use solo números y punto decimal.",
    "anticipo.exceeds_total": "El anticipo no puede superar el total con impuestos.",
    "date.before_entry": "La fecha estimada no puede ser anterior a la fecha de ingreso.",
    "amount.must_be_positive": "El importe debe ser mayor que cero.",
    "refund.exceeds_paid": "No se puede reembolsar más de lo pagado.",
    "deposit.already_registered": (
        "Ya hay un anticipo registrado en la recepción; este pago se restará además de ese anticipo."
    ),
    "payment.already_voided": "Este pago ya estaba anulado.",
    "equipment.other_customer": "El equipo elegido no pertenece a este cliente.",
}

_FIELD_LABELS = {
    "nombre_completo": "Nombre completo",
    "numero_identificacion": "Cédula, RUC o identificación",
    "telefono_principal": "Teléfono principal",
    "telefono_secundario": "Teléfono secundario",
    "correo_electronico": "Correo electrónico",
    "cliente_id": "Cliente",
    "tipo_equipo": "Tipo de equipo",
    "cliente": "Cliente",
    "costo_diagnostico": "Costo de diagnóstico",
    "anticipo": "Anticipo recibido",
    "descuento": "Descuento",
    "cantidad": "Cantidad",
    "precio_unitario": "Precio unitario",
    "descripcion": "Descripción",
    "tipo_linea": "Tipo",
    "fecha_estimada_entrega": "Fecha estimada de entrega",
    "equipo": "Equipo",
}


def error_text(code: str) -> str:
    source = _ERROR_TEXTS.get(code)
    if source is None:
        return code
    return QCoreApplication.translate(_CONTEXT, source)


def field_label(field: str) -> str:
    source = _FIELD_LABELS.get(field)
    if source is None:
        return field
    return QCoreApplication.translate(_CONTEXT, source)
