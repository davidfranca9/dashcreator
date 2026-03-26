from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from .data import SETTINGS_GROUPS
from .repository import UGCRepository
from .widgets import (
    ActivityRow,
    BreakdownRow,
    DashboardStatCard,
    FeaturedProjectCard,
    HighlightCard,
    JobCard,
    PipelineStageCard,
    ProspectCard,
    RevenueChart,
    ScheduleRow,
    SectionCard,
    SettingsRow,
    build_checkbox,
    build_combo,
    build_ghost_button,
    clear_layout,
)


class BasePage(QScrollArea):
    def __init__(self, repository: UGCRepository) -> None:
        super().__init__()
        self.repository = repository
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        container.setObjectName("pageBody")
        self.setWidget(container)

        self.body_layout = QVBoxLayout(container)
        self.body_layout.setContentsMargins(0, 0, 0, 20)
        self.body_layout.setSpacing(18)

    def refresh(self) -> None:
        raise NotImplementedError


class DashboardPage(BasePage):
    def __init__(self, repository: UGCRepository, open_jobs_callback) -> None:
        super().__init__(repository)
        self.open_jobs_callback = open_jobs_callback
        self.revenue_range_key = "last_6_months"
        self.refresh()

    def refresh(self) -> None:
        clear_layout(self.body_layout)
        snapshot = self.repository.dashboard_snapshot(self.revenue_range_key)

        stats_row = QHBoxLayout()
        stats_row.setContentsMargins(0, 0, 0, 0)
        stats_row.setSpacing(18)
        for item in snapshot["stats"]:
            stats_row.addWidget(DashboardStatCard(item["title"], item["value"], item["icon"]))
        self.body_layout.addLayout(stats_row)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(18)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(18)

        chart_range = QComboBox()
        chart_range.addItem("Este mes", "current_month")
        chart_range.addItem("Ultimo trimestre", "last_quarter")
        chart_range.addItem("Ultimos 6 meses", "last_6_months")
        chart_range.setCurrentIndex(max(chart_range.findData(self.revenue_range_key), 0))
        chart_range.currentIndexChanged.connect(self._on_revenue_range_changed)

        chart_card = SectionCard("Faturamento Mensal", chart_range)
        chart_card.content_layout.addWidget(RevenueChart(snapshot["revenue_points"]))
        left.addWidget(chart_card, 3)

        activity_card = SectionCard("Atividades Recentes")
        if snapshot["activities"]:
            for activity in snapshot["activities"]:
                activity_card.content_layout.addWidget(
                    ActivityRow(
                        activity["project"],
                        activity["company"],
                        activity["content_type"],
                        activity["progress"],
                        activity["date"],
                        activity["colors"],
                        activity["accent"],
                    )
                )
        else:
            empty_activity = QLabel("Nenhuma atividade recente ainda.")
            empty_activity.setObjectName("mutedText")
            activity_card.content_layout.addWidget(empty_activity)
        left.addWidget(activity_card, 2)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(18)

        pipeline_card = SectionCard("Pipeline de Trabalhos", compact=True)
        for item in snapshot["pipeline"]:
            pipeline_card.content_layout.addWidget(
                PipelineStageCard(
                    item["stage"],
                    item["count"],
                    item["amount"],
                    item["progress"],
                    item["icon"],
                    item["accent"],
                    highlighted=item["stage"] == "Fechado",
                )
            )

        link_button = QPushButton("Ver Trabalhos  >")
        link_button.setObjectName("linkButton")
        link_button.setCursor(Qt.PointingHandCursor)
        link_button.clicked.connect(self.open_jobs_callback)
        pipeline_card.content_layout.addWidget(link_button, 0, Qt.AlignRight)
        right.addWidget(pipeline_card, 3)

        if snapshot["featured"]:
            spotlight = SectionCard("")
            spotlight.content_layout.addWidget(FeaturedProjectCard(snapshot["featured"]))
            right.addWidget(spotlight, 2)
        else:
            spotlight = SectionCard("Projeto em destaque")
            empty_featured = QLabel("Quando voce cadastrar um projeto fechado, ele aparece aqui.")
            empty_featured.setObjectName("mutedText")
            empty_featured.setWordWrap(True)
            spotlight.content_layout.addWidget(empty_featured)
            right.addWidget(spotlight, 2)

        content_row.addLayout(left, 3)
        content_row.addLayout(right, 1)
        self.body_layout.addLayout(content_row)
        self.body_layout.addStretch(1)

    def _on_revenue_range_changed(self, index: int) -> None:
        combo = self.sender()
        if not isinstance(combo, QComboBox):
            return

        selected_key = combo.itemData(index)
        if selected_key == self.revenue_range_key:
            return

        self.revenue_range_key = selected_key
        self.refresh()


