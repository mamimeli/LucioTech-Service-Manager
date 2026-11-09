"""Usuarios, contraseñas y sesión (§19): servicio, migración y lo que llega al papel."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from luciotech.config import DEFAULT_USER
from luciotech.database.enums import UserRole
from luciotech.database.models import User
from luciotech.services.customer_service import CustomerData
from luciotech.services.equipment_service import EquipmentData
from luciotech.services.reception_service import ReceptionData, register_reception
from luciotech.services.user_service import (
    DEFAULT_CURRENT_USER,
    MIN_PASSWORD_LENGTH,
    authenticate,
    change_own_password,
    count_users,
    create_first_admin,
    create_user,
    current_user_of,
    get_user,
    hash_password,
    list_login_users,
    list_users,
    normalize_username,
    set_active,
    set_password,
    update_user,
    validate_username,
    verify_password,
)
from luciotech.ui import documents
from luciotech.ui.dialogs.reception_dialog import ReceptionDialog

PASSWORD = "taller2026"


def _make_user(
    session: Session, username: str = "ana", role: UserRole = UserRole.TECNICO
) -> User:
    user = create_user(
        session,
        username=username,
        full_name="Ana Torres",
        password=PASSWORD,
        role=role,
    )
    session.commit()
    return user


# Contraseñas


def test_the_password_is_stored_as_a_salted_hash() -> None:
    first = hash_password(PASSWORD)
    second = hash_password(PASSWORD)
    assert first.startswith("pbkdf2_sha256$")
    assert first != second, "cada contraseña lleva su propia sal"
    assert PASSWORD not in first


def test_verify_accepts_the_right_password_and_rejects_the_rest() -> None:
    stored = hash_password(PASSWORD)
    assert verify_password(PASSWORD, stored)
    assert not verify_password("taller2027", stored)
    assert not verify_password("", stored)


def test_verify_never_raises_on_a_damaged_hash() -> None:
    for stored in ("", "basura", "pbkdf2_sha256$0$sal$abc", "otro$260000$sal$abc"):
        assert verify_password(PASSWORD, stored) is False


# Alta de usuarios


def test_create_user_normalises_the_username_and_hashes_the_password(
    session: Session,
) -> None:
    user = _make_user(session, username="  Ana.Torres  ")
    assert user.nombre_usuario == "ana.torres"
    assert user.nombre_completo == "Ana Torres"
    assert user.rol == UserRole.TECNICO.value
    assert user.activo is True
    assert user.contrasena_hash != PASSWORD


def test_the_same_username_cannot_be_used_twice_even_with_other_capitals(
    session: Session,
) -> None:
    _make_user(session, username="ana")
    with pytest.raises(ValueError, match="Ya existe"):
        create_user(session, username="ANA", full_name="Otra", password=PASSWORD)


def test_usernames_and_passwords_are_validated(session: Session) -> None:
    with pytest.raises(ValueError, match="al menos 3"):
        create_user(session, username="ab", full_name="Ana", password=PASSWORD)
    with pytest.raises(ValueError, match="sin tilde"):
        create_user(session, username="ana torres", full_name="Ana", password=PASSWORD)
    with pytest.raises(ValueError, match=f"al menos {MIN_PASSWORD_LENGTH}"):
        create_user(session, username="ana", full_name="Ana", password="corta")
    with pytest.raises(ValueError, match="nombre completo"):
        create_user(session, username="ana", full_name="   ", password=PASSWORD)


def test_validate_username_returns_the_value_that_gets_stored() -> None:
    assert validate_username(" Ana ") == "ana"
    assert normalize_username("ANA") == "ana"


def test_the_full_name_is_cleaned_up(session: Session) -> None:
    user = create_user(
        session, username="ana", full_name="  Ana   Torres  ", password=PASSWORD
    )
    assert user.nombre_completo == "Ana Torres"


def test_count_and_list_users(session: Session) -> None:
    assert count_users(session) == 0
    _make_user(session, username="ana")
    _make_user(session, username="luis")
    assert count_users(session) == 2
    assert [user.nombre_usuario for user in list_users(session)] == ["ana", "luis"]


def test_an_inactive_user_is_not_listed_as_active(session: Session) -> None:
    _make_user(session, username="ana")
    set_active(session, get_user(session, "ana"), False)  # type: ignore[arg-type]
    session.commit()
    assert list_users(session, only_active=True) == []


def test_login_users_are_active_and_the_last_one_first(session: Session) -> None:
    ana = _make_user(session, username="ana")
    luis = _make_user(session, username="luis")
    inactivo = _make_user(session, username="carmen")
    set_active(session, inactivo, False)
    ana.ultimo_acceso = datetime(2026, 1, 1, 9, 0)
    luis.ultimo_acceso = datetime(2026, 1, 2, 9, 0)
    session.commit()

    assert [user.nombre_usuario for user in list_login_users(session)] == ["luis", "ana"]


def test_login_users_who_never_signed_in_come_last(session: Session) -> None:
    ana = _make_user(session, username="ana")
    luis = _make_user(session, username="luis")
    luis.ultimo_acceso = datetime(2026, 1, 2, 9, 0)
    session.commit()
    assert ana.ultimo_acceso is None

    assert [user.nombre_usuario for user in list_login_users(session)] == ["luis", "ana"]


# Acceso


def test_authenticate_returns_the_user_with_the_right_password(session: Session) -> None:
    _make_user(session, username="ana")
    user = authenticate(session, "ANA", PASSWORD)
    assert user is not None
    assert user.nombre_usuario == "ana"


def test_authenticate_rejects_a_wrong_password(session: Session) -> None:
    _make_user(session, username="ana")
    assert authenticate(session, "ana", "otra cosa") is None


def test_authenticate_rejects_an_unknown_user(session: Session) -> None:
    assert authenticate(session, "nadie", PASSWORD) is None


def test_authenticate_rejects_a_deactivated_account(session: Session) -> None:
    user = _make_user(session, username="ana")
    set_active(session, user, False)
    session.commit()
    assert authenticate(session, "ana", PASSWORD) is None


def test_current_user_carries_the_name_that_goes_on_paper(session: Session) -> None:
    user = _make_user(session, username="ana")
    current = current_user_of(user)
    assert current.display_name == "Ana Torres"
    assert current.username == "ana"
    assert current.is_admin is False


def test_the_default_current_user_keeps_the_old_name() -> None:
    assert DEFAULT_CURRENT_USER.display_name == DEFAULT_USER
    assert DEFAULT_CURRENT_USER.is_admin is True


# Contraseñas: cambio y permisos


def test_an_admin_can_set_a_password_without_knowing_the_old_one(session: Session) -> None:
    user = _make_user(session, username="ana")
    set_password(session, user, "nueva2026")
    session.commit()
    assert authenticate(session, "ana", "nueva2026") is not None
    assert authenticate(session, "ana", PASSWORD) is None


def test_changing_your_own_password_asks_for_the_current_one(session: Session) -> None:
    user = _make_user(session, username="ana")
    with pytest.raises(ValueError, match="actual no es correcta"):
        change_own_password(session, user, "no es", "nueva2026")
    change_own_password(session, user, PASSWORD, "nueva2026")
    session.commit()
    assert authenticate(session, "ana", "nueva2026") is not None


# Roles y bajas


def test_the_last_active_admin_cannot_be_deactivated(session: Session) -> None:
    admin = _make_user(session, username="jefe", role=UserRole.ADMINISTRADOR)
    with pytest.raises(ValueError, match="al menos un administrador"):
        set_active(session, admin, False)


def test_the_last_active_admin_cannot_become_a_technician(session: Session) -> None:
    admin = _make_user(session, username="jefe", role=UserRole.ADMINISTRADOR)
    with pytest.raises(ValueError, match="al menos un administrador"):
        update_user(session, admin, role=UserRole.TECNICO)


def test_with_another_admin_in_place_the_change_is_allowed(session: Session) -> None:
    first = _make_user(session, username="jefe", role=UserRole.ADMINISTRADOR)
    _make_user(session, username="jefa", role=UserRole.ADMINISTRADOR)
    set_active(session, first, False)
    session.commit()
    assert first.activo is False


def test_update_user_changes_the_printed_name(session: Session) -> None:
    user = _make_user(session, username="ana")
    update_user(session, user, full_name="Ana María Torres")
    session.commit()
    assert current_user_of(user).display_name == "Ana María Torres"


# Primer arranque


def test_the_first_admin_is_only_created_on_an_empty_database(session: Session) -> None:
    admin = create_first_admin(
        session, username="lucio", full_name="Ing. Lucio", password=PASSWORD
    )
    session.commit()
    assert admin.rol == UserRole.ADMINISTRADOR.value
    with pytest.raises(ValueError, match="Ya hay usuarios"):
        create_first_admin(
            session, username="otro", full_name="Otro", password=PASSWORD
        )


# Migración


def test_the_users_table_arrives_with_migration_0005(tmp_path: Path) -> None:
    from alembic import command
    from alembic.config import Config

    url = f"sqlite:///{tmp_path / 'migrada.sqlite3'}"
    config = Config("alembic.ini")
    config.set_main_option("script_location", "src/luciotech/database/migrations")
    config.set_main_option("sqlalchemy.url", url)

    command.upgrade(config, "0004")
    engine = create_engine(url)
    assert "usuarios" not in inspect(engine).get_table_names()
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(url)
    columns = {column["name"] for column in inspect(engine).get_columns("usuarios")}
    engine.dispose()
    assert columns == {
        "id",
        "nombre_usuario",
        "nombre_completo",
        "contrasena_hash",
        "rol",
        "activo",
        "fecha_creacion",
        "ultimo_acceso",
    }


# Lo que llega al papel


def _order_id(session_factory: sessionmaker[Session], usuario: str) -> int:
    with session_factory() as session:
        order = register_reception(
            session,
            ReceptionData(
                equipment=EquipmentData(cliente_id=None, tipo_equipo="Laptop", marca="HP"),
                new_customer=CustomerData(
                    nombre_completo="Ana Torres", telefono_principal="0991234567"
                ),
                costo_diagnostico=Decimal("20"),
                usuario=usuario,
            ),
        )
        session.commit()
        return order.id


def test_the_footer_says_who_printed_the_document(
    session_factory: sessionmaker[Session], session: Session
) -> None:
    order_id = _order_id(session_factory, "Ana Torres")
    from luciotech.database.models import ServiceOrder

    order = session.get(ServiceOrder, order_id)
    assert order is not None
    furniture = documents._furniture(session, order, documents.DocumentKind.PRESUPUESTO, "Ana Torres")
    assert furniture.footer_left.endswith("por Ana Torres")
    assert furniture.footer_left.startswith("Generado el ")


def test_without_a_session_the_footer_has_no_name(
    session_factory: sessionmaker[Session], session: Session
) -> None:
    order_id = _order_id(session_factory, "Ana Torres")
    from luciotech.database.models import ServiceOrder

    order = session.get(ServiceOrder, order_id)
    assert order is not None
    furniture = documents._furniture(session, order, documents.DocumentKind.PRESUPUESTO)
    assert " por " not in furniture.footer_left


def test_the_reception_proposes_the_session_user_as_technician(
    qtbot: object, session_factory: sessionmaker[Session]
) -> None:
    dialog = ReceptionDialog(session_factory, usuario="Ana Torres")
    try:
        assert dialog._technician.text() == "Ana Torres"
        data = dialog._collect()
        assert data.usuario == "Ana Torres"
    finally:
        dialog.deleteLater()


def test_the_technician_of_the_order_is_the_one_who_signed_the_reception(
    session_factory: sessionmaker[Session], session: Session
) -> None:
    from luciotech.database.models import ServiceOrder

    order_id = _order_id(session_factory, "Ana Torres")
    order = session.get(ServiceOrder, order_id)
    assert order is not None
    assert order.tecnico_responsable == "Ana Torres"


def test_the_state_history_keeps_the_name_of_the_session_user(
    session_factory: sessionmaker[Session], session: Session
) -> None:
    from luciotech.database.models import ServiceOrder, StateHistory
    from luciotech.services.state_service import change_order_state
    from luciotech.database.enums import OrderState

    order_id = _order_id(session_factory, "Ana Torres")
    order = session.get(ServiceOrder, order_id)
    assert order is not None
    change_order_state(session, order, OrderState.PENDIENTE_DIAGNOSTICO, usuario="Ana Torres")
    session.commit()
    entry = session.query(StateHistory).filter_by(orden_id=order_id).order_by(
        StateHistory.id.desc()
    ).first()
    assert entry is not None
    assert entry.usuario == "Ana Torres"
