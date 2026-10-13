"""Pruebas de UI de la pestaña de fotografías (§7.4)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication, QImage
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from pytestqt.qtbot import QtBot
from sqlalchemy.orm import Session, sessionmaker

import luciotech.ui.dialogs.photographs_tab as photographs_tab
from luciotech.database.enums import PhotoType
from luciotech.database.models import Photograph, ServiceOrder
from luciotech.services.customer_service import CustomerData
from luciotech.services.equipment_service import EquipmentData
from luciotech.services.photo_service import import_photo, photos_for_order
from luciotech.services.reception_service import ReceptionData, register_reception
from luciotech.ui.dialogs.order_detail_dialog import OrderDetailDialog
from luciotech.ui.dialogs.photographs_tab import PhotographsTab


@pytest.fixture
def order_id(session_factory: sessionmaker[Session]) -> int:
    with session_factory() as session:
        order = register_reception(
            session,
            ReceptionData(
                equipment=EquipmentData(cliente_id=None, tipo_equipo="Laptop"),
                new_customer=CustomerData(nombre_completo="Ana Torres", telefono_principal="0991234567"),
                fecha_ingreso=datetime(2026, 3, 10, 9, 0),
            ),
        )
        session.commit()
        return order.id


def _make_png(path: Path) -> str:
    image = QImage(40, 20, QImage.Format.Format_ARGB32)
    image.fill(0x8844AAFF)
    assert image.save(str(path), "PNG")
    return str(path)


def _imported_count(session_factory: sessionmaker[Session], order_id: int) -> int:
    with session_factory() as session:
        return len(photos_for_order(session, order_id))


def test_import_button_adds_photo_to_the_list(
    qtbot: QtBot,
    session_factory: sessionmaker[Session],
    order_id: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    png = _make_png(tmp_path / "foto.png")
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *a, **k: ([png], ""))
    tab = PhotographsTab(session_factory)
    qtbot.addWidget(tab)
    tab.set_order(order_id)
    assert tab.photo_count() == 0
    tab._import_dialog()
    assert tab.photo_count() == 1
    assert _imported_count(session_factory, order_id) == 1


def test_drag_and_drop_paths_are_imported(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int, tmp_path: Path
) -> None:
    first = _make_png(tmp_path / "a.png")
    second = _make_png(tmp_path / "b.png")
    tab = PhotographsTab(session_factory)
    qtbot.addWidget(tab)
    tab.set_order(order_id)
    tab._import_paths([first, second])
    assert tab.photo_count() == 2


def test_invalid_import_reports_and_imports_nothing(
    qtbot: QtBot,
    session_factory: sessionmaker[Session],
    order_id: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = tmp_path / "nota.txt"
    text.write_text("hola")
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    tab = PhotographsTab(session_factory)
    qtbot.addWidget(tab)
    tab.set_order(order_id)
    tab._import_paths([str(text)])
    assert tab.photo_count() == 0
    assert _imported_count(session_factory, order_id) == 0


def test_remove_button_deletes_selected_photo(
    qtbot: QtBot,
    session_factory: sessionmaker[Session],
    order_id: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    png = _make_png(tmp_path / "foto.png")
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        import_photo(session, order, png, base_dir=tmp_path / "att")
        session.commit()
    tab = PhotographsTab(session_factory)
    qtbot.addWidget(tab)
    tab.set_order(order_id)
    assert tab.photo_count() == 1
    tab._list.setCurrentRow(0)
    tab._remove_photo()
    assert tab.photo_count() == 0
    assert _imported_count(session_factory, order_id) == 0


def test_edit_dialog_saves_description_and_type(
    qtbot: QtBot,
    session_factory: sessionmaker[Session],
    order_id: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    png = _make_png(tmp_path / "foto.png")
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        photo = import_photo(session, order, png, base_dir=tmp_path / "att")
        session.commit()
        photo_id = photo.id

    class FakeEditDialog:
        def __init__(self, descripcion: str, tipo: str, parent=None) -> None:
            pass

        def exec(self) -> bool:
            return True

        def descripcion(self) -> str:
            return "Vista del teclado"

        def tipo(self) -> str:
            return PhotoType.ACCESORIOS.value

    monkeypatch.setattr(photographs_tab, "PhotoEditDialog", FakeEditDialog)
    tab = PhotographsTab(session_factory)
    qtbot.addWidget(tab)
    tab.set_order(order_id)
    tab._list.setCurrentRow(0)
    tab._edit_photo()
    with session_factory() as session:
        saved = session.get(Photograph, photo_id)
        assert saved.descripcion == "Vista del teclado"
        assert saved.tipo_fotografia == PhotoType.ACCESORIOS.value


def test_move_buttons_reorder_the_list(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int, tmp_path: Path
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        import_photo(session, order, _make_png(tmp_path / "uno.png"), base_dir=tmp_path / "att")
        import_photo(session, order, _make_png(tmp_path / "dos.png"), base_dir=tmp_path / "att")
        session.commit()
    tab = PhotographsTab(session_factory)
    qtbot.addWidget(tab)
    tab.set_order(order_id)
    assert [tab._list.item(i).text() for i in range(2)] == ["uno.png", "dos.png"]
    tab._list.setCurrentRow(1)
    tab._move(-1)
    assert [tab._list.item(i).text() for i in range(2)] == ["dos.png", "uno.png"]


def test_paste_button_imports_clipboard_image(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    image = QImage(30, 10, QImage.Format.Format_ARGB32)
    image.fill(0xFF3366AA)
    QGuiApplication.clipboard().setImage(image)
    tab = PhotographsTab(session_factory)
    qtbot.addWidget(tab)
    tab.set_order(order_id)
    assert not tab._view_button.isEnabled()
    assert tab._paste_button.isEnabled()
    tab._paste_from_clipboard()
    assert tab.photo_count() == 1
    assert _imported_count(session_factory, order_id) == 1


def test_ctrl_v_shortcut_is_bound_to_paste(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    """QtTest no activa atajos con teclas sintéticas, así que se comprueba la configuración
    del atajo y que su señal ejecuta el pegado."""
    from PyQt6.QtGui import QKeySequence, QShortcut

    tab = PhotographsTab(session_factory)
    qtbot.addWidget(tab)
    tab.set_order(order_id)
    shortcuts = [s for s in tab.findChildren(QShortcut) if s.key() == QKeySequence("Ctrl+V")]
    assert len(shortcuts) == 1
    assert shortcuts[0].parent() is tab
    assert shortcuts[0].context() == Qt.ShortcutContext.WidgetWithChildrenShortcut

    image = QImage(30, 10, QImage.Format.Format_ARGB32)
    image.fill(0xFF3366AA)
    QGuiApplication.clipboard().setImage(image)
    shortcuts[0].activated.emit()
    assert tab.photo_count() == 1
    assert _imported_count(session_factory, order_id) == 1


def test_order_detail_has_photographs_tab(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    dialog = OrderDetailDialog(session_factory, order_id, "Ing. Lucio")
    qtbot.addWidget(dialog)
    assert dialog._photos.photo_count() == 0
    assert dialog._photos._order_id == order_id


def test_actions_follow_selection(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int, tmp_path: Path
) -> None:
    tab = PhotographsTab(session_factory)
    qtbot.addWidget(tab)
    tab.set_order(order_id)
    assert not tab._view_button.isEnabled()
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        import_photo(session, order, _make_png(tmp_path / "foto.png"), base_dir=tmp_path / "att")
        session.commit()
    tab.refresh()
    assert not tab._view_button.isEnabled()
    tab._list.setCurrentRow(0)
    assert tab._view_button.isEnabled()