class ProspectionPage(BasePage):
    def __init__(self, repository: UGCRepository, on_edit, on_delete, on_convert) -> None:
        super().__init__(repository)
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.on_convert = on_convert
        self.refresh()

    def refresh(self) -> None:
        clear_layout(self.body_layout)
        snapshot = self.repository.prospection_snapshot()

        stats_row = QHBoxLayout()
        stats_row.setContentsMargins(0, 0, 0, 0)
        stats_row.setSpacing(18)
        for item in snapshot["stats"]:
            stats_row.addWidget(DashboardStatCard(item["title"], item["value"], item["icon"]))
        self.body_layout.addLayout(stats_row)

        board_row = QHBoxLayout()
        board_row.setContentsMargins(0, 0, 0, 0)
        board_row.setSpacing(18)

        for column in snapshot["columns"]:
            card = SectionCard(column["title"])
            if not column["items"]:
                empty = QLabel("Nenhum lead nesta etapa.")
                empty.setObjectName("mutedText")
                card.content_layout.addWidget(empty)
            for item in column["items"]:
                card.content_layout.addWidget(
                    ProspectCard(
                        item,
                        on_edit=self.on_edit,
                        on_delete=self.on_delete,
                        on_convert=self.on_convert,
                    )
                )
            card.content_layout.addStretch(1)
            board_row.addWidget(card)

        self.body_layout.addLayout(board_row)
        self.body_layout.addStretch(1)


