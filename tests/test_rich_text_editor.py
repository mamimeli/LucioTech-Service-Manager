"""Pruebas del editor de texto enriquecido (Fase 2, primer bloque)."""

from __future__ import annotations

import pytest
from PyQt6.QtGui import QTextCursor
from pytestqt.qtbot import QtBot

from luciotech.ui.widgets.rich_text_editor import RichTextEditor


@pytest.fixture
def editor(qtbot: QtBot) -> RichTextEditor:
    widget = RichTextEditor()
    qtbot.addWidget(widget)
    return widget


def _plain(html: str, editor: RichTextEditor) -> str:
    editor.set_html(html)
    return editor.editor.toPlainText()


def test_new_editor_is_empty(editor: RichTextEditor) -> None:
    assert editor.is_empty()


def test_html_round_trip_keeps_text_and_bold(editor: RichTextEditor) -> None:
    editor.set_html("<p><b>Pantalla rota</b> y sin carga</p>")
    saved = editor.html()
    other = RichTextEditor()
    other.set_html(saved)
    assert other.editor.toPlainText() == "Pantalla rota y sin carga"
    assert "font-weight:700" in saved
    assert other.html() == saved


def test_html_round_trip_keeps_italic_and_underline(editor: RichTextEditor) -> None:
    editor.set_html("<p><i>cursiva</i> y <u>subrayado</u></p>")
    other = RichTextEditor()
    other.set_html(editor.html())
    assert "font-style:italic" in other.html()
    assert "text-decoration: underline" in other.html()


def test_bold_applies_to_selection(editor: RichTextEditor) -> None:
    editor.set_html("<p>uno dos</p>")
    cursor = editor.editor.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    editor.editor.setTextCursor(cursor)
    editor.action("bold").setChecked(True)
    assert "font-weight" in editor.html()
    assert "600" in editor.html() or "700" in editor.html()


def test_bullet_list_is_created_and_removed(editor: RichTextEditor) -> None:
    editor.set_html("<p>uno</p><p>dos</p>")
    cursor = editor.editor.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    editor.editor.setTextCursor(cursor)

    editor._bullet_list()
    assert editor.editor.textCursor().currentList() is not None

    editor._bullet_list()
    assert editor.editor.textCursor().currentList() is None


def test_undo_and_redo_restore_text(editor: RichTextEditor) -> None:
    editor.editor.insertPlainText("primero")
    editor.editor.insertPlainText(" segundo")
    editor.action("undo").trigger()
    assert "segundo" not in editor.editor.toPlainText()
    editor.action("redo").trigger()
    assert "segundo" in editor.editor.toPlainText()


def test_alignment_is_saved_in_html(editor: RichTextEditor) -> None:
    editor.set_html("<p>centrado</p>")
    cursor = editor.editor.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    editor.editor.setTextCursor(cursor)
    from PyQt6.QtCore import Qt

    editor.editor.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    assert editor.editor.textCursor().blockFormat().alignment() == Qt.AlignmentFlag.AlignHCenter
    other = RichTextEditor()
    other.set_html(editor.html())
    assert other.editor.document().firstBlock().blockFormat().alignment() == Qt.AlignmentFlag.AlignHCenter


def test_toolbar_has_the_essential_actions(editor: RichTextEditor) -> None:
    for name in ("bold", "italic", "underline", "bullet", "numbered", "left", "center", "right", "undo", "redo"):
        assert editor.action(name) is not None


def test_formatting_buttons_have_icons_and_name_in_tooltip(editor: RichTextEditor) -> None:
    from luciotech.ui.widgets.rich_text_editor import ICON_FILES

    expected = {
        "bold": "Negrita",
        "italic": "Cursiva",
        "underline": "Subrayado",
        "bullet": "Lista con viñetas",
        "numbered": "Lista numerada",
        "left": "Alinear a la izquierda",
        "center": "Centrar",
        "right": "Alinear a la derecha",
    }
    assert set(ICON_FILES) == set(expected)
    for name, tooltip in expected.items():
        action = editor.action(name)
        assert not action.icon().isNull(), name
        assert action.toolTip() == tooltip


def test_html_from_user_text_is_not_interpreted_as_markup(editor: RichTextEditor) -> None:
    editor.set_html("<p>&lt;script&gt;x&lt;/script&gt;</p>")
    assert editor.editor.toPlainText() == "<script>x</script>"
    assert "&lt;script&gt;" in editor.html()
