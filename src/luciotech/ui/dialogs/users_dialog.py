"""Gestión de usuarios del taller (§19): crear, editar, cambiar contraseña y dar de baja.

Solo el administrador abre esta ventana. Las cuentas no se borran: se desactivan, porque el
historial de las órdenes guarda el nombre de quien hizo cada cambio y ese nombre tiene que
seguir significando algo dentro de dos años.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from luciotech.database.enums import UserRole
from luciotech.database.models import User
from luciotech.services.user_service import (
    CurrentUser,
    create_user,
    list_users,
    set_active,
    set_password,
    update_user,
)
from luciotech.ui.formatting import format_datetime

COLUMNS = ("Usuario", "Nombre completo", "Rol", "Estado", "Último acceso")
ERROR_STYLE = "color: #b00020;"


class UserFormDialog(QDialog):
    """Alta de un usuario nuevo o edición del nombre y el rol de uno existente."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        user_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._user_id = user_id
        self.setWindowTitle(
            self.tr("Editar usuario") if user_id is not None else self.tr("Nuevo usuario")
        )
        self.setMinimumWidth(440)

        self._full_name = QLineEdit()
        self._full_name.setPlaceholderText(self.tr("Como debe salir en los documentos"))
        self._username = QLineEdit()
        self._username.setPlaceholderText(self.tr("Para entrar; sin espacios ni tildes"))
        self._role = QComboBox()
        for role in UserRole:
            self._role.addItem(role.value, role.value)
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._repeat = QLineEdit()
        self._repeat.setEchoMode(QLineEdit.EchoMode.Password)

        form = QFormLayout()
        form.addRow(self.tr("Nombre completo") + " *", self._full_name)
        form.addRow(self.tr("Usuario") + " *", self._username)
        form.addRow(self.tr("Rol"), self._role)
        if user_id is None:
            form.addRow(self.tr("Contraseña") + " *", self._password)
            form.addRow(self.tr("Repetir contraseña") + " *", self._repeat)

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

        if user_id is not None:
            self._load(user_id)

    def _load(self, user_id: int) -> None:
        with self._session_factory() as session:
            user = session.get(User, user_id)
            if user is None:
                return
            self._full_name.setText(user.nombre_completo)
            self._username.setText(user.nombre_usuario)
            # El nombre de acceso no se cambia: es la firma que queda en el historial.
            self._username.setReadOnly(True)
            self._username.setToolTip(
                self.tr("El nombre de usuario no se puede cambiar una vez creado.")
            )
            index = self._role.findData(user.rol)
            if index >= 0:
                self._role.setCurrentIndex(index)

    def _save(self) -> None:
        if self._user_id is None and self._password.text() != self._repeat.text():
            self._message.setText(self.tr("Las dos contraseñas no coinciden."))
            return
        try:
            with self._session_factory() as session:
                if self._user_id is None:
                    create_user(
                        session,
                        username=self._username.text(),
                        full_name=self._full_name.text(),
                        password=self._password.text(),
                        role=self._role.currentData(),
                    )
                else:
                    user = session.get(User, self._user_id)
                    if user is None:
                        self._message.setText(self.tr("El usuario ya no existe."))
                        return
                    update_user(
                        session, user, full_name=self._full_name.text(), role=self._role.currentData()
                    )
                session.commit()
        except ValueError as exc:
            self._message.setText(str(exc))
            return
        except SQLAlchemyError:
            self._message.setText(self.tr("No se pudo guardar el usuario. Intente de nuevo."))
            return
        self.accept()


