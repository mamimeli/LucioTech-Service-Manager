"""Pruebas del segundo bloque de la barra del editor: justificar, cortar, tabla, imagen, buscar y reemplazar, PDF."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QTextCursor
from pytestqt.qtbot import QtBot

from luciotech.ui.dialogs.find_replace_dialog import FindReplaceDialog
from luciotech.ui.widgets.rich_text_editor import RichTextEditor


@pytest.fixture
def editor(qtbot: QtBot) -> RichTextEditor:
    widget = RichTextEditor()
    qtbot.addWidget(widget)
    return widget


def _make_png(path: Path) -> str:
    image = QImage(8, 8, QImage.Format.Format_ARGB32)
    image.fill(0)
    saved = str(path)
    assert image.save(saved, "PNG")
    return saved


def test_justify_sets_block_alignment(editor: RichTextEditor) -> None:
    editor.set_html("<p>texto largo</p>")
    editor.action("justify").trigger()
    assert editor.editor.textCursor().blockFormat().alignment() == Qt.AlignmentFlag.AlignJustify


def test_cut_removes_selection(editor: RichTextEditor) -> None:
    editor.set_html("<p>borrame</p>")
    cursor = editor.editor.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    editor.editor.setTextCursor(cursor)
    editor.action("cut").trigger()
    assert editor.editor.toPlainText().strip() == ""


def test_insert_table_creates_table(editor: RichTextEditor) -> None:
    editor.set_html("<p>antes</p>")
    editor.insert_table(2, 3)
    assert editor.editor.textCursor().currentTable() is not None
    assert "<table" in editor.html()


def test_insert_table_rejects_invalid_size(editor: RichTextEditor) -> None:
    editor.set_html("<p>igual</p>")
    editor.insert_table(0, 3)
    editor.insert_table(2, -1)
    assert "<table" not in editor.html()


def test_insert_image_references_the_file(editor: RichTextEditor, tmp_path: Path) -> None:
    png = _make_png(tmp_path / "img.png")
    assert editor.insert_image(png) is True
    assert "<img" in editor.html()
    assert "img.png" in editor.html()


def test_insert_image_rejects_missing_file(editor: RichTextEditor) -> None:
    assert editor.insert_image("/no/existe/x.png") is False
    assert "<img" not in editor.html()


def test_find_next_selects_occurrence(editor: RichTextEditor) -> None:
    editor.set_html("<p>alpha beta gamma</p>")
    assert editor.find_next("beta") is True
    assert editor.editor.textCursor().selectedText() == "beta"
    assert editor.find_next("delta") is False


def test_find_next_is_case_insensitive_by_default(editor: RichTextEditor) -> None:
    editor.set_html("<p>RAM dañada</p>")
    assert editor.find_next("ram") is True
    assert editor.find_next("ram", case_sensitive=True) is False


def test_replace_all_replaces_every_occurrence(editor: RichTextEditor) -> None:
    editor.set_html("<p>disco, disco, disco</p>")
    count = editor.replace_all("disco", "SSD")
    assert count == 3
    assert editor.editor.toPlainText() == "SSD, SSD, SSD"


def test_replace_all_with_replacement_containing_needle_terminates(editor: RichTextEditor) -> None:
    editor.set_html("<p>aa</p>")
    count = editor.replace_all("a", "aa")
    assert count == 2
    assert editor.editor.toPlainText() == "aaaa"


def test_replace_current_replaces_only_selection(editor: RichTextEditor) -> None:
    editor.set_html("<p>uno dos</p>")
    editor.find_next("uno")
    assert editor.replace_current("uno", "1") is True
    assert editor.editor.toPlainText() == "1 dos"
    assert editor.replace_current("uno", "1") is False


def test_render_to_pdf_creates_a_pdf(editor: RichTextEditor, tmp_path: Path) -> None:
    editor.set_html("<p>Informe de prueba</p>")
    pdf = str(tmp_path / "informe.pdf")
    assert editor.render_to_pdf(pdf) is True
    assert Path(pdf).read_bytes()[:5] == b"%PDF-"


def test_find_replace_dialog_replaces_all(editor: RichTextEditor) -> None:
    editor.set_html("<p>ram rota, ram nueva</p>")
    dialog = FindReplaceDialog(editor)
    dialog._find_field.setText("ram")
    dialog._replace_field.setText("memoria")
    dialog._on_replace_all()
    assert editor.editor.toPlainText() == "memoria rota, memoria nueva"
    assert "2" in dialog._status.text()


def test_find_replace_dialog_reports_no_match(editor: RichTextEditor) -> None:
    editor.set_html("<p>texto</p>")
    dialog = FindReplaceDialog(editor)
    dialog._find_field.setText("inexistente")
    dialog._on_find_next()
    assert "Sin más coincidencias" in dialog._status.text()
