"""Pruebas del paso 2: modelos, conexión y migración inicial sobre base temporal."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from luciotech.database.connection import create_db_engine, create_session_factory
from luciotech.database.enums import OrderState, Priority
from luciotech.database.models import Base, Customer, Equipment, ServiceOrder

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_TABLES = {
    "customers",
    "equipment",
    "service_orders",
    "photographs",
    "state_history",
    "events",
    "payments",
    "budget_lines",
    "configuracion",
    "secuencias",
}


@pytest.fixture
def alembic_config(tmp_path: Path) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option(
        "script_location", str(ROOT / "src" / "luciotech" / "database" / "migrations")
    )
    config.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path / 'test.sqlite3'}")
    return config


@pytest.fixture
def engine(alembic_config: Config):
    command.upgrade(alembic_config, "head")
    db_engine = create_db_engine(alembic_config.get_main_option("sqlalchemy.url"))
    yield db_engine
    db_engine.dispose()


def _create_customer_and_equipment(session: Session) -> tuple[Customer, Equipment]:
    customer = Customer(nombre_completo="Juan Pérez", numero_identificacion="1712345678")
    equipment = Equipment(customer=customer, tipo_equipo="Laptop", marca="HP")
    session.add_all([customer, equipment])
    session.flush()
    return customer, equipment


def test_migration_creates_all_tables(engine: Engine) -> None:
    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())


def test_models_match_migration(engine: Engine) -> None:
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == []


def test_the_ghost_cost_columns_are_gone(engine: Engine) -> None:
    """`costo_repuestos` y `costo_mano_obra` nunca se editaron y valían cero: fuera (§5.3)."""
    columns = {column["name"] for column in inspect(engine).get_columns("service_orders")}
    assert "costo_repuestos" not in columns
    assert "costo_mano_obra" not in columns
    assert "costo_diagnostico" in columns


def test_the_ghost_costs_can_come_back_without_losing_orders(
    alembic_config: Config,
) -> None:
    """Bajar y volver a subir la migración no puede llevarse por delante ninguna orden."""
    url = alembic_config.get_main_option("sqlalchemy.url")
    assert url is not None
    command.upgrade(alembic_config, "head")

    engine = create_db_engine(url)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        customer, equipment = _create_customer_and_equipment(session)
        order = ServiceOrder(
            numero_orden="OT-2026-000009",
            customer=customer,
            equipment=equipment,
            prioridad=Priority.NORMAL,
            estado=OrderState.RECIBIDO,
            costo_diagnostico=Decimal("15"),
            anticipo=Decimal("5"),
        )
        session.add(order)
        session.commit()
        order_id = order.id
    engine.dispose()

    command.downgrade(alembic_config, "0003")
    engine = create_db_engine(url)
    with engine.connect() as connection:
        columns = {column["name"] for column in inspect(engine).get_columns("service_orders")}
        assert {"costo_repuestos", "costo_mano_obra"} <= columns
        values = connection.execute(
            text("select costo_repuestos, costo_mano_obra from service_orders")
        ).all()
    assert values == [(Decimal("0.00"), Decimal("0.00"))]
    engine.dispose()

    command.upgrade(alembic_config, "head")
    engine = create_db_engine(url)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        saved = session.get(ServiceOrder, order_id)
        assert saved is not None
        assert saved.numero_orden == "OT-2026-000009"
        assert saved.costo_diagnostico == Decimal("15.00")
        assert saved.anticipo == Decimal("5.00")
    engine.dispose()


def test_downgrade_removes_tables(alembic_config: Config, engine: Engine) -> None:
    command.downgrade(alembic_config, "base")
    assert not (EXPECTED_TABLES & set(inspect(engine).get_table_names()))


def test_order_defaults_are_applied(engine: Engine) -> None:
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        customer, equipment = _create_customer_and_equipment(session)
        order = ServiceOrder(
            numero_orden="OT-2026-000001",
            customer=customer,
            equipment=equipment,
            prioridad=Priority.NORMAL,
            estado=OrderState.RECIBIDO,
        )
        session.add(order)
        session.commit()

        saved = session.get(ServiceOrder, order.id)
        assert saved is not None
        assert saved.estado == OrderState.RECIBIDO
        assert saved.activo is True
        assert saved.total == Decimal("0.00")
        assert saved.saldo_pendiente == Decimal("0.00")
        assert isinstance(saved.fecha_ingreso, datetime)
        assert saved.customer.nombre_completo == "Juan Pérez"
        assert saved.equipment.tipo_equipo == "Laptop"


def test_foreign_keys_are_enforced(engine: Engine) -> None:
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        session.add(Equipment(cliente_id=999, tipo_equipo="Impresora"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_duplicate_order_number_is_rejected(engine: Engine) -> None:
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        customer, equipment = _create_customer_and_equipment(session)
        session.add(
            ServiceOrder(
                numero_orden="OT-2026-000001",
                customer=customer,
                equipment=equipment,
                prioridad=Priority.NORMAL,
                estado=OrderState.RECIBIDO,
            )
        )
        session.commit()

        session.add(
            ServiceOrder(
                numero_orden="OT-2026-000001",
                customer=customer,
                equipment=equipment,
                prioridad=Priority.ALTA,
                estado=OrderState.RECIBIDO,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
