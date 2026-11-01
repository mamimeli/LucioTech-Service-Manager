"""Entrada a la aplicación: acceso con usuario y contraseña, y creación del primer usuario (§19).

Son dos diálogos distintos porque son dos momentos distintos:

- `FirstUserDialog` sale una sola vez, la primera vez que se abre la aplicación en un equipo,
  cuando la tabla `usuarios` está vacía. No se pide una contraseña que nadie conoce: se crea la
  cuenta de administrador del taller.
- `LoginDialog` es el de todos los días: nombre de acceso y contraseña.

Los dos devuelven en `self.user` un `CurrentUser`, que es lo que después viaja a la ventana, al
historial de las órdenes y al pie de los documentos.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from luciotech.config import APP_CONFIG, DEFAULT_USER
from luciotech.database.models import User
from luciotech.services.user_service import (
    CurrentUser,
    authenticate,
    change_own_password,
    create_first_admin,
    current_user_of,
    has_users,
    touch_login,
)

ERROR_STYLE = "color: #b00020;"


class LoginDialog(QDialog):
    """Pide usuario y contraseña; deja la cuenta en `self.user` si el acceso es correcto."""

    def __init__(
        self, session_factory: sessionmaker[Session], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self.user: CurrentUser | None = None
        self.attempts = 0

        self.setWindowTitle(self.tr("Entrar"))
        self.setMinimumWidth(420)

        title = QLabel(APP_CONFIG.app_name)
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 4)
        title_font.setBold(True)
        title.setFont(title_font)

        subtitle = QLabel(self.tr("Escriba su usuario y su contraseña para abrir el taller."))
        subtitle.setWordWrap(True)

        self._username = QLineEdit()
        self._username.setPlaceholderText(self.tr("Nombre de usuario"))
        self._username.setClearButtonEnabled(True)
        self._password = QLineEdit()
        self._password.setPlaceholderText(self.tr("Contraseña"))
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._show_password = QCheckBox(self.tr("Mostrar contraseña"))
        self._show_password.toggled.connect(self._on_show_password)

        form = QFormLayout()
        form.addRow(self.tr("Usuario"), self._username)
        form.addRow(self.tr("Contraseña"), self._password)

        self._message = QLabel()
        self._message.setWordWrap(True)
        self._message.setStyleSheet(ERROR_STYLE)

        buttons = QDialogButtonBox()
        self._enter_button = buttons.addButton(
            self.tr("Entrar"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._enter_button.setDefault(True)
        buttons.addButton(self.tr("Salir"), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._attempt_login)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(form)
        layout.addWidget(self._show_password)
        layout.addWidget(self._message)
        layout.addWidget(buttons)

        self._username.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_show_password(self, shown: bool) -> None:
        self._password.setEchoMode(
            QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password
        )

    def _attempt_login(self) -> None:
        username = self._username.text().strip()
        password = self._password.text()
        if not username or not password:
            self._message.setText(self.tr("Escriba el usuario y la contraseña."))
            return
        self.attempts += 1
        try:
            with self._session_factory() as session:
                user = authenticate(session, username, password)
                if user is None:
                    self._message.setText(self.tr("Usuario o contraseña incorrectos."))
                    self._password.clear()
                    self._password.setFocus(Qt.FocusReason.OtherFocusReason)
                    return
                touch_login(session, user)
                session.commit()
                self.user = current_user_of(user)
        except SQLAlchemyError:
            self._message.setText(self.tr("No se pudo comprobar el acceso. Intente de nuevo."))
            return
        self.accept()


class FirstUserDialog(QDialog):
    """Crea la cuenta de administrador cuando el equipo todavía no tiene usuarios."""

    def __init__(
        self, session_factory: sessionmaker[Session], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self.user: CurrentUser | None = None

        self.setWindowTitle(self.tr("Crear el primer usuario"))
        self.setMinimumWidth(460)

        title = QLabel(self.tr("Bienvenido a %1").replace("%1", APP_CONFIG.app_name))
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 4)
        title_font.setBold(True)
        title.setFont(title_font)

        explanation = QLabel(
            self.tr(
                "Todavía no hay ninguna cuenta en este equipo. Cree la del administrador del "
                "taller: será la que aparezca en los documentos que imprima y la que podrá "
                "añadir a los demás técnicos después, desde Archivo ▸ Usuarios."
            )
        )
        explanation.setWordWrap(True)

        self._full_name = QLineEdit(DEFAULT_USER)
        self._full_name.setPlaceholderText(self.tr("Nombre y apellido, como debe salir impreso"))
        self._username = QLineEdit()
        self._username.setPlaceholderText(self.tr("Para entrar; sin espacios ni tildes"))
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._repeat = QLineEdit()
        self._repeat.setEchoMode(QLineEdit.EchoMode.Password)

        form = QFormLayout()
        form.addRow(self.tr("Nombre completo"), self._full_name)
        form.addRow(self.tr("Usuario"), self._username)
        form.addRow(self.tr("Contraseña"), self._password)
        form.addRow(self.tr("Repetir contraseña"), self._repeat)

        self._message = QLabel()
        self._message.setWordWrap(True)
        self._message.setStyleSheet(ERROR_STYLE)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addLayout(form)
        layout.addWidget(self._message)
        layout.addWidget(buttons)

        self._username.setFocus(Qt.FocusReason.OtherFocusReason)

    def _save(self) -> None:
        if self._password.text() != self._repeat.text():
            self._message.setText(self.tr("Las dos contraseñas no coinciden."))
            self._repeat.clear()
            self._repeat.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        try:
            with self._session_factory() as session:
                user = create_first_admin(
                    session,
                    username=self._username.text(),
                    full_name=self._full_name.text(),
                    password=self._password.text(),
                )
                session.commit()
                self.user = current_user_of(user)
        except ValueError as exc:
            self._message.setText(str(exc))
            return
        except SQLAlchemyError:
            self._message.setText(self.tr("No se pudo crear el usuario. Intente de nuevo."))
            return
        self.accept()


class ChangePasswordDialog(QDialog):
    """Cambio de contraseña de la propia cuenta: pide la actual y la repite."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        user_id: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._user_id = user_id
        self.setWindowTitle(self.tr("Cambiar mi contraseña"))
        self.setMinimumWidth(420)

        self._current = QLineEdit()
        self._current.setEchoMode(QLineEdit.EchoMode.Password)
        self._new = QLineEdit()
        self._new.setEchoMode(QLineEdit.EchoMode.Password)
        self._repeat = QLineEdit()
        self._repeat.setEchoMode(QLineEdit.EchoMode.Password)

        form = QFormLayout()
        form.addRow(self.tr("Contraseña actual"), self._current)
        form.addRow(self.tr("Contraseña nueva"), self._new)
        form.addRow(self.tr("Repetir la nueva"), self._repeat)

        self._message = QLabel()
        self._message.setWordWrap(True)
        self._message.setStyleSheet(ERROR_STYLE)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._message)
        layout.addWidget(buttons)

        self._current.setFocus(Qt.FocusReason.OtherFocusReason)

    def _save(self) -> None:
        if self._new.text() != self._repeat.text():
            self._message.setText(self.tr("Las dos contraseñas nuevas no coinciden."))
            return
        try:
            with self._session_factory() as session:
                user = session.get(User, self._user_id)
                if user is None:
                    self._message.setText(self.tr("El usuario ya no existe."))
                    return
                change_own_password(session, user, self._current.text(), self._new.text())
                session.commit()
        except ValueError as exc:
            self._message.setText(str(exc))
            return
        except SQLAlchemyError:
            self._message.setText(self.tr("No se pudo cambiar la contraseña. Intente de nuevo."))
            return
        self.accept()


def login_user(
    session_factory: sessionmaker[Session], parent: QWidget | None = None
) -> CurrentUser | None:
    """Abre el diálogo que toca: crear el primer usuario o pedir el acceso.

    Devuelve `None` si el usuario cierra el diálogo sin entrar.
    """
    with session_factory() as session:
        first_time = not has_users(session)
    dialog = (
        FirstUserDialog(session_factory, parent)
        if first_time
        else LoginDialog(session_factory, parent)
    )
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.user
