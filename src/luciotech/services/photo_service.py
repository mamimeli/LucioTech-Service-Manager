"""Fotografías de una orden (§7.4): importación, copia con UUID, rotación y reordenado.

Las imágenes se copian a `attachments/<número de orden>/` con un nombre UUID, y al leerlas
se aplica la orientación EXIF para que el archivo guardado ya no dependa de metadatos.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication, QImage, QImageReader, QTransform
from sqlalchemy import select
from sqlalchemy.orm import Session

from luciotech.database.enums import PhotoType
from luciotech.database.models import Photograph, ServiceOrder
from luciotech.utils.paths import attachments_dir

ALLOWED_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp"})
MAX_FILE_BYTES = 20 * 1024 * 1024
THUMBNAIL_SIZE = 160
_SAVE_FORMATS = {".jpg": "JPEG", ".jpeg": "JPEG"}


class PhotoImportError(ValueError):
    """Error de importación; `reason` lleva el mensaje para la interfaz."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def import_photo(
    session: Session,
    order: ServiceOrder,
    source: str | Path,
    *,
    tipo: PhotoType | str = PhotoType.ESTADO_AL_RECIBIR,
    descripcion: str | None = None,
    base_dir: Path | None = None,
) -> Photograph:
    """Copia la imagen a `attachments/<orden>/` con nombre UUID y crea el registro."""
    path = Path(source)
    suffix = path.suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise PhotoImportError(f"Formato no permitido: {path.suffix or 'sin extensión'}")
    if not path.is_file():
        raise PhotoImportError("El archivo no existe.")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise PhotoImportError("La imagen supera el tamaño máximo de 20 MB.")
    image = load_oriented(path)
    if image is None:
        raise PhotoImportError("No se pudo leer la imagen.")

    dest_dir = (base_dir or attachments_dir()) / order.numero_orden
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid4().hex}{suffix}"
    if not image.save(str(dest), _SAVE_FORMATS.get(suffix, suffix.lstrip(".").upper())):
        dest.unlink(missing_ok=True)
        raise PhotoImportError("No se pudo guardar la imagen.")

    photo = Photograph(
        order=order,
        ruta_archivo=str(dest),
        nombre_archivo=path.name,
        descripcion=(descripcion or "").strip() or None,
        tipo_fotografia=PhotoType(tipo).value,
        fecha_captura=datetime.fromtimestamp(path.stat().st_mtime),
        orden_visualizacion=next_position(session, order),
    )
    session.add(photo)
    session.flush()
    return photo


def import_clipboard_image(
    session: Session,
    order: ServiceOrder,
    *,
    tipo: PhotoType | str = PhotoType.ESTADO_AL_RECIBIR,
    descripcion: str | None = None,
    base_dir: Path | None = None,
) -> Photograph:
    """Guarda la imagen del portapapeles como PNG en la carpeta de la orden."""
    image = QGuiApplication.clipboard().image()
    if image.isNull():
        raise PhotoImportError("El portapapeles no contiene una imagen.")
    dest_dir = (base_dir or attachments_dir()) / order.numero_orden
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid4().hex}.png"
    if not image.save(str(dest), "PNG"):
        raise PhotoImportError("No se pudo guardar la imagen del portapapeles.")
    photo = Photograph(
        order=order,
        ruta_archivo=str(dest),
        nombre_archivo=f"portapapeles-{dest.stem[:8]}.png",
        descripcion=(descripcion or "").strip() or None,
        tipo_fotografia=PhotoType(tipo).value,
        fecha_captura=None,
        orden_visualizacion=next_position(session, order),
    )
    session.add(photo)
    session.flush()
    return photo


def photos_for_order(session: Session, order_id: int) -> list[Photograph]:
    statement = (
        select(Photograph)
        .where(Photograph.orden_id == order_id)
        .order_by(Photograph.orden_visualizacion, Photograph.id)
    )
    return list(session.scalars(statement))


def next_position(session: Session, order: ServiceOrder) -> int:
    positions = session.scalars(
        select(Photograph.orden_visualizacion).where(Photograph.orden_id == order.id)
    ).all()
    return max(positions) + 1 if positions else 0


def remove_photo(session: Session, photo: Photograph) -> None:
    """Elimina el registro y el archivo del disco."""
    path = Path(photo.ruta_archivo)
    session.delete(photo)
    session.flush()
    if path.is_file():
        path.unlink()


def rotate_photo(photo: Photograph, degrees: int) -> None:
    """Rota la imagen guardada en múltiplos de 90 grados."""
    if degrees % 90 != 0:
        raise PhotoImportError("La rotación debe ser un múltiplo de 90 grados.")
    path = Path(photo.ruta_archivo)
    image = load_oriented(path)
    if image is None:
        raise PhotoImportError("No se pudo leer la imagen guardada.")
    suffix = path.suffix.lower()
    rotated = image.transformed(QTransform().rotate(degrees))
    if not rotated.save(str(path), _SAVE_FORMATS.get(suffix, suffix.lstrip(".").upper())):
        raise PhotoImportError("No se pudo guardar la imagen rotada.")


def move_photo(session: Session, photo: Photograph, offset: int) -> None:
    """Intercambia la posición de la foto con la anterior (-1) o la siguiente (1)."""
    siblings = photos_for_order(session, photo.orden_id)
    index = siblings.index(photo)
    target = index + offset
    if not 0 <= target < len(siblings):
        return
    other = siblings[target]
    photo.orden_visualizacion, other.orden_visualizacion = (
        other.orden_visualizacion,
        photo.orden_visualizacion,
    )
    session.flush()


def set_photo_details(
    session: Session, photo: Photograph, descripcion: str | None, tipo: PhotoType | str
) -> None:
    photo.descripcion = (descripcion or "").strip() or None
    photo.tipo_fotografia = PhotoType(tipo).value
    session.flush()


def photo_thumbnail(photo: Photograph, size: int = THUMBNAIL_SIZE) -> QImage:
    """Miniatura de la foto guardada; imagen nula si el archivo no se puede leer."""
    image = load_oriented(Path(photo.ruta_archivo))
    if image is None:
        return QImage()
    return image.scaled(
        size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
    )


def load_oriented(path: Path) -> QImage | None:
    """Lee la imagen aplicando la orientación EXIF, si la tuviera."""
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    image = reader.read()
    return None if image.isNull() else image
