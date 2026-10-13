"""Detalle de una orden: resumen, cambio de estado, pagos, notas, entrega e historial (§9)."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal, InvalidOperation

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
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

from luciotech.database.enums import OrderState, PaymentMethod, PaymentType
from luciotech.database.models import ServiceOrder
from luciotech.services.order_detail_service import (
    PaymentValidationError,
    add_note,
    mark_delivered,
    order_timeline,
    register_payment,
)
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
from luciotech.services.state_service import change_order_state
from luciotech.ui.dialogs.photographs_tab import PhotographsTab
from luciotech.ui.formatting import format_datetime, format_money
from luciotech.ui.widgets.rich_text_editor import RichTextEditor
from luciotech.ui.validation_texts import error_text

HISTORY_COLUMNS = ("Fecha", "Tipo", "Detalle", "Usuario")
AUTOSAVE_DELAY_MS = 1500


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
        self.setMinimumSize(760, 560)
        self.resize(960, 720)

        self._summary = QLabel()
        self._summary.setWordWrap(True)
        self._state_combo = QComboBox()
        for state in OrderState:
            self._state_combo.addItem(state.value, state.value)
        self._state_comment = QLineEdit()
        self._state_comment.setPlaceholderText(self.tr("Comentario del cambio (opcional)"))
        change_button = QPushButton(self.tr("Cambiar estado"))
        change_button.clicked.connect(self._change_state)

        self._payment_type = QComboBox()
        for kind in PaymentType:
            self._payment_type.addItem(kind.value, kind.value)
        self._payment_method = QComboBox()
        for method in PaymentMethod:
            self._payment_method.addItem(method.value, method.value)
        self._payment_amount = QLineEdit()
        self._payment_amount.setPlaceholderText("0.00")
        self._payment_reference = QLineEdit()
        self._payment_reference.setPlaceholderText(self.tr("Referencia (opcional)"))
        pay_button = QPushButton(self.tr("Registrar pago"))
        pay_button.clicked.connect(self._register_payment)

        self._note_title = QLineEdit()
        self._note_title.setPlaceholderText(self.tr("Título de la nota"))
        self._note_body = QLineEdit()
        self._note_body.setPlaceholderText(self.tr("Detalle (opcional)"))
        note_button = QPushButton(self.tr("Añadir nota"))
        note_button.clicked.connect(self._add_note)

        deliver_button = QPushButton(self.tr("Marcar como entregado"))
        deliver_button.clicked.connect(self._deliver)

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

        payment_form = QFormLayout()
        payment_row = QHBoxLayout()
        payment_row.addWidget(self._payment_type)
        payment_row.addWidget(self._payment_method)
        payment_row.addWidget(self._payment_amount)
        payment_row.addWidget(self._payment_reference, 1)
        payment_row.addWidget(pay_button)
        payment_form.addRow(self.tr("Pago o reembolso"), payment_row)

        note_row = QHBoxLayout()
        note_row.addWidget(self._note_title, 1)
        note_row.addWidget(self._note_body, 2)
        note_row.addWidget(note_button)

        actions = QGroupBox(self.tr("Acciones"))
        actions_layout = QVBoxLayout(actions)
        actions_layout.addLayout(state_row)
        actions_layout.addLayout(payment_form)
        actions_layout.addLayout(note_row)

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
        tabs.addTab(_scrollable(self._summary), self.tr("Resumen"))
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

        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        history_layout.addWidget(self._history)
        tabs.addTab(history_tab, self.tr("Historial"))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        save_texts_button = QPushButton(self.tr("Guardar textos"))
        save_texts_button.clicked.connect(self._save_clinical_texts)

        bottom_row = QHBoxLayout()
        bottom_row.addWidget(deliver_button)
        bottom_row.addWidget(save_texts_button)
        bottom_row.addStretch(1)
        bottom_row.addWidget(buttons)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs, 1)
        layout.addWidget(actions)
        layout.addWidget(self._message)
        layout.addLayout(bottom_row)

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(AUTOSAVE_DELAY_MS)
        self._autosave_timer.timeout.connect(self._autosave_clinical_texts)
        self._saved_clinical_html: tuple[str, str, str] = ("", "", "")
        self._load_clinical_texts()
        for editor in self._clinical_editors():
            editor.editor.document().contentsChanged.connect(self._schedule_autosave)
        self.refresh()

    def refresh(self) -> None:
        with self._session_factory() as session:
            order = session.get(ServiceOrder, self._order_id)
            if order is None:
                self._message.setText(self.tr("La orden ya no existe."))
                return
            self.setWindowTitle(f"{self.tr('Orden')} {order.numero_orden}")
            self._summary.setText(_summary_html(order))
            self._customer_text.setText(_customer_html(customer_view(session, order)))
            self._equipment_text.setText(
                _equipment_html(equipment_view(order), reveal=self._toggle_password.isChecked())
            )
            index = self._state_combo.findData(order.estado)
            if index >= 0:
                self._state_combo.setCurrentIndex(index)
            self._fill_history(order)

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
        comment = self._state_comment.text().strip() or None
        self._run(
            lambda session, order: change_order_state(
                session, order, nuevo, usuario=self._usuario, comentario=comment
            )
        )

    def _register_payment(self) -> None:
        try:
            amount = Decimal(self._payment_amount.text().strip().replace(",", "."))
        except InvalidOperation:
            self._message.setText(error_text("amount.invalid"))
            return
        tipo = self._payment_type.currentData()
        metodo = self._payment_method.currentData()
        reference = self._payment_reference.text()
        self._run(
            lambda session, order: register_payment(
                session, order, tipo=tipo, metodo=metodo, monto=amount,
                usuario=self._usuario, referencia=reference,
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

    def _deliver(self) -> None:
        answer = QMessageBox.question(
            self,
            self.windowTitle(),
            self.tr("¿Marcar la orden como entregada?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._run(lambda session, order: mark_delivered(session, order, usuario=self._usuario))


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


def _summary_html(order: ServiceOrder) -> str:
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
        ("Problema reportado", order.problema_reportado or "-"),
        ("Total", format_money(order.total)),
        ("Anticipo", format_money(order.anticipo)),
        ("Saldo pendiente", format_money(order.saldo_pendiente)),
    ]
    return _table(rows)


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )
