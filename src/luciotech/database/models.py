"""Modelos SQLAlchemy de LucioTech Service Manager (§5 del ROADMAP)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

MONEY = Numeric(12, 2)
ZERO = Decimal("0.00")


class Base(DeclarativeBase):
    """Base declarativa de todos los modelos."""


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre_completo: Mapped[str] = mapped_column(String(200))
    numero_identificacion: Mapped[str | None] = mapped_column(String(20), index=True)
    telefono_principal: Mapped[str | None] = mapped_column(String(30), index=True)
    telefono_secundario: Mapped[str | None] = mapped_column(String(30))
    correo_electronico: Mapped[str | None] = mapped_column(String(200))
    direccion: Mapped[str | None] = mapped_column(Text)
    notas: Mapped[str | None] = mapped_column(Text)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    equipment: Mapped[list[Equipment]] = relationship(back_populates="customer")
    orders: Mapped[list[ServiceOrder]] = relationship(back_populates="customer")


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    tipo_equipo: Mapped[str] = mapped_column(String(60))
    marca: Mapped[str | None] = mapped_column(String(100))
    modelo: Mapped[str | None] = mapped_column(String(100))
    numero_serie: Mapped[str | None] = mapped_column(String(100), index=True)
    color: Mapped[str | None] = mapped_column(String(50))
    sistema_operativo: Mapped[str | None] = mapped_column(String(100))
    contrasena_equipo: Mapped[str | None] = mapped_column(String(200))
    accesorios_recibidos: Mapped[str | None] = mapped_column(Text)
    estado_fisico: Mapped[str | None] = mapped_column(Text)
    problema_reportado_cliente: Mapped[str | None] = mapped_column(Text)
    observaciones_ingreso: Mapped[str | None] = mapped_column(Text)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    customer: Mapped[Customer] = relationship(back_populates="equipment")
    orders: Mapped[list[ServiceOrder]] = relationship(back_populates="equipment")


class ServiceOrder(Base):
    __tablename__ = "service_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    numero_orden: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    fecha_ingreso: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    fecha_estimada_entrega: Mapped[datetime | None] = mapped_column(DateTime)
    fecha_finalizacion: Mapped[datetime | None] = mapped_column(DateTime)
    fecha_entrega: Mapped[datetime | None] = mapped_column(DateTime)
    estado: Mapped[str] = mapped_column(String(40), index=True)
    prioridad: Mapped[str] = mapped_column(String(20))
    tecnico_responsable: Mapped[str | None] = mapped_column(String(100))
    problema_reportado: Mapped[str | None] = mapped_column(Text)
    diagnostico_html: Mapped[str | None] = mapped_column(Text)
    trabajo_realizado_html: Mapped[str | None] = mapped_column(Text)
    recomendaciones_html: Mapped[str | None] = mapped_column(Text)
    repuestos_utilizados: Mapped[str | None] = mapped_column(Text)
    costo_diagnostico: Mapped[Decimal] = mapped_column(MONEY, default=ZERO)
    descuento: Mapped[Decimal] = mapped_column(MONEY, default=ZERO)
    impuestos: Mapped[Decimal] = mapped_column(MONEY, default=ZERO)
    total: Mapped[Decimal] = mapped_column(MONEY, default=ZERO)
    anticipo: Mapped[Decimal] = mapped_column(MONEY, default=ZERO)
    saldo_pendiente: Mapped[Decimal] = mapped_column(MONEY, default=ZERO)
    garantia_dias: Mapped[int] = mapped_column(Integer, default=0)
    notas_internas: Mapped[str | None] = mapped_column(Text)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    fecha_eliminacion: Mapped[datetime | None] = mapped_column(DateTime)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    customer: Mapped[Customer] = relationship(back_populates="orders")
    equipment: Mapped[Equipment] = relationship(back_populates="orders")
    photographs: Mapped[list[Photograph]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="Photograph.orden_visualizacion",
    )
    state_changes: Mapped[list[StateHistory]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="StateHistory.fecha",
    )
    events: Mapped[list[OrderEvent]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderEvent.fecha",
    )
    payments: Mapped[list[Payment]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="Payment.fecha",
    )
    budget_lines: Mapped[list[BudgetLine]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="BudgetLine.id",
    )


class Photograph(Base):
    __tablename__ = "photographs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    orden_id: Mapped[int] = mapped_column(ForeignKey("service_orders.id"), index=True)
    ruta_archivo: Mapped[str] = mapped_column(String(500))
    nombre_archivo: Mapped[str] = mapped_column(String(255))
    descripcion: Mapped[str | None] = mapped_column(Text)
    tipo_fotografia: Mapped[str] = mapped_column(String(40))
    fecha_captura: Mapped[datetime | None] = mapped_column(DateTime)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    orden_visualizacion: Mapped[int] = mapped_column(Integer, default=0)

    order: Mapped[ServiceOrder] = relationship(back_populates="photographs")


class StateHistory(Base):
    __tablename__ = "state_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    orden_id: Mapped[int] = mapped_column(ForeignKey("service_orders.id"), index=True)
    estado_anterior: Mapped[str | None] = mapped_column(String(40))
    estado_nuevo: Mapped[str] = mapped_column(String(40))
    comentario: Mapped[str | None] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    usuario: Mapped[str] = mapped_column(String(100))

    order: Mapped[ServiceOrder] = relationship(back_populates="state_changes")


class OrderEvent(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    orden_id: Mapped[int] = mapped_column(ForeignKey("service_orders.id"), index=True)
    tipo_evento: Mapped[str] = mapped_column(String(60))
    titulo: Mapped[str] = mapped_column(String(200))
    descripcion: Mapped[str | None] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    usuario: Mapped[str] = mapped_column(String(100))

    order: Mapped[ServiceOrder] = relationship(back_populates="events")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    orden_id: Mapped[int] = mapped_column(ForeignKey("service_orders.id"), index=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    tipo_pago: Mapped[str] = mapped_column(String(40))
    metodo_pago: Mapped[str] = mapped_column(String(40))
    monto: Mapped[Decimal] = mapped_column(MONEY)
    referencia: Mapped[str | None] = mapped_column(String(100))
    observaciones: Mapped[str | None] = mapped_column(Text)
    anulado: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_anulacion: Mapped[datetime | None] = mapped_column(DateTime)
    motivo_anulacion: Mapped[str | None] = mapped_column(Text)

    order: Mapped[ServiceOrder] = relationship(back_populates="payments")


class BudgetLine(Base):
    """Línea de presupuesto de una orden (§12): tipo, descripción, cantidad y precio."""

    __tablename__ = "budget_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    orden_id: Mapped[int] = mapped_column(ForeignKey("service_orders.id"), index=True)
    tipo_linea: Mapped[str] = mapped_column(String(40))
    descripcion: Mapped[str] = mapped_column(Text)
    cantidad: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    precio_unitario: Mapped[Decimal] = mapped_column(MONEY)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    order: Mapped[ServiceOrder] = relationship(back_populates="budget_lines")


class Configuration(Base):
    """Configuración de negocio en formato clave/valor (§5.8)."""

    __tablename__ = "configuracion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clave: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    valor: Mapped[str | None] = mapped_column(Text)


class NumberSequence(Base):
    """Contadores atómicos para la numeración de órdenes (p. ej. 'OT-2026')."""

    __tablename__ = "secuencias"

    clave: Mapped[str] = mapped_column(String(50), primary_key=True)
    ultimo_valor: Mapped[int] = mapped_column(Integer, default=0)
