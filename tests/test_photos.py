"""Pruebas del servicio de fotografías (§7.4): importación, UUID, EXIF, rotación y reordenado."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from PyQt6.QtGui import QGuiApplication, QImage
from sqlalchemy.orm import Session, sessionmaker

from luciotech.database.enums import PhotoType
from luciotech.database.models import Photograph, ServiceOrder
from luciotech.services.customer_service import CustomerData
from luciotech.services.equipment_service import EquipmentData
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
from luciotech.services.reception_service import ReceptionData, register_reception


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


def _make_image(path: Path, width: int = 40, height: int = 20) -> Path:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(0x8844AAFF)
    suffix = path.suffix.lstrip(".").upper()
    assert image.save(str(path), "JPEG" if suffix in {"JPG", "JPEG"} else suffix)
    return path


def _make_exif_rotated_jpeg(path: Path) -> Path:
    from PIL import Image

    image = Image.new("RGB", (40, 20), "red")
    exif = Image.Exif()
    exif[0x0112] = 6
    image.save(str(path), "JPEG", exif=exif)
    return path


def test_import_copies_with_uuid_name_and_creates_record(
    session_factory: sessionmaker[Session], order_id: int, tmp_path: Path
) -> None:
    source = _make_image(tmp_path / "foto.jpg")
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        photo = import_photo(
            session, order, source, tipo=PhotoType.DANO_FISICO, base_dir=tmp_path / "att"
        )
        session.commit()
        stored_id = photo.id
        ruta = photo.ruta_archivo

    stored = Path(ruta)
    assert stored.parent == tmp_path / "att" / order.numero_orden
    assert stored.is_file()
    assert stored.name != "foto.jpg"
    assert stored.suffix == ".jpg"
    with session_factory() as session:
        saved = session.get(Photograph, stored_id)
        assert saved.nombre_archivo == "foto.jpg"
        assert saved.tipo_fotografia == PhotoType.DANO_FISICO.value
        assert saved.descripcion is None
        assert saved.orden_visualizacion == 0
        assert saved.fecha_captura is not None


def test_importing_twice_creates_two_files_and_positions(
    session_factory: sessionmaker[Session], order_id: int, tmp_path: Path
) -> None:
    first = _make_image(tmp_path / "a.png")
    second = _make_image(tmp_path / "b.png")
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        one = import_photo(session, order, first, base_dir=tmp_path / "att")
        two = import_photo(session, order, second, base_dir=tmp_path / "att")
        session.commit()
        assert one.ruta_archivo != two.ruta_archivo
        assert Path(one.ruta_archivo).is_file()
        assert Path(two.ruta_archivo).is_file()
        assert [one.orden_visualizacion, two.orden_visualizacion] == [0, 1]


def test_import_rejects_disallowed_format(
    session_factory: sessionmaker[Session], order_id: int, tmp_path: Path
) -> None:
    text = tmp_path / "nota.txt"
    text.write_text("no soy una imagen")
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        with pytest.raises(PhotoImportError) as exc:
            import_photo(session, order, text, base_dir=tmp_path / "att")
        assert "Formato no permitido" in exc.value.reason


def test_import_rejects_missing_file(
    session_factory: sessionmaker[Session], order_id: int, tmp_path: Path
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        with pytest.raises(PhotoImportError):
            import_photo(session, order, tmp_path / "no_existe.png", base_dir=tmp_path / "att")


def test_import_corrects_exif_orientation(
    session_factory: sessionmaker[Session], order_id: int, tmp_path: Path
) -> None:
    source = _make_exif_rotated_jpeg(tmp_path / "girada.jpg")
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        photo = import_photo(session, order, source, base_dir=tmp_path / "att")
        session.commit()
        ruta = photo.ruta_archivo

    stored = load_oriented(Path(ruta))
    assert stored is not None
    assert stored.width() == 20
    assert stored.height() == 40


def test_remove_deletes_file_and_record(
    session_factory: sessionmaker[Session], order_id: int, tmp_path: Path
) -> None:
    source = _make_image(tmp_path / "fuente.png")
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        photo = import_photo(session, order, source, base_dir=tmp_path / "att")
        session.commit()
        stored_id = photo.id
        ruta = Path(photo.ruta_archivo)

    with session_factory() as session:
        remove_photo(session, session.get(Photograph, stored_id))
        session.commit()

    assert not ruta.is_file()
    with session_factory() as session:
        assert session.get(Photograph, stored_id) is None


def test_rotate_swaps_dimensions_on_disk(
    session_factory: sessionmaker[Session], order_id: int, tmp_path: Path
) -> None:
    source = _make_image(tmp_path / "pano.jpg", 40, 20)
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        photo = import_photo(session, order, source, base_dir=tmp_path / "att")
        session.commit()
        ruta = photo.ruta_archivo

    with session_factory() as session:
        rotate_photo(session.get(Photograph, photo.id), 90)

    rotated = load_oriented(Path(ruta))
    assert rotated is not None
    assert rotated.width() == 20
    assert rotated.height() == 40


def test_move_photo_swaps_positions(
    session_factory: sessionmaker[Session], order_id: int, tmp_path: Path
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        one = import_photo(session, order, _make_image(tmp_path / "1.png"), base_dir=tmp_path / "att")
        two = import_photo(session, order, _make_image(tmp_path / "2.png"), base_dir=tmp_path / "att")
        session.commit()
        second_id = two.id

        move_photo(session, session.get(Photograph, second_id), -1)
        session.commit()
        ordered = photos_for_order(session, order_id)
        assert [p.nombre_archivo for p in ordered] == ["2.png", "1.png"]


def test_move_photo_out_of_range_is_noop(
    session_factory: sessionmaker[Session], order_id: int, tmp_path: Path
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        one = import_photo(session, order, _make_image(tmp_path / "1.png"), base_dir=tmp_path / "att")
        session.commit()
        move_photo(session, one, -1)
        session.commit()
        assert photos_for_order(session, order_id)[0].id == one.id


def test_set_photo_details(
    session_factory: sessionmaker[Session], order_id: int, tmp_path: Path
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        photo = import_photo(session, order, _make_image(tmp_path / "1.png"), base_dir=tmp_path / "att")
        session.commit()
        set_photo_details(
            session, photo, "  Panorámica del daño  ", PhotoType.ACCESORIOS
        )
        session.commit()
        saved = session.get(Photograph, photo.id)
        assert saved.descripcion == "Panorámica del daño"
        assert saved.tipo_fotografia == PhotoType.ACCESORIOS.value


def test_clipboard_image_is_saved_as_png(
    session_factory: sessionmaker[Session], order_id: int, tmp_path: Path
) -> None:
    image = QImage(30, 10, QImage.Format.Format_ARGB32)
    image.fill(0xFF3366AA)
    QGuiApplication.clipboard().setImage(image)
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        photo = import_clipboard_image(session, order, base_dir=tmp_path / "att")
        session.commit()
    stored = Path(photo.ruta_archivo)
    assert stored.is_file()
    assert stored.suffix == ".png"
    assert "portapapeles" in photo.nombre_archivo


def test_clipboard_without_image_is_rejected(
    session_factory: sessionmaker[Session], order_id: int, tmp_path: Path
) -> None:
    QGuiApplication.clipboard().clear()
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        with pytest.raises(PhotoImportError) as exc:
            import_clipboard_image(session, order, base_dir=tmp_path / "att")
        assert "portapapeles" in exc.value.reason


def test_thumbnail_is_scaled_to_fit(
    session_factory: sessionmaker[Session], order_id: int, tmp_path: Path
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        photo = import_photo(
            session, order, _make_image(tmp_path / "1.png", 400, 200), base_dir=tmp_path / "att"
        )
        session.commit()
        thumb = photo_thumbnail(session.get(Photograph, photo.id))
    assert not thumb.isNull()
    assert thumb.width() <= 160 and thumb.height() <= 160
    assert max(thumb.width(), thumb.height()) == 160