class JobsPage(BasePage):
    def __init__(self, repository: UGCRepository, on_edit, on_delete) -> None:
        super().__init__(repository)
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.refresh()

    def refresh(self) -> None:
        clear_layout(self.body_layout)
        snapshot = self.repository.jobs_snapshot()

        stats_row = QHBoxLayout()
        stats_row.setContentsMargins(0, 0, 0, 0)
        stats_row.setSpacing(18)
        for item in snapshot["stats"]:
            stats_row.addWidget(DashboardStatCard(item["title"], item["value"], item["icon"]))
        self.body_layout.addLayout(stats_row)

        active_card = SectionCard("Projetos ativos")
        active_grid = QGridLayout()
        active_grid.setContentsMargins(0, 0, 0, 0)
        active_grid.setHorizontalSpacing(18)
        active_grid.setVerticalSpacing(18)
        if snapshot["active"]:
            for index, project in enumerate(snapshot["active"]):
                active_grid.addWidget(JobCard(project, self.on_edit, self.on_delete), index // 2, index % 2)
        else:
            empty_active = QLabel("Nenhum projeto ativo cadastrado ainda.")
            empty_active.setObjectName("mutedText")
            active_grid.addWidget(empty_active, 0, 0)
        active_card.content_layout.addLayout(active_grid)
        self.body_layout.addWidget(active_card)

        delivered_card = SectionCard("Ultimas entregas")
        delivered_grid = QGridLayout()
        delivered_grid.setContentsMargins(0, 0, 0, 0)
        delivered_grid.setHorizontalSpacing(18)
        delivered_grid.setVerticalSpacing(18)
        if snapshot["delivered"]:
            for index, project in enumerate(snapshot["delivered"]):
                delivered_grid.addWidget(JobCard(project, self.on_edit, self.on_delete), index // 2, index % 2)
        else:
            empty_delivered = QLabel("Nenhuma entrega registrada ainda.")
            empty_delivered.setObjectName("mutedText")
            delivered_grid.addWidget(empty_delivered, 0, 0)
        delivered_card.content_layout.addLayout(delivered_grid)
        self.body_layout.addWidget(delivered_card)
        self.body_layout.addStretch(1)


class FinancePage(BasePage):
    def __init__(self, repository: UGCRepository) -> None:
        super().__init__(repository)
        self.refresh()

    def refresh(self) -> None:
        clear_layout(self.body_layout)
        snapshot = self.repository.finance_snapshot()

        stats_row = QHBoxLayout()
        stats_row.setContentsMargins(0, 0, 0, 0)
        stats_row.setSpacing(18)
        for item in snapshot["stats"]:
            stats_row.addWidget(DashboardStatCard(item["title"], item["value"], item["icon"]))
        self.body_layout.addLayout(stats_row)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(18)

        schedule_card = SectionCard("Agenda de recebimentos")
        if snapshot["schedule"]:
            for entry in snapshot["schedule"]:
                schedule_card.content_layout.addWidget(
                    ScheduleRow(entry["company"], entry["kind"], entry["due"], entry["amount"], entry["status"], entry["accent"])
                )
        else:
            empty_schedule = QLabel("Nenhum recebimento pendente no momento.")
            empty_schedule.setObjectName("mutedText")
            schedule_card.content_layout.addWidget(empty_schedule)

        breakdown_card = SectionCard("Distribuicao do caixa")
        for row in snapshot["breakdown"]:
            breakdown_card.content_layout.addWidget(BreakdownRow(row["label"], row["amount_text"], row["progress"], row["accent"]))
        breakdown_card.content_layout.addWidget(build_ghost_button("Exportar resumo"))

        content_row.addWidget(schedule_card, 3)
        content_row.addWidget(breakdown_card, 2)
        self.body_layout.addLayout(content_row)
        self.body_layout.addStretch(1)


class ReportsPage(BasePage):
    def __init__(self, repository: UGCRepository) -> None:
        super().__init__(repository)
        self.refresh()

    def refresh(self) -> None:
        clear_layout(self.body_layout)
        snapshot = self.repository.reports_snapshot()

        stats_row = QHBoxLayout()
        stats_row.setContentsMargins(0, 0, 0, 0)
        stats_row.setSpacing(18)
        for item in snapshot["stats"]:
            stats_row.addWidget(DashboardStatCard(item["title"], item["value"], item["icon"]))
        self.body_layout.addLayout(stats_row)

        report_card = SectionCard("Radar de performance")
        for row in snapshot["breakdown"]:
            report_card.content_layout.addWidget(BreakdownRow(row["label"], row["amount_text"], row["progress"], row["accent"]))
        self.body_layout.addWidget(report_card)

        highlight_card = SectionCard("Leituras estrategicas")
        highlight_row = QHBoxLayout()
        highlight_row.setContentsMargins(0, 0, 0, 0)
        highlight_row.setSpacing(16)
        for item in snapshot["highlights"]:
            highlight_row.addWidget(HighlightCard(item["title"], item["description"]))
        highlight_card.content_layout.addLayout(highlight_row)
        self.body_layout.addWidget(highlight_card)
        self.body_layout.addStretch(1)


class SettingsPage(BasePage):
    def __init__(self, repository: UGCRepository) -> None:
        super().__init__(repository)
        self.refresh()

    def refresh(self) -> None:
        clear_layout(self.body_layout)
        saved_settings = self.repository.get_settings()
        note = QLabel(
            "As configuracoes abaixo agora sao salvas automaticamente no banco local do app."
        )
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        self.body_layout.addWidget(note)

        for group in SETTINGS_GROUPS:
            card = SectionCard(group["title"])
            description = QLabel(group["description"])
            description.setObjectName("mutedText")
            description.setWordWrap(True)
            card.content_layout.addWidget(description)
            for row in group["rows"]:
                saved_value = saved_settings.get(row["id"])
                if row["type"] == "check":
                    bool_value = self._parse_bool(saved_value) if saved_value is not None else bool(row["value"])
                    control = build_checkbox(bool_value)
                    control.stateChanged.connect(
                        lambda _state, setting_id=row["id"], widget=control: self._save_check_setting(setting_id, widget.isChecked())
                    )
                else:
                    combo_value = saved_value if saved_value is not None else row["value"]
                    control = build_combo(row["options"], combo_value)
                    control.currentTextChanged.connect(
                        lambda text, setting_id=row["id"]: self._save_combo_setting(setting_id, text)
                    )
                card.content_layout.addWidget(SettingsRow(row["label"], row["detail"], control))
            self.body_layout.addWidget(card)

        self.body_layout.addStretch(1)

    def _parse_bool(self, value: str | None) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _save_check_setting(self, key: str, checked: bool) -> None:
        self.repository.save_setting(key, "1" if checked else "0")

    def _save_combo_setting(self, key: str, value: str) -> None:
        self.repository.save_setting(key, value)
