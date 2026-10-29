"""Detalle de una orden: resumen, cambio de estado, notas, entrega e historial (§9).

El cobro no vive aquí: los pagos se registran en la pestaña «Presupuesto y pagos», que es el
único sitio donde se mueve el dinero de la orden (§5.7).
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from luciotech.database.enums import OrderState
from luciotech.database.models import ServiceOrder
from luciotech.services.order_detail_service import (
    PaymentValidationError,
    add_note,
    mark_delivered,
    order_timeline,
)
from luciotech.services.order_service import soft_delete_order
from luciotech.services.order_view_service import (
    CustomerView,
    EquipmentView,
    customer_view,
    equipment_view,
)
from luciotech.services.clinical_text_service import (
    ClinicalTexts,
    get_clinical_texts,
    save_clinical_texts,
)
from luciotech.services.predefined_text_service import predefined_texts
from luciotech.services.settings_service import tax_settings
from luciotech.services.state_service import change_order_state
from luciotech.services.totals_service import OrderTotals, order_totals
from luciotech.ui.dialogs.budget_payments_tab import BudgetPaymentsTab
from luciotech.ui.dialogs.document_chooser_dialog import DocumentChooserDialog
from luciotech.ui.dialogs.photographs_tab import PhotographsTab
from luciotech.ui.documents import DocumentKind, print_order_document
from luciotech.ui.formatting import format_datetime, format_money
from luciotech.ui.order_actions import NextAction, next_action
from luciotech.ui.widgets.rich_text_editor import RichTextEditor
from luciotech.ui.validation_texts import error_text

HISTORY_COLUMNS = ("Fecha", "Tipo", "Detalle", "Usuario")
AUTOSAVE_DELAY_MS = 1500

# El diálogo se abre con el mayor tamaño cómodo de la pantalla: la pestaña de presupuesto tiene
# que enseñar el desglose completo sin recortarlo (§12).
PRIMARY_BUTTON_HEIGHT = 38
SCREEN_RATIO = 0.92
MAX_WIDTH = 1180
MAX_HEIGHT = 1000


class OrderDetailDialog(QDialog):
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        order_id: int,
        usuario: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._order_id = order_id
        self._usuario = usuario
        self.setWindowTitle(self.tr("Orden de servicio"))

        self._summary = QLabel()
        self._summary.setWordWrap(True)
        self._state_combo = QComboBox()
        for state in OrderState:
            self._state_combo.addItem(state.value, state.value)
        self._state_comment = QLineEdit()
        self._state_comment.setPlaceholderText(self.tr("Comentario del cambio (opcional)"))
        change_button = QPushButton(self.tr("Cambiar estado"))
        change_button.clicked.connect(self._change_state)

        self._note_title = QLineEdit()
        self._note_title.setPlaceholderText(self.tr("Título de la nota"))
        self._note_body = QLineEdit()
        self._note_body.setPlaceholderText(self.tr("Detalle (opcional)"))
        note_button = QPushButton(self.tr("Añadir nota"))
        note_button.clicked.connect(self._add_note)

        self._history = QTableWidget(0, len(HISTORY_COLUMNS))
        self._history.setHorizontalHeaderLabels([self.tr(c) for c in HISTORY_COLUMNS])
        self._history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._history.verticalHeader().setVisible(False)
        self._history.horizontalHeader().setStretchLastSection(True)

        self._message = QLabel()
        self._message.setWordWrap(True)

        state_row = QHBoxLayout()
        state_row.addWidget(self._state_combo)
        state_row.addWidget(self._state_comment, 1)
        state_row.addWidget(change_button)

        note_row = QHBoxLayout()
        note_row.addWidget(self._note_title, 1)
        note_row.addWidget(self._note_body, 2)
        note_row.addWidget(note_button)

        actions = QGroupBox(self.tr("Acciones"))
        actions_layout = QVBoxLayout(actions)
        actions_layout.addLayout(state_row)
        actions_layout.addLayout(note_row)

        self._next_action = next_action(OrderState.RECIBIDO)
        self._primary_button = QPushButton(self._next_action.label)
        self._primary_button.setMinimumHeight(PRIMARY_BUTTON_HEIGHT)
        primary_font = self._primary_button.font()
        primary_font.setBold(True)
        self._primary_button.setFont(primary_font)
        self._primary_button.clicked.connect(self._run_primary)
        self._primary_hint = QLabel(self._next_action.hint)
        self._primary_hint.setWordWrap(True)

        primary_box = QGroupBox(self.tr("Siguiente paso"))
        primary_layout = QVBoxLayout(primary_box)
        primary_layout.addWidget(self._primary_button)
        primary_layout.addWidget(self._primary_hint)

        summary_tab = QWidget()
        summary_layout = QVBoxLayout(summary_tab)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.addWidget(primary_box)
        summary_layout.addWidget(self._summary)
        summary_layout.addStretch(1)

        self._customer_text = QLabel()
        self._customer_text.setWordWrap(True)
        self._equipment_text = QLabel()
        self._equipment_text.setWordWrap(True)
        self._toggle_password = QPushButton(self.tr("Mostrar contraseña"))
        self._toggle_password.setCheckable(True)
        self._toggle_password.toggled.connect(self._on_toggle_password)

        with self._session_factory() as session:
            predefined = predefined_texts(session)
        self._diagnosis = RichTextEditor(predefined=predefined)
        self._recommendations = RichTextEditor(predefined=predefined)
        self._work_performed = RichTextEditor(predefined=predefined)

        tabs = QTabWidget()
        tabs.addTab(_scrollable(summary_tab), self.tr("Resumen"))
        tabs.addTab(_scrollable(self._customer_text), self.tr("Cliente"))
        equipment_tab = QWidget()
        equipment_layout = QVBoxLayout(equipment_tab)
        equipment_layout.addWidget(self._equipment_text)
        equipment_layout.addWidget(self._toggle_password, alignment=Qt.AlignmentFlag.AlignLeft)
        equipment_layout.addStretch(1)
        tabs.addTab(equipment_tab, self.tr("Equipo"))

        diagnosis_tab = QWidget()
        diagnosis_layout = QVBoxLayout(diagnosis_tab)
        diagnosis_layout.setContentsMargins(0, 0, 0, 0)
        diagnosis_layout.setSpacing(2)
        diagnosis_layout.addWidget(QLabel(self.tr("Diagnóstico técnico")))
        diagnosis_layout.addWidget(self._diagnosis, 1)
        tabs.addTab(diagnosis_tab, self.tr("Diagnóstico"))

        repair_tab = QWidget()
        repair_layout = QVBoxLayout(repair_tab)
        repair_layout.setContentsMargins(0, 0, 0, 0)
        repair_layout.setSpacing(2)
        repair_layout.addWidget(QLabel(self.tr("Trabajo realizado")))
        repair_layout.addWidget(self._work_performed, 1)
        tabs.addTab(repair_tab, self.tr("Reparación"))

        recommendations_tab = QWidget()
        recommendations_layout = QVBoxLayout(recommendations_tab)
        recommendations_layout.setContentsMargins(0, 0, 0, 0)
        recommendations_layout.setSpacing(2)
        recommendations_layout.addWidget(QLabel(self.tr("Recomendaciones al cliente")))
        recommendations_layout.addWidget(self._recommendations, 1)
        tabs.addTab(recommendations_tab, self.tr("Recomendaciones"))

        self._photos = PhotographsTab(session_factory)
        self._photos.set_order(self._order_id)
        tabs.addTab(self._photos, self.tr("Fotografías"))

        self._budget_payments = BudgetPaymentsTab(session_factory, usuario=self._usuario)
        self._budget_payments.set_order(self._order_id)
        self._budget_payments.changed.connect(self.refresh)
        tabs.addTab(self._budget_payments, self.tr("Presupuesto y pagos"))

        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        history_layout.addWidget(self._history)
        tabs.addTab(history_tab, self.tr("Historial"))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        self._documents_button = QPushButton(self.tr("Documentos…"))
        self._documents_button.setToolTip(
            self.tr("Imprimir o guardar en PDF los documentos de la orden")
        )
        self._documents_button.clicked.connect(self._print_document)
        self._delete_button = QPushButton(self.tr("Eliminar orden"))
        self._delete_button.clicked.connect(self._delete_order)

        save_texts_button = QPushButton(self.tr("Guardar textos"))
        save_texts_button.clicked.connect(self._save_clinical_texts)

        bottom_row = QHBoxLayout()
        bottom_row.addWidget(self._documents_button)
        bottom_row.addWidget(save_texts_button)
        bottom_row.addStretch(1)
        bottom_row.addWidget(self._delete_button)
        bottom_row.addWidget(buttons)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs, 1)
        layout.addWidget(actions)
        layout.addWidget(self._message)
        layout.addLayout(bottom_row)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(AUTOSAVE_DELAY_MS)
        self._autosave_timer.timeout.connect(self._autosave_clinical_texts)
        self._saved_clinical_html: tuple[str, str, str] = ("", "", "")
        self._load_clinical_texts()
        for editor in self._clinical_editors():
            editor.editor.document().contentsChanged.connect(self._schedule_autosave)
        self.refresh()
        self._fit_to_screen()

    def _fit_to_screen(self) -> None:
        """Abre el diálogo con el mayor tamaño cómodo de la pantalla.

        El tamaño mínimo lo fija el propio contenido (`SetMinimumSize`), así que la ventana no
        puede encogerse hasta recortar el panel de totales; aquí solo se decide con cuánto
        espacio se abre y se centra.
        """
        screen = self.screen() or QApplication.primaryScreen()
        needed = self.layout().minimumSize()
        self.setMinimumSize(needed)
        if screen is None:
            self.resize(max(MAX_WIDTH, needed.width()), max(MAX_HEIGHT, needed.height()))
            return
        available = screen.availableGeometry()
        width = max(min(MAX_WIDTH, int(available.width() * SCREEN_RATIO)), needed.width())
        height = max(min(MAX_HEIGHT, int(available.height() * SCREEN_RATIO)), needed.height())
        self.resize(width, height)
        self.move(
            available.x() + max(0, (available.width() - width) // 2),
            available.y() + max(0, (available.height() - height) // 2),
        )

    def refresh(self) -> None:
        with self._session_factory() as session:
            order = session.get(ServiceOrder, self._order_id)
            if order is None:
                self._message.setText(self.tr("La orden ya no existe."))
                return
            self.setWindowTitle(f"{self.tr('Orden')} {order.numero_orden}")
            self._summary.setText(
                _summary_html(order, order_totals(order, tax_settings(session)))
            )
            self._customer_text.setText(_customer_html(customer_view(session, order)))
            self._equipment_text.setText(
                _equipment_html(equipment_view(order), reveal=self._toggle_password.isChecked())
            )
            self._show_next_action(order.estado)
            index = self._state_combo.findData(order.estado)
            if index >= 0:
                self._state_combo.setCurrentIndex(index)
            self._delete_button.setEnabled(order.activo)
            self._fill_history(order)
        self._budget_payments.refresh()

    def _on_toggle_password(self, shown: bool) -> None:
        self._toggle_password.setText(
            self.tr("Ocultar contraseña") if shown else self.tr("Mostrar contraseña")
        )
        self.refresh()

    def _clinical_editors(self) -> tuple[RichTextEditor, RichTextEditor, RichTextEditor]:
        return self._diagnosis, self._work_performed, self._recommendations

    def _current_clinical_html(self) -> tuple[str, str, str]:
        diagnosis, work, recommendations = self._clinical_editors()
        return diagnosis.html(), work.html(), recommendations.html()

    def _load_clinical_texts(self) -> None:
        """Carga los textos guardados. refresh() no los recarga, para no pisar lo que se escribe."""
        with self._session_factory() as session:
            order = session.get(ServiceOrder, self._order_id)
            if order is None:
                return
            texts = get_clinical_texts(order)
        self._diagnosis.set_html(texts.diagnostico_html)
        self._recommendations.set_html(texts.recomendaciones_html)
        self._work_performed.set_html(texts.trabajo_realizado_html)
        self._saved_clinical_html = self._current_clinical_html()

    def _schedule_autosave(self) -> None:
        self._autosave_timer.start()

    def _autosave_clinical_texts(self) -> None:
        self._persist_clinical_texts(show_message=False)

    def _save_clinical_texts(self) -> None:
        self._persist_clinical_texts(show_message=True)

    def _persist_clinical_texts(self, show_message: bool) -> bool:
        """Guarda los textos solo si cambiaron desde el último guardado. Devuelve True si quedaron guardados."""
        current = self._current_clinical_html()
        if current == self._saved_clinical_html:
            if show_message:
                self._message.setText(self.tr("Guardado."))
            return True
        self._autosave_timer.stop()
        diagnosis, work, recommendations = current
        texts = ClinicalTexts(
            diagnostico_html=diagnosis,
            trabajo_realizado_html=work,
            recomendaciones_html=recommendations,
        )
        try:
            with self._session_factory() as session:
                order = session.get(ServiceOrder, self._order_id)
                if order is None:
                    raise ValueError(self.tr("La orden ya no existe."))
                save_clinical_texts(session, order, texts)
                session.commit()
        except (SQLAlchemyError, ValueError) as exc:
            self._message.setText(self.tr("No se pudieron guardar los textos: %1").replace("%1", str(exc)))
            if not show_message:
                self._autosave_timer.start()
            return False
        self._saved_clinical_html = current
        self._message.setText(
            self.tr("Textos guardados.") if show_message else self.tr("Cambios guardados automáticamente.")
        )
        self._refresh_history_only()
        return True

    def _refresh_history_only(self) -> None:
        with self._session_factory() as session:
            order = session.get(ServiceOrder, self._order_id)
            if order is not None:
                self._fill_history(order)

    def reject(self) -> None:
        """Al cerrar, guarda lo pendiente. Si no se puede guardar, pide confirmación antes de descartarlo."""
        if not self._persist_clinical_texts(show_message=False):
            answer = QMessageBox.question(
                self,
                self.windowTitle(),
                self.tr("No se pudieron guardar los textos clínicos. ¿Cerrar de todos modos?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._autosave_timer.stop()
        super().reject()

    def _fill_history(self, order: ServiceOrder) -> None:
        entries = order_timeline(order)
        self._history.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            cells = [format_datetime(entry.fecha), entry.titulo, entry.detalle, entry.usuario]
            for column, value in enumerate(cells):
                self._history.setItem(row, column, QTableWidgetItem(value))

    def _run(self, action: Callable[[Session, ServiceOrder], object]) -> bool:
        """Ejecuta una acción dentro de una sesión, la confirma y refresca la vista."""
        try:
            with self._session_factory() as session:
                order = session.get(ServiceOrder, self._order_id)
                if order is None:
                    raise ValueError(self.tr("La orden ya no existe."))
                action(session, order)
                session.commit()
        except PaymentValidationError as exc:
            self._message.setText("\n".join(error_text(code) for code in exc.errors.values()))
            return False
        except ValueError as exc:
            self._message.setText(str(exc))
            return False
        except SQLAlchemyError:
            QMessageBox.critical(
                self, self.windowTitle(), self.tr("No se pudo guardar. Intente de nuevo.")
            )
            return False
        self._message.setText(self.tr("Guardado."))
        self.refresh()
        return True

    def _change_state(self) -> None:
        nuevo = self._state_combo.currentData()
        if nuevo == OrderState.ENTREGADO.value:
            self._deliver()
            return
        comment = self._state_comment.text().strip() or None
        self._run(
            lambda session, order: change_order_state(
                session, order, nuevo, usuario=self._usuario, comentario=comment
            )
        )

    def _add_note(self) -> None:
        title = self._note_title.text()
        body = self._note_body.text()
        self._run(
            lambda session, order: add_note(
                session, order, titulo=title, descripcion=body, usuario=self._usuario
            )
        )

    def _show_next_action(self, state: str) -> None:
        """Pinta el siguiente paso que propone el estado de la orden (§9)."""
        self._next_action = next_action(state)
        self._primary_button.setText(self.tr(self._next_action.label))
        self._primary_hint.setText(self.tr(self._next_action.hint))
        self._primary_hint.setVisible(bool(self._next_action.hint))
        self._primary_button.setEnabled(self._next_action.available)

    def _run_primary(self) -> None:
        """Ejecuta el siguiente paso: cambia el estado y, si toca, abre el documento."""
        action: NextAction = self._next_action
        if not action.available:
            return
        if action.delivers:
            if not self._confirm_delivery():
                return
            if not self._run(
                lambda session, order: mark_delivered(session, order, usuario=self._usuario)
            ):
                return
        elif action.state is not None:
            if not self._run(
                lambda session, order: change_order_state(
                    session, order, action.state, usuario=self._usuario
                )
            ):
                return
        if action.document is not None:
            self._open_document(action.document)

    def _confirm_delivery(self) -> bool:
        answer = QMessageBox.question(
            self,
            self.windowTitle(),
            self.tr("¿Marcar la orden como entregada?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _deliver(self) -> None:
        if not self._confirm_delivery():
            return
        self._run(lambda session, order: mark_delivered(session, order, usuario=self._usuario))

    def _open_document(self, kind: DocumentKind) -> None:
        """Abre la vista previa del documento pedido y lo anota en el mensaje."""
        if print_order_document(self._session_factory, self._order_id, kind, self):
            self._message.setText(
                self.tr("Vista previa: {documento}.").format(documento=self.tr(kind.value))
            )

    def _print_document(self) -> None:
        """Pide qué documento imprimir y abre su vista previa (§13.1 y §13.3)."""
        kind = DocumentChooserDialog.choose(self)
        if kind is not None:
            self._open_document(kind)

    def _delete_order(self) -> None:
        """Borra lógicamente la orden: se pide confirmación y se envía a la papelera (§18)."""
        answer = QMessageBox.warning(
            self,
            self.windowTitle(),
            self.tr(
                "La orden se enviará a la papelera y dejará de aparecer en la lista. "
                "Podrá restaurarla desde la pestaña Papelera.\n\n¿Desea continuar?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            with self._session_factory() as session:
                order = session.get(ServiceOrder, self._order_id)
                if order is None:
                    raise ValueError(self.tr("La orden ya no existe."))
                soft_delete_order(session, order, usuario=self._usuario)
                session.commit()
        except ValueError as exc:
            self._message.setText(str(exc))
            return
        except SQLAlchemyError:
            QMessageBox.critical(
                self, self.windowTitle(), self.tr("No se pudo eliminar. Intente de nuevo.")
            )
            return
        self._autosave_timer.stop()
        super().reject()


def _table(rows: list[tuple[str, str]]) -> str:
    body = "".join(
        f"<tr><td><b>{_escape(label)}</b></td><td>{_escape(value)}</td></tr>" for label, value in rows
    )
    return f"<table cellspacing='4'>{body}</table>"


def _customer_html(view: CustomerView) -> str:
    rows = [
        ("Nombre", view.nombre_completo),
        ("Identificación", view.numero_identificacion or "-"),
        ("Teléfono principal", view.telefono_principal or "-"),
        ("Teléfono secundario", view.telefono_secundario or "-"),
        ("Correo", view.correo_electronico or "-"),
        ("Dirección", view.direccion or "-"),
        ("Notas", view.notas or "-"),
        ("Otras órdenes", ", ".join(view.otras_ordenes) or "-"),
        ("Saldo pendiente total", format_money(view.saldo_pendiente_total)),
    ]
    return _table(rows)


def _equipment_html(view: EquipmentView, reveal: bool) -> str:
    password = view.contrasena_equipo or "-"
    if view.contrasena_equipo and not reveal:
        password = "••••••"
    rows = [
        ("Tipo", view.tipo_equipo),
        ("Marca", view.marca or "-"),
        ("Modelo", view.modelo or "-"),
        ("Número de serie", view.numero_serie or "-"),
        ("Color", view.color or "-"),
        ("Sistema operativo", view.sistema_operativo or "-"),
        ("Contraseña o PIN", password),
        ("Accesorios recibidos", view.accesorios_recibidos or "-"),
        ("Estado físico", view.estado_fisico or "-"),
        ("Problema reportado", view.problema_reportado_cliente or "-"),
        ("Observaciones de ingreso", view.observaciones_ingreso or "-"),
    ]
    return _table(rows)


def _scrollable(content: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(content)
    return area


def _summary_html(order: ServiceOrder, totals: OrderTotals) -> str:
    """Resumen de la orden con los importes calculados, igual que la pestaña de presupuesto."""
    equipment = order.equipment
    customer = order.customer
    rows = [
        ("Número de orden", order.numero_orden),
        ("Estado", order.estado),
        ("Prioridad", order.prioridad),
        ("Cliente", f"{customer.nombre_completo} ({customer.telefono_principal or '-'})"),
        ("Equipo", f"{equipment.tipo_equipo} {equipment.marca or ''} {equipment.modelo or ''}".strip()),
        ("Número de serie", equipment.numero_serie or "-"),
        ("Fecha de ingreso", format_datetime(order.fecha_ingreso)),
        ("Fecha estimada", format_datetime(order.fecha_estimada_entrega) or "-"),
        ("Fecha de entrega", format_datetime(order.fecha_entrega) or "-"),
        ("Técnico responsable", order.tecnico_responsable or "-"),
        ("Problema reportado", order.problema_reportado or "-"),
        ("Total", format_money(totals.total)),
        ("Anticipo", format_money(order.anticipo)),
        ("Saldo pendiente", format_money(totals.saldo_pendiente)),
    ]
    return _table(rows)


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )
