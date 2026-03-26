from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDate, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMessageBox,
    QSpinBox,
    QStyle,
    QStyledItemDelegate,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .data import PROJECT_STAGES, PROJECT_STATUSES, PROSPECT_STAGES


class ComboItemDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        rect = option.rect.adjusted(6, 2, -6, -2)
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        background = QColor("#ffffff")
        text_color = QColor("#1a2649")

        if is_selected:
            background = QColor("#e8f1ff")
            text_color = QColor("#245fbe")
        elif is_hovered:
            background = QColor("#f4f8ff")

        painter.setPen(Qt.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(rect, 10, 10)

        painter.setPen(QPen(text_color))
        text_rect = rect.adjusted(12, 0, -12, 0)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, index.data(Qt.DisplayRole))
        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        size = super().sizeHint(option, index)
        size.setHeight(max(size.height(), 36))
        return size


class ComboPopupView(QListView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("comboPopup")
        self.setFrameShape(QFrame.NoFrame)
        self.setMouseTracking(True)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setUniformItemSizes(True)
        self.setSpacing(2)
        self.setItemDelegate(ComboItemDelegate(self))
        self.setStyleSheet(
            """
            QListView#comboPopup {
                background: #ffffff;
                border: 1px solid #d9e4f3;
                border-radius: 16px;
                padding: 6px;
                outline: 0;
            }
            """
        )


class BaseDialog(QDialog):
    def __init__(self, title: str, subtitle: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(520, 640)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 18)
        root.setSpacing(18)

        header = QVBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        title_label.setStyleSheet("font-size: 24px;")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("pageSubtitle")
        subtitle_label.setWordWrap(True)

        header.addWidget(title_label)
        header.addWidget(subtitle_label)
        root.addLayout(header)

        self.body = QWidget()
        self.form_layout = QFormLayout(self.body)
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setHorizontalSpacing(16)
        self.form_layout.setVerticalSpacing(14)
        self.form_layout.setLabelAlignment(self.form_layout.labelAlignment())
        root.addWidget(self.body, 1)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        root.addWidget(self.button_box)


class ProjectDialog(BaseDialog):
    def __init__(self, parent=None, project: dict | None = None, prospect: dict | None = None) -> None:
        subtitle = "Cadastre ou ajuste um projeto com valores, status e datas reais."
        super().__init__("Projeto", subtitle, parent)
        self.project = project
        self.prospect = prospect

        self.company_input = QLineEdit()
        self.project_input = QLineEdit()
        self.type_input = QLineEdit()
        self.stage_input = self._combo_input()
        self.stage_input.addItems(PROJECT_STAGES)
        self.status_input = self._combo_input()
        self.status_input.addItems(PROJECT_STATUSES)

        self.total_value_input = self._money_input()
        self.entry_value_input = self._money_input()
        self.received_value_input = self._money_input()
        self.deliverables_input = self._integer_input(1, 99)
        self.progress_input = self._integer_input(0, 100)

        self.close_date_input = self._date_input()
        self.due_date_input = self._date_input()

        self.form_layout.addRow("Empresa", self.company_input)
        self.form_layout.addRow("Projeto", self.project_input)
        self.form_layout.addRow("Tipo de conteudo", self.type_input)

        stage_row = QWidget()
        stage_layout = QHBoxLayout(stage_row)
        stage_layout.setContentsMargins(0, 0, 0, 0)
        stage_layout.setSpacing(12)
        stage_layout.addWidget(self.stage_input)
        stage_layout.addWidget(self.status_input)
        self.form_layout.addRow("Etapa / status", stage_row)

        value_row = QWidget()
        value_layout = QHBoxLayout(value_row)
        value_layout.setContentsMargins(0, 0, 0, 0)
        value_layout.setSpacing(12)
        value_layout.addWidget(self.total_value_input)
        value_layout.addWidget(self.entry_value_input)
        self.form_layout.addRow("Valor total / entrada", value_row)

        receive_row = QWidget()
        receive_layout = QHBoxLayout(receive_row)
        receive_layout.setContentsMargins(0, 0, 0, 0)
        receive_layout.setSpacing(12)
        receive_layout.addWidget(self.received_value_input)
        receive_layout.addWidget(self.deliverables_input)
        receive_layout.addWidget(self.progress_input)
        self.form_layout.addRow("Recebido / pecas / %", receive_row)

        date_row = QWidget()
        date_layout = QHBoxLayout(date_row)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.setSpacing(12)
        date_layout.addWidget(self.close_date_input)
        date_layout.addWidget(self.due_date_input)
        self.form_layout.addRow("Fechamento / entrega", date_row)

        self._hydrate()

    def _combo_input(self) -> QComboBox:
        widget = QComboBox()
        widget.setView(ComboPopupView(widget))
        widget.setMaxVisibleItems(8)
        return widget

    def _money_input(self) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setRange(0, 1_000_000)
        widget.setDecimals(0)
        widget.setPrefix("R$ ")
        widget.setSingleStep(100)
        widget.setButtonSymbols(QAbstractSpinBox.NoButtons)
        return widget

    def _integer_input(self, minimum: int, maximum: int) -> QSpinBox:
        widget = QSpinBox()
        widget.setRange(minimum, maximum)
        widget.setButtonSymbols(QAbstractSpinBox.NoButtons)
        return widget

    def _date_input(self) -> QDateEdit:
        widget = QDateEdit()
        widget.setCalendarPopup(True)
        widget.setDisplayFormat("dd/MM/yyyy")
        widget.setDate(QDate.currentDate())
        return widget

    def _hydrate(self) -> None:
        if self.project:
            self.company_input.setText(self.project["company"])
            self.project_input.setText(self.project["project_name"])
            self.type_input.setText(self.project["content_type"])
            self.stage_input.setCurrentText(self.project["stage"])
            self.status_input.setCurrentText(self.project["status"])
            self.total_value_input.setValue(float(self.project["total_value"]))
            self.entry_value_input.setValue(float(self.project["entry_value"]))
            self.received_value_input.setValue(float(self.project["received_value"]))
            self.deliverables_input.setValue(int(self.project["deliverables_count"]))
            self.progress_input.setValue(int(self.project["progress"]))
            self.close_date_input.setDate(QDate.fromString(self.project["close_date"], "yyyy-MM-dd"))
            self.due_date_input.setDate(QDate.fromString(self.project["due_date"], "yyyy-MM-dd"))
            return

        if self.prospect:
            self.company_input.setText(self.prospect["company"])
            self.project_input.setText(f"Projeto {self.prospect['company']}")
            self.stage_input.setCurrentText("Fechado")
            self.status_input.setCurrentText("Briefing")
            self.total_value_input.setValue(float(self.prospect["proposal_value"]))
            self.entry_value_input.setValue(float(self.prospect["proposal_value"]) * 0.5)
            self.received_value_input.setValue(0)
            self.deliverables_input.setValue(3)
            self.progress_input.setValue(15)
            self.close_date_input.setDate(QDate.currentDate())
            self.due_date_input.setDate(QDate.currentDate().addDays(12))
            return

        self.stage_input.setCurrentText("Fechado")
        self.status_input.setCurrentText("Briefing")
        self.deliverables_input.setValue(3)
        self.progress_input.setValue(10)
        self.close_date_input.setDate(QDate.currentDate())
        self.due_date_input.setDate(QDate.currentDate().addDays(12))

    def accept(self) -> None:
        if not self.company_input.text().strip() or not self.project_input.text().strip():
            QMessageBox.warning(self, "Campos obrigatorios", "Preencha empresa e nome do projeto.")
            return

        if self.entry_value_input.value() > self.total_value_input.value():
            QMessageBox.warning(self, "Valores invalidos", "A entrada nao pode ser maior que o valor total.")
            return

        if self.received_value_input.value() > self.total_value_input.value():
            QMessageBox.warning(self, "Valores invalidos", "O valor recebido nao pode ser maior que o total.")
            return

        super().accept()

    def payload(self) -> dict:
        return {
            "company": self.company_input.text().strip(),
            "project_name": self.project_input.text().strip(),
            "content_type": self.type_input.text().strip(),
            "stage": self.stage_input.currentText(),
            "status": self.status_input.currentText(),
            "total_value": int(self.total_value_input.value()),
            "entry_value": int(self.entry_value_input.value()),
            "received_value": int(self.received_value_input.value()),
            "deliverables_count": int(self.deliverables_input.value()),
            "progress": int(self.progress_input.value()),
            "close_date": self.close_date_input.date().toString("yyyy-MM-dd"),
            "due_date": self.due_date_input.date().toString("yyyy-MM-dd"),
        }


class ProspectDialog(BaseDialog):
    def __init__(self, parent=None, prospect: dict | None = None) -> None:
        subtitle = "Registre e acompanhe oportunidades antes do fechamento."
        super().__init__("Lead / prospeccao", subtitle, parent)
        self.prospect = prospect

        self.company_input = QLineEdit()
        self.contact_input = QLineEdit()
        self.stage_input = self._combo_input()
        self.stage_input.addItems(PROSPECT_STAGES)
        self.value_input = self._money_input()
        self.value_input.setRange(0, 500000)
        self.meeting_input = QCheckBox("Reuniao agendada")
        self.note_input = QTextEdit()
        self.note_input.setFixedHeight(140)

        self.form_layout.addRow("Empresa", self.company_input)
        self.form_layout.addRow("Contato", self.contact_input)
        self.form_layout.addRow("Etapa", self.stage_input)
        self.form_layout.addRow("Valor estimado", self.value_input)
        self.form_layout.addRow("", self.meeting_input)
        self.form_layout.addRow("Observacoes", self.note_input)

        if self.prospect:
            self.company_input.setText(self.prospect["company"])
            self.contact_input.setText(self.prospect["contact"])
            self.stage_input.setCurrentText(self.prospect["stage"])
            self.value_input.setValue(float(self.prospect["proposal_value"]))
            self.meeting_input.setChecked(bool(self.prospect["meeting_scheduled"]))
            self.note_input.setPlainText(self.prospect["note"])

    def _combo_input(self) -> QComboBox:
        widget = QComboBox()
        widget.setView(ComboPopupView(widget))
        widget.setMaxVisibleItems(8)
        return widget

    def _money_input(self) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setRange(0, 500000)
        widget.setDecimals(0)
        widget.setPrefix("R$ ")
        widget.setSingleStep(100)
        widget.setButtonSymbols(QAbstractSpinBox.NoButtons)
        return widget

    def accept(self) -> None:
        if not self.company_input.text().strip() or not self.contact_input.text().strip():
            QMessageBox.warning(self, "Campos obrigatorios", "Preencha empresa e contato.")
            return
        super().accept()

    def payload(self) -> dict:
        return {
            "company": self.company_input.text().strip(),
            "contact": self.contact_input.text().strip(),
            "stage": self.stage_input.currentText(),
            "proposal_value": int(self.value_input.value()),
            "note": self.note_input.toPlainText().strip(),
            "meeting_scheduled": 1 if self.meeting_input.isChecked() else 0,
        }
