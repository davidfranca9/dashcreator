from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .data import NAV_ITEMS
from .dialogs import ProjectDialog, ProspectDialog
from .pages import DashboardPage, FinancePage, JobsPage, ProspectionPage, ReportsPage, SettingsPage
from .repository import UGCRepository
from .widgets import make_icon


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sistema de Gestao de Demandas UGC")
        self.resize(1540, 940)
        self.setMinimumSize(1320, 840)

        self.repository = UGCRepository()
        self.repository.changed.connect(self.refresh_pages)

        self.current_page_key = "dashboard"
        self.pages = {}
        self.nav_meta = {item["key"]: item for item in NAV_ITEMS}

        root = QWidget()
        root.setObjectName("appRoot")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())
        root_layout.addWidget(self._build_content_area(), 1)

        self.setCentralWidget(root)
        self._set_current_page("dashboard")

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(328)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(32, 32, 24, 28)
        layout.setSpacing(28)

        brand = QVBoxLayout()
        brand.setContentsMargins(0, 0, 0, 0)
        brand.setSpacing(4)
        title = QLabel("UGC Management")
        title.setObjectName("brandTitle")
        subtitle = QLabel("Creative + financial workflow")
        subtitle.setObjectName("brandSubtitle")
        brand.addWidget(title)
        brand.addWidget(subtitle)
        layout.addLayout(brand)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = {}

        nav_layout = QVBoxLayout()
        nav_layout.setContentsMargins(0, 10, 0, 0)
        nav_layout.setSpacing(14)

        for item in NAV_ITEMS:
            button = QPushButton(item["label"])
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setIcon(make_icon(item["icon"], "#edf5ff", 18))
            button.setIconSize(QSize(22, 22))
            button.clicked.connect(lambda checked=False, key=item["key"]: self._set_current_page(key))
            nav_layout.addWidget(button)
            self.nav_group.addButton(button)
            self.nav_buttons[item["key"]] = button

        nav_layout.addStretch(1)
        layout.addLayout(nav_layout)
        return sidebar

    def _build_content_area(self) -> QWidget:
        content = QWidget()
        content.setObjectName("contentArea")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(34, 26, 34, 26)
        layout.setSpacing(18)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        title_block = QVBoxLayout()
        title_block.setContentsMargins(0, 0, 0, 0)
        title_block.setSpacing(3)
        self.page_title = QLabel()
        self.page_title.setObjectName("pageTitle")
        self.page_subtitle = QLabel()
        self.page_subtitle.setObjectName("pageSubtitle")
        title_block.addWidget(self.page_title)
        title_block.addWidget(self.page_subtitle)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(10)

        self.add_button = QToolButton()
        self.add_button.setObjectName("headerAction")
        self.add_button.setText("+")
        self.add_button.setCursor(Qt.PointingHandCursor)
        self.add_button.clicked.connect(self._handle_add_action)

        self.more_button = QToolButton()
        self.more_button.setObjectName("headerAction")
        self.more_button.setText("...")
        self.more_button.setCursor(Qt.PointingHandCursor)
        self.more_button.clicked.connect(self._create_backup)

        actions.addWidget(self.add_button)
        actions.addWidget(self.more_button)

        header_layout.addLayout(title_block, 1)
        header_layout.addLayout(actions)
        layout.addWidget(header)

        self.stack = QStackedWidget()
        self.stack.setObjectName("pageStack")

        self.pages["dashboard"] = DashboardPage(self.repository, lambda: self._set_current_page("jobs"))
        self.pages["prospection"] = ProspectionPage(self.repository, self._edit_prospect, self._delete_prospect, self._convert_prospect)
        self.pages["jobs"] = JobsPage(self.repository, self._edit_project, self._delete_project)
        self.pages["finance"] = FinancePage(self.repository)
        self.pages["reports"] = ReportsPage(self.repository)
        self.pages["settings"] = SettingsPage(self.repository)

        for key in ("dashboard", "prospection", "jobs", "finance", "reports", "settings"):
            self.stack.addWidget(self.pages[key])

        layout.addWidget(self.stack, 1)
        return content

    def _set_current_page(self, key: str) -> None:
        if key not in self.pages:
            return

        self.current_page_key = key
        meta = self.nav_meta[key]
        self.page_title.setText(meta["label"])
        self.page_subtitle.setText(meta["subtitle"])
        self.stack.setCurrentWidget(self.pages[key])
        self.nav_buttons[key].setChecked(True)

    def refresh_pages(self) -> None:
        for page in self.pages.values():
            page.refresh()
        self._set_current_page(self.current_page_key)

    def _handle_add_action(self) -> None:
        if self.current_page_key == "prospection":
            dialog = ProspectDialog(self)
            if dialog.exec():
                self.repository.add_prospect(dialog.payload())
            return

        dialog = ProjectDialog(self)
        if dialog.exec():
            self.repository.add_project(dialog.payload())

    def _edit_project(self, project_id: int) -> None:
        project = self.repository.get_project(project_id)
        if not project:
            return
        dialog = ProjectDialog(self, project=project)
        if dialog.exec():
            self.repository.update_project(project_id, dialog.payload())

    def _delete_project(self, project_id: int) -> None:
        confirm = QMessageBox.question(self, "Excluir projeto", "Deseja remover este projeto do sistema?")
        if confirm == QMessageBox.Yes:
            self.repository.delete_project(project_id)

    def _edit_prospect(self, prospect_id: int) -> None:
        prospect = self.repository.get_prospect(prospect_id)
        if not prospect:
            return
        dialog = ProspectDialog(self, prospect=prospect)
        if dialog.exec():
            self.repository.update_prospect(prospect_id, dialog.payload())

    def _delete_prospect(self, prospect_id: int) -> None:
        confirm = QMessageBox.question(self, "Excluir lead", "Deseja remover este lead da prospeccao?")
        if confirm == QMessageBox.Yes:
            self.repository.delete_prospect(prospect_id)

    def _convert_prospect(self, prospect_id: int) -> None:
        prospect = self.repository.get_prospect(prospect_id)
        if not prospect:
            return
        dialog = ProjectDialog(self, prospect=prospect)
        if dialog.exec():
            self.repository.convert_prospect_to_project(prospect_id, dialog.payload())

    def _create_backup(self) -> None:
        backup_path = self.repository.create_backup(Path(self.repository.db_path.parent) / "backups")
        QMessageBox.information(self, "Backup criado", f"Backup salvo em:\n{backup_path}")

    def closeEvent(self, event) -> None:  # noqa: N802
        self.repository.close()
        super().closeEvent(event)
