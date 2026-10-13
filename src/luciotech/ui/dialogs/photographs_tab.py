"""Pestaña de fotografías de una orden (§7.4): importar, ver, rotar, describir y reordenar."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QImage, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from luciotech.database.enums import PhotoType
from luciotech.database.models import Photograph, ServiceOrder
from luciotech.services.photo_service import (
    PhotoImportError,
    import_clipboard_image,
    import_photo,
    load_oriented,
    move_photo,
    photo_thumbnail,
    photos_for_order,
    remove_photo,
    rotate_photo,
    set_photo_details,
)

THUMBNAIL = 160
IMAGE_FILTER = "Imágenes (*.jpg *.jpeg *.png *.webp *.bmp)"


class _DropList(QListWidget):
    """Lista que acepta imágenes arrastradas desde el gestor de archivos."""

    files_dropped = pyqtSignal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        files = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if files:
            event.acceptProposedAction()
            self.files_dropped.emit(files)


class PhotoViewerDialog(QDialog):
    """Muestra una foto escalada al tamaño de la ventana."""

    def __init__(self, image: QImage, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(900, 650)
        self._image = image
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll)
        layout.addWidget(buttons)
        self._render()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._render()

    def _render(self) -> None:
        if self._image.isNull():
            return
        pixmap = QPixmap.fromImage(self._image).scaled(
            max(1, self.width() - 40),
            max(1, self.height() - 80),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._label.setPixmap(pixmap)


class PhotoEditDialog(QDialog):
    """Edita la descripción y el tipo de una fotografía."""

    def __init__(self, descripcion: str, tipo: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Editar fotografía"))
        self._description = QLineEdit(descripcion)
        self._type = QComboBox()
        for photo_type in PhotoType:
            self._type.addItem(photo_type.value, photo_type.value)
        index = self._type.findData(tipo)
        if index >= 0:
            self._type.setCurrentIndex(index)
        form = QFormLayout()
        form.addRow(self.tr("Descripción"), self._description)
        form.addRow(self.tr("Tipo"), self._type)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def descripcion(self) -> str:
        return self._description.text()

    def tipo(self) -> str:
        return self._type.currentData()


class PhotographsTab(QWidget):
    """Galería de fotos de una orden: miniaturas en cuadrícula con acciones."""

    def __init__(
        self, session_factory: sessionmaker[Session], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._order_id: int | None = None

        self._list = _DropList()
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setIconSize(QSize(THUMBNAIL, THUMBNAIL))
        self._list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list.itemDoubleClicked.connect(lambda _item: self.view_photo())
        self._list.itemSelectionChanged.connect(self._sync_actions)
        self._list.files_dropped.connect(self._import_paths)

        self._import_button = QPushButton(self.tr("Importar…"))
        self._import_button.clicked.connect(self._import_dialog)
        self._paste_button = QPushButton(self.tr("Pegar"))
        self._paste_button.clicked.connect(self._paste_from_clipboard)
        paste_shortcut = QShortcut(QKeySequence("Ctrl+V"), self)
        paste_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        paste_shortcut.activated.connect(self._paste_from_clipboard)
        self._view_button = QPushButton(self.tr("Ver"))
        self._view_button.clicked.connect(self.view_photo)
        self._rotate_left = QPushButton(self.tr("Rotar izquierda"))
        self._rotate_left.clicked.connect(lambda: self._rotate(-90))
        self._rotate_right = QPushButton(self.tr("Rotar derecha"))
        self._rotate_right.clicked.connect(lambda: self._rotate(90))
        self._edit_button = QPushButton(self.tr("Editar…"))
        self._edit_button.clicked.connect(self._edit_photo)
        self._remove_button = QPushButton(self.tr("Quitar"))
        self._remove_button.clicked.connect(self._remove_photo)
        self._up_button = QPushButton(self.tr("Subir"))
        self._up_button.clicked.connect(lambda: self._move(-1))
        self._down_button = QPushButton(self.tr("Bajar"))
        self._down_button.clicked.connect(lambda: self._move(1))

        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)
        for button in (
            self._import_button,
            self._paste_button,
            self._view_button,
            self._rotate_left,
            self._rotate_right,
            self._edit_button,
            self._remove_button,
            self._up_button,
            self._down_button,
        ):
            toolbar.addWidget(button)
        toolbar.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addLayout(toolbar)
        layout.addWidget(self._list, 1)
        self._sync_actions()

    def set_order(self, order_id: int) -> None:
        self._order_id = order_id
        self.refresh()

    def refresh(self) -> None:
        self._list.clear()
        if self._order_id is not None:
            with self._session_factory() as session:
                photos = photos_for_order(session, self._order_id)
                entries = [
                    (photo.id, photo.nombre_archivo, photo.descripcion, photo.tipo_fotografia,
                     photo_thumbnail(photo))
                    for photo in photos
                ]
            for photo_id, name, description, tipo, thumb in entries:
                item = QListWidgetItem(name)
                if not thumb.isNull():
                    item.setIcon(QIcon(QPixmap.fromImage(thumb)))
                item.setToolTip(description or tipo)
                item.setData(Qt.ItemDataRole.UserRole, photo_id)
                self._list.addItem(item)
        self._sync_actions()

    def photo_count(self) -> int:
        return self._list.count()

    def view_photo(self) -> None:
        photo_id = self._selected_id()
        if photo_id is None:
            return
        with self._session_factory() as session:
            photo = session.get(Photograph, photo_id)
            if photo is None:
                return
            image = load_oriented(Path(photo.ruta_archivo))
            title = photo.nombre_archivo
        if image is None:
            QMessageBox.warning(self, self.tr("Ver fotografía"), self.tr("No se pudo cargar la imagen."))
            return
        PhotoViewerDialog(image, title, self).exec()

    def _import_dialog(self) -> None:
        files, _filter = QFileDialog.getOpenFileNames(
            self, self.tr("Importar fotografías"), "", IMAGE_FILTER
        )
        if files:
            self._import_paths(files)

    def _import_paths(self, files: list) -> None:
        if self._order_id is None or not files:
            return
        errors: list[str] = []
        with self._session_factory() as session:
            order = session.get(ServiceOrder, self._order_id)
            if order is None:
                return
            for file_path in files:
                try:
                    import_photo(session, order, file_path)
                except PhotoImportError as exc:
                    errors.append(f"{Path(file_path).name}: {exc.reason}")
            session.commit()
        if errors:
            QMessageBox.warning(self, self.tr("Importar fotografías"), "\n".join(errors))
        self.refresh()

    def _paste_from_clipboard(self) -> None:
        if self._order_id is None:
            return
        try:
            with self._session_factory() as session:
                order = session.get(ServiceOrder, self._order_id)
                if order is None:
                    return
                import_clipboard_image(session, order)
                session.commit()
        except PhotoImportError as exc:
            QMessageBox.warning(self, self.tr("Pegar fotografía"), exc.reason)
        self.refresh()

    def _rotate(self, degrees: int) -> None:
        photo_id = self._selected_id()
        if photo_id is None:
            return
        try:
            with self._session_factory() as session:
                photo = session.get(Photograph, photo_id)
                if photo is not None:
                    rotate_photo(photo, degrees)
                session.commit()
        except PhotoImportError as exc:
            QMessageBox.warning(self, self.tr("Rotar fotografía"), exc.reason)
        self.refresh()

    def _edit_photo(self) -> None:
        photo_id = self._selected_id()
        if photo_id is None:
            return
        with self._session_factory() as session:
            photo = session.get(Photograph, photo_id)
            if photo is None:
                return
            descripcion = photo.descripcion or ""
            tipo = photo.tipo_fotografia
        dialog = PhotoEditDialog(descripcion, tipo, self)
        if not dialog.exec():
            return
        with self._session_factory() as session:
            photo = session.get(Photograph, photo_id)
            if photo is None:
                return
            set_photo_details(session, photo, dialog.descripcion(), dialog.tipo())
            session.commit()
        self.refresh()

    def _remove_photo(self) -> None:
        photo_id = self._selected_id()
        if photo_id is None:
            return
        answer = QMessageBox.question(
            self,
            self.tr("Quitar fotografía"),
            self.tr("¿Quitar la fotografía seleccionada? El archivo también se borrará."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        with self._session_factory() as session:
            photo = session.get(Photograph, photo_id)
            if photo is not None:
                remove_photo(session, photo)
            session.commit()
        self.refresh()

    def _move(self, offset: int) -> None:
        photo_id = self._selected_id()
        if photo_id is None:
            return
        with self._session_factory() as session:
            photo = session.get(Photograph, photo_id)
            if photo is not None:
                move_photo(session, photo, offset)
            session.commit()
        self.refresh()

    def _selected_id(self) -> int | None:
        item = self._list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _sync_actions(self) -> None:
        has_selection = self._list.currentItem() is not None
        for button in (
            self._view_button,
            self._rotate_left,
            self._rotate_right,
            self._edit_button,
            self._remove_button,
            self._up_button,
            self._down_button,
        ):
            button.setEnabled(has_selection)