class UsersDialog(QDialog):
    """Lista de usuarios con las acciones de administración."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        current_user: CurrentUser,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._current_user = current_user
        self.setWindowTitle(self.tr("Usuarios"))
        self.setMinimumSize(720, 420)

        self._table = QTableWidget(0, len(COLUMNS))
        self._table.setHorizontalHeaderLabels([self.tr(c) for c in COLUMNS])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        for column in range(len(COLUMNS)):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.Stretch
                if COLUMNS[column] == "Nombre completo"
                else QHeaderView.ResizeMode.ResizeToContents,
            )
        self._table.doubleClicked.connect(lambda _index: self._edit_selected())
        self._user_ids: list[int] = []

        self._new_button = QPushButton(self.tr("Nuevo usuario…"))
        self._new_button.clicked.connect(self._new_user)
        self._edit_button = QPushButton(self.tr("Editar…"))
        self._edit_button.clicked.connect(self._edit_selected)
        self._password_button = QPushButton(self.tr("Cambiar contraseña…"))
        self._password_button.clicked.connect(self._change_password)
        self._active_button = QPushButton(self.tr("Desactivar"))
        self._active_button.clicked.connect(self._toggle_active)

        top = QHBoxLayout()
        top.addWidget(self._new_button)
        top.addWidget(self._edit_button)
        top.addWidget(self._password_button)
        top.addWidget(self._active_button)
        top.addStretch(1)

        note = QLabel(
            self.tr(
                "El nombre completo es el que aparece en el historial de las órdenes y en el "
                "pie de los documentos que imprime cada usuario."
            )
        )
        note.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self._table, 1)
        layout.addWidget(note)
        layout.addWidget(buttons)

        self._table.itemSelectionChanged.connect(self._update_buttons)
        self.refresh()

    def refresh(self) -> None:
        with self._session_factory() as session:
            users = list_users(session)
        self._user_ids = [user.id for user in users]
        self._table.setRowCount(len(users))
        for row, user in enumerate(users):
            cells = (
                user.nombre_usuario,
                user.nombre_completo,
                user.rol,
                self.tr("Activo") if user.activo else self.tr("Desactivado"),
                format_datetime(user.ultimo_acceso) if user.ultimo_acceso else self.tr("Nunca"),
            )
            for column, value in enumerate(cells):
                self._table.setItem(row, column, QTableWidgetItem(value))
        self._update_buttons()

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._user_ids):
            return None
        return self._user_ids[row]

    def _selected_user(self, session: Session) -> User | None:
        user_id = self._selected_id()
        if user_id is None:
            return None
        return session.get(User, user_id)

    def _update_buttons(self) -> None:
        user_id = self._selected_id()
        self._edit_button.setEnabled(user_id is not None)
        self._password_button.setEnabled(user_id is not None)
        self._active_button.setEnabled(user_id is not None)
        if user_id is None:
            self._active_button.setText(self.tr("Desactivar"))
            return
        with self._session_factory() as session:
            user = session.get(User, user_id)
            active = bool(user and user.activo)
        self._active_button.setText(self.tr("Desactivar") if active else self.tr("Activar"))

    def _new_user(self) -> None:
        if UserFormDialog(self._session_factory, parent=self).exec():
            self.refresh()

    def _edit_selected(self) -> None:
        user_id = self._selected_id()
        if user_id is None:
            return
        if UserFormDialog(self._session_factory, user_id, parent=self).exec():
            self.refresh()

    def _change_password(self) -> None:
        user_id = self._selected_id()
        if user_id is None:
            return
        dialog = SetPasswordDialog(self._session_factory, user_id, parent=self)
        if dialog.exec():
            self.refresh()

    def _toggle_active(self) -> None:
        user_id = self._selected_id()
        if user_id is None:
            return
        if user_id == self._current_user.id:
            QMessageBox.information(
                self,
                self.windowTitle(),
                self.tr("No puede desactivar la cuenta con la que está trabajando."),
            )
            return
        try:
            with self._session_factory() as session:
                user = session.get(User, user_id)
                if user is None:
                    return
                set_active(session, user, not user.activo)
                session.commit()
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        except SQLAlchemyError:
            QMessageBox.critical(
                self, self.windowTitle(), self.tr("No se pudo cambiar el estado. Intente de nuevo.")
            )
            return
        self.refresh()


class SetPasswordDialog(QDialog):
    """El administrador pone una contraseña nueva a otra cuenta, sin pedir la anterior."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        user_id: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._user_id = user_id
        self.setWindowTitle(self.tr("Cambiar contraseña"))
        self.setMinimumWidth(420)

        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._repeat = QLineEdit()
        self._repeat.setEchoMode(QLineEdit.EchoMode.Password)

        form = QFormLayout()
        form.addRow(self.tr("Contraseña nueva"), self._password)
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

        self._password.setFocus(Qt.FocusReason.OtherFocusReason)

    def _save(self) -> None:
        if self._password.text() != self._repeat.text():
            self._message.setText(self.tr("Las dos contraseñas no coinciden."))
            return
        try:
            with self._session_factory() as session:
                user = session.get(User, self._user_id)
                if user is None:
                    self._message.setText(self.tr("El usuario ya no existe."))
                    return
                set_password(session, user, self._password.text())
                session.commit()
        except ValueError as exc:
            self._message.setText(str(exc))
            return
        except SQLAlchemyError:
            self._message.setText(self.tr("No se pudo cambiar la contraseña. Intente de nuevo."))
            return
        self.accept()
