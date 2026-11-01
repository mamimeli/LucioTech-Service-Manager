"""Ventana principal con pestañas Inicio, Órdenes, Clientes, Equipos y Papelera (§6, §9, §17 y §18).

La ventana sabe quién tiene la sesión abierta (`CurrentUser`): ese nombre es el que va a la
barra de estado, al historial de cada orden y al pie de los documentos que se imprimen.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtWidgets import QLabel, QMainWindow, QTabWidget, QWidget
from sqlalchemy.orm import Session, sessionmaker

from luciotech.config import APP_CONFIG
from luciotech.services.user_service import DEFAULT_CURRENT_USER, CurrentUser
from luciotech.ui.dialogs.login_dialog import ChangePasswordDialog
from luciotech.ui.dialogs.users_dialog import UsersDialog
from luciotech.ui.pages.customers_page import CustomersPage
from luciotech.ui.pages.equipment_page import EquipmentPage
from luciotech.ui.pages.home_page import HomePage
from luciotech.ui.pages.orders_page import OrdersPage
from luciotech.ui.pages.trash_page import TrashPage

MIN_WIDTH = 800
MIN_HEIGHT = 560


class MainWindow(QMainWindow):
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        user: CurrentUser | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._user = user or DEFAULT_CURRENT_USER
        self.logout_requested = False
        self.setWindowTitle(APP_CONFIG.app_name)
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

        self._home = HomePage(session_factory)
        self._customers = CustomersPage(session_factory)
        self._equipment = EquipmentPage(session_factory)
        self._orders = OrdersPage(session_factory, usuario=self._user.display_name)
        self._trash = TrashPage(session_factory, usuario=self._user.display_name)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._home, self.tr("Inicio"))
        self._tabs.addTab(self._orders, self.tr("Órdenes"))
        self._tabs.addTab(self._customers, self.tr("Clientes"))
        self._tabs.addTab(self._equipment, self.tr("Equipos"))
        self._tabs.addTab(self._trash, self.tr("Papelera"))
        self.setCentralWidget(self._tabs)

        self._customers.data_changed.connect(self.refresh_all)
        self._equipment.data_changed.connect(self.refresh_all)
        self._orders.data_changed.connect(self.refresh_all)
        self._trash.data_changed.connect(self.refresh_all)
        self._tabs.currentChanged.connect(lambda _index: self.refresh_all())

        self._build_menu()
        self._show_session()
        refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        refresh_shortcut.activated.connect(self.refresh_all)

    @property
    def user(self) -> CurrentUser:
        return self._user

    @property
    def home_page(self) -> HomePage:
        return self._home

    @property
    def customers_page(self) -> CustomersPage:
        return self._customers

    @property
    def equipment_page(self) -> EquipmentPage:
        return self._equipment

    @property
    def orders_page(self) -> OrdersPage:
        return self._orders

    @property
    def trash_page(self) -> TrashPage:
        return self._trash

    def refresh_all(self) -> None:
        self._home.refresh()
        self._orders.refresh()
        self._customers.refresh()
        self._equipment.refresh()
        self._trash.refresh()

    def _show_session(self) -> None:
        """Quién está dentro, a la vista y sin ocupar sitio en la barra de pestañas."""
        label = QLabel(
            self.tr("Sesión: %1 · %2")
            .replace("%1", self._user.display_name)
            .replace("%2", self._user.role)
        )
        label.setToolTip(
            self.tr(
                "Este nombre aparece en el historial de las órdenes y en el pie de los "
                "documentos que imprima."
            )
        )
        self.statusBar().addPermanentWidget(label)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu(self.tr("&Archivo"))
        if self._user.id is not None:
            password_action = QAction(self.tr("Cambiar &mi contraseña…"), self)
            password_action.triggered.connect(self._change_password)
            file_menu.addAction(password_action)
        if self._user.is_admin:
            users_action = QAction(self.tr("&Usuarios…"), self)
            users_action.setShortcut(QKeySequence("Ctrl+U"))
            users_action.triggered.connect(self._open_users)
            file_menu.addAction(users_action)
        if self._user.id is not None:
            logout_action = QAction(self.tr("&Cerrar sesión"), self)
            logout_action.triggered.connect(self._logout)
            file_menu.addAction(logout_action)
        file_menu.addSeparator()
        quit_action = QAction(self.tr("&Salir"), self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _open_users(self) -> None:
        UsersDialog(self._session_factory, self._user, parent=self).exec()
        self.refresh_all()

    def _change_password(self) -> None:
        if self._user.id is None:
            return
        ChangePasswordDialog(self._session_factory, self._user.id, parent=self).exec()

    def _logout(self) -> None:
        self.logout_requested = True
        self.close()
