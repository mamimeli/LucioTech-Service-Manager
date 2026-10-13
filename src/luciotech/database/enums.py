"""Enumeraciones del dominio (§5.3 a §5.7 del ROADMAP)."""

from __future__ import annotations

from enum import StrEnum


class OrderState(StrEnum):
    RECIBIDO = "Recibido"
    PENDIENTE_DIAGNOSTICO = "Pendiente de diagnóstico"
    DIAGNOSTICADO = "Diagnosticado"
    ESPERANDO_APROBACION = "Esperando aprobación"
    ESPERANDO_REPUESTO = "Esperando repuesto"
    EN_REPARACION = "En reparación"
    REPARADO = "Reparado"
    LISTO_PARA_ENTREGAR = "Listo para entregar"
    ENTREGADO = "Entregado"
    NO_REPARABLE = "No reparable"
    CANCELADO = "Cancelado"


class Priority(StrEnum):
    BAJA = "Baja"
    NORMAL = "Normal"
    ALTA = "Alta"
    URGENTE = "Urgente"


class PhotoType(StrEnum):
    ESTADO_AL_RECIBIR = "Estado al recibir"
    NUMERO_DE_SERIE = "Número de serie"
    ACCESORIOS = "Accesorios"
    DANO_FISICO = "Daño físico"
    PROCESO_DE_REPARACION = "Proceso de reparación"
    EQUIPO_REPARADO = "Equipo reparado"
    OTRO = "Otro"


class PaymentType(StrEnum):
    ANTICIPO = "Anticipo"
    ABONO = "Abono"
    PAGO_FINAL = "Pago final"
    REEMBOLSO = "Reembolso"


class PaymentMethod(StrEnum):
    EFECTIVO = "Efectivo"
    TRANSFERENCIA = "Transferencia bancaria"
    TARJETA = "Tarjeta"
    DEPOSITO = "Depósito"
    OTRO = "Otro"


class EventType(StrEnum):
    LLAMADA_CLIENTE = "Llamada al cliente"
    MENSAJE_ENVIADO = "Mensaje enviado"
    PRESUPUESTO_APROBADO = "Presupuesto aprobado"
    PRESUPUESTO_RECHAZADO = "Presupuesto rechazado"
    REPUESTO_SOLICITADO = "Repuesto solicitado"
    REPUESTO_RECIBIDO = "Repuesto recibido"
    DIAGNOSTICO_ACTUALIZADO = "Diagnóstico actualizado"
    PAGO_RECIBIDO = "Pago recibido"
    PAGO_ANULADO = "Pago anulado"
    EQUIPO_ENTREGADO = "Equipo entregado"
    NOTA_INTERNA = "Nota interna"
    ORDEN_ELIMINADA = "Orden eliminada"
    ORDEN_RESTAURADA = "Orden restaurada"


class BudgetLineType(StrEnum):
    DIAGNOSTICO = "Diagnóstico"
    MANO_OBRA = "Mano de obra"
    REPUESTO = "Repuesto"
    ACCESORIO = "Accesorio"
    SERVICIO = "Servicio"
    OTRO = "Otro"
