"""Diálogos de acceso y de gestión de usuarios (§19)."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QDialog, QLabel, QLineEdit, QMessageBox
from pytestqt.qtbot import QtBot
from sqlalchemy.orm import Session, sessionmaker

from luciotech.database.enums import UserRole
from luciotech.services.user_service import (
    CurrentUser,
    authenticate,
    count_users,
    create_user,
    get_user,
    list_users,
)
from luciotech.ui.dialogs.login_dialog import (
    ChangePasswordDialog,
    FirstUserDialog,
    LoginDialog,
)
from luciotech.ui.dialogs.users_dialog import (
    SetPasswordDialog,
    UserFormDialog,
    UsersDialog,
)
from luciotech.ui.main_window import MainWindow

PASSWORD = "taller2026"


def _seed(session_factory: sessionmaker[Session]) -> CurrentUser:
    with session_factory() as session:
        user = create_user(
            session,
            username="ana",
            full_name="Ana Torres",
            password=PASSWORD,
            role=UserRole.ADMINISTRADOR,
        )
        session.commit()
        return CurrentUser(user.id, user.nombre_usuario, user.nombre_completo, user.rol)


# Primer arranque


def test_the_first_user_dialog_creates_the_admin_account(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    dialog = FirstUserDialog(session_factory)
    qtbot.addWidget(dialog)
    dialog._full_name.setText("Ing. Lucio")
    dialog._username.setText("lucio")
    dialog._password.setText(PASSWORD)
    dialog._repeat.setText(PASSWORD)

    dialog._save()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.user is not None
    assert dialog.user.is_admin is True
    assert dialog.user.display_name == "Ing. Lucio"
    assert count_users(_session(session_factory)) == 1


def test_the_first_user_dialog_asks_for_the_same_password_twice(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    dialog = FirstUserDialog(session_factory)
    qtbot.addWidget(dialog)
    dialog._full_name.setText("Ing. Lucio")
    dialog._username.setText("lucio")
    dialog._password.setText(PASSWORD)
    dialog._repeat.setText("otra cosa")

    dialog._save()

    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "no coinciden" in dialog._message.text()
    assert count_users(_session(session_factory)) == 0


def _session(session_factory: sessionmaker[Session]) -> Session:
    return session_factory()


# Acceso


def test_login_accepts_the_right_password_and_notes_the_access(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    _seed(session_factory)
    dialog = LoginDialog(session_factory)
    qtbot.addWidget(dialog)
    dialog._username.setText("ANA")
    dialog._password.setText(PASSWORD)

    dialog._attempt_login()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.user is not None
    assert dialog.user.display_name == "Ana Torres"
    with session_factory() as session:
        assert get_user(session, "ana").ultimo_acceso is not None


def test_login_rejects_a_wrong_password_and_keeps_the_window_open(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    _seed(session_factory)
    dialog = LoginDialog(session_factory)
    qtbot.addWidget(dialog)
    dialog._username.setText("ana")
    dialog._password.setText("no es esta")

    dialog._attempt_login()

    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog.user is None
    assert "incorrectos" in dialog._message.text()
    assert dialog._password.text() == ""
    assert dialog.attempts == 1


def test_login_complains_when_a_field_is_empty(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    _seed(session_factory)
    dialog = LoginDialog(session_factory)
    qtbot.addWidget(dialog)
    dialog._username.setText("ana")

    dialog._attempt_login()

    assert "Escriba" in dialog._message.text()
    assert dialog.attempts == 0


def test_login_can_show_the_password_while_typing(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    dialog = LoginDialog(session_factory)
    qtbot.addWidget(dialog)
    assert dialog._password.echoMode() == QLineEdit.EchoMode.Password

    dialog._show_password.setChecked(True)

    assert dialog._password.echoMode() == QLineEdit.EchoMode.Normal


# Gestión de usuarios


def test_the_users_dialog_lists_the_accounts(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    admin = _seed(session_factory)
    with session_factory() as session:
        create_user(session, username="luis", full_name="Luis Paredes", password=PASSWORD)
        session.commit()

    dialog = UsersDialog(session_factory, admin)
    qtbot.addWidget(dialog)

    assert dialog._table.rowCount() == 2
    assert dialog._table.item(0, 0).text() == "ana"
    assert dialog._table.item(0, 2).text() == UserRole.ADMINISTRADOR.value


def test_the_buttons_stay_disabled_until_a_row_is_chosen(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    admin = _seed(session_factory)
    dialog = UsersDialog(session_factory, admin)
    qtbot.addWidget(dialog)

    assert not dialog._edit_button.isEnabled()
    assert not dialog._password_button.isEnabled()
    assert not dialog._active_button.isEnabled()

    dialog._table.selectRow(0)

    assert dialog._edit_button.isEnabled()


def test_the_admin_cannot_deactivate_his_own_account(
    qtbot: QtBot, session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = _seed(session_factory)
    shown: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda _parent, _title, text: shown.append(text)
    )
    dialog = UsersDialog(session_factory, admin)
    qtbot.addWidget(dialog)
    dialog._table.selectRow(0)

    dialog._toggle_active()

    assert shown and "No puede desactivar" in shown[0]
    with session_factory() as session:
        assert get_user(session, "ana").activo is True


def test_deactivating_another_user_keeps_the_row_but_marks_it(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    admin = _seed(session_factory)
    with session_factory() as session:
        create_user(session, username="luis", full_name="Luis Paredes", password=PASSWORD)
        session.commit()
    dialog = UsersDialog(session_factory, admin)
    qtbot.addWidget(dialog)
    dialog._table.selectRow(1)

    dialog._toggle_active()

    assert dialog._table.item(1, 3).text() == "Desactivado"
    assert dialog._active_button.text() == "Activar"
    with session_factory() as session:
        assert authenticate(session, "luis", PASSWORD) is None


def test_the_form_creates_a_user_with_its_password(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    dialog = UserFormDialog(session_factory)
    qtbot.addWidget(dialog)
    dialog._full_name.setText("Luis Paredes")
    dialog._username.setText("Luis")
    dialog._password.setText(PASSWORD)
    dialog._repeat.setText(PASSWORD)
    dialog._role.setCurrentIndex(dialog._role.findData(UserRole.TECNICO.value))

    dialog._save()

    assert dialog.result() == QDialog.DialogCode.Accepted
    with session_factory() as session:
        user = get_user(session, "luis")
        assert user is not None
        assert user.nombre_completo == "Luis Paredes"
        assert user.rol == UserRole.TECNICO.value


def test_the_form_does_not_change_the_username_of_an_existing_user(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    admin = _seed(session_factory)
    dialog = UserFormDialog(session_factory, admin.id)
    qtbot.addWidget(dialog)

    assert dialog._username.isReadOnly()
    assert dialog._username.text() == "ana"

    dialog._full_name.setText("Ana María Torres")
    dialog._save()

    with session_factory() as session:
        user = get_user(session, "ana")
        assert user is not None
        assert user.nombre_completo == "Ana María Torres"


def test_an_admin_can_reset_a_password(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    admin = _seed(session_factory)
    dialog = SetPasswordDialog(session_factory, admin.id)
    qtbot.addWidget(dialog)
    dialog._password.setText("nueva2026")
    dialog._repeat.setText("nueva2026")

    dialog._save()

    with session_factory() as session:
        assert authenticate(session, "ana", "nueva2026") is not None


def test_changing_your_own_password_needs_the_current_one(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    admin = _seed(session_factory)
    dialog = ChangePasswordDialog(session_factory, admin.id)
    qtbot.addWidget(dialog)
    dialog._current.setText("no es")
    dialog._new.setText("nueva2026")
    dialog._repeat.setText("nueva2026")

    dialog._save()

    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "actual no es correcta" in dialog._message.text()

    dialog._current.setText(PASSWORD)
    dialog._save()

    with session_factory() as session:
        assert authenticate(session, "ana", "nueva2026") is not None


# La sesión en la ventana principal


def _menu_titles(window: MainWindow) -> list[str]:
    menu = window.menuBar().actions()[0].menu()
    return [action.text() for action in menu.actions()]


def test_the_window_shows_who_is_logged_in(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    admin = _seed(session_factory)
    window = MainWindow(session_factory, admin)
    qtbot.addWidget(window)

    labels = [label.text() for label in window.statusBar().findChildren(QLabel)]
    assert window.user.display_name == "Ana Torres"
    assert any("Ana Torres" in text for text in labels)


def test_an_admin_sees_the_users_menu_and_a_technician_does_not(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    admin = _seed(session_factory)
    technician = CurrentUser(id=99, username="luis", full_name="Luis", role=UserRole.TECNICO.value)

    admin_window = MainWindow(session_factory, admin)
    qtbot.addWidget(admin_window)
    technician_window = MainWindow(session_factory, technician)
    qtbot.addWidget(technician_window)

    assert "&Usuarios…" in _menu_titles(admin_window)
    assert "&Usuarios…" not in _menu_titles(technician_window)
    assert "&Cerrar sesión" in _menu_titles(technician_window)


def test_logging_out_closes_the_window_and_asks_for_the_login_again(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    admin = _seed(session_factory)
    window = MainWindow(session_factory, admin)
    qtbot.addWidget(window)
    assert window.logout_requested is False

    window._logout()

    assert window.logout_requested is True


def test_the_orders_page_uses_the_name_of_the_session(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    admin = _seed(session_factory)
    window = MainWindow(session_factory, admin)
    qtbot.addWidget(window)

    assert window.orders_page._usuario == "Ana Torres"


def test_the_users_of_the_database_survive_a_new_session(
    session_factory: sessionmaker[Session]
) -> None:
    _seed(session_factory)
    with session_factory() as session:
        assert [user.nombre_usuario for user in list_users(session)] == ["ana"]
