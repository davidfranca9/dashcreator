from __future__ import annotations

import shutil
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .data import COMPANY_COLORS


class UGCRepository(QObject):
    changed = Signal()

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self.db_path = db_path or Path(__file__).resolve().parent.parent / "ugc_management.db"
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self._initialize()

    def close(self) -> None:
        self.connection.close()

    def _initialize(self) -> None:
        self._create_schema()

    def _create_schema(self) -> None:
        cursor = self.connection.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS prospects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL,
                contact TEXT NOT NULL,
                stage TEXT NOT NULL,
                proposal_value REAL NOT NULL DEFAULT 0,
                note TEXT NOT NULL DEFAULT '',
                meeting_scheduled INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL,
                project_name TEXT NOT NULL,
                content_type TEXT NOT NULL,
                stage TEXT NOT NULL,
                status TEXT NOT NULL,
                total_value REAL NOT NULL DEFAULT 0,
                entry_value REAL NOT NULL DEFAULT 0,
                received_value REAL NOT NULL DEFAULT 0,
                deliverables_count INTEGER NOT NULL DEFAULT 1,
                progress INTEGER NOT NULL DEFAULT 0,
                close_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS revenue_points (
                month_label TEXT PRIMARY KEY,
                sort_order INTEGER NOT NULL,
                amount REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def _rows(self, query: str, params: tuple | dict = ()) -> list[dict]:
        cursor = self.connection.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def _one(self, query: str, params: tuple | dict = ()) -> dict | None:
        row = self.connection.execute(query, params).fetchone()
        return dict(row) if row else None

    def company_palette(self, company: str) -> tuple[str, str, str]:
        if company in COMPANY_COLORS:
            return COMPANY_COLORS[company]

        palette_values = list(COMPANY_COLORS.values())
        return palette_values[sum(ord(char) for char in company) % len(palette_values)]

    def list_prospects(self) -> list[dict]:
        return self._rows(
            """
            SELECT *
            FROM prospects
            ORDER BY
                CASE stage
                    WHEN 'Negociacao' THEN 0
                    ELSE 1
                END,
                updated_at DESC
            """
        )

    def list_projects(self) -> list[dict]:
        return self._rows(
            """
            SELECT *
            FROM projects
            ORDER BY
                CASE stage
                    WHEN 'Fechado' THEN 0
                    ELSE 1
                END,
                due_date ASC,
                updated_at DESC
            """
        )

    def get_project(self, project_id: int) -> dict | None:
        return self._one("SELECT * FROM projects WHERE id = ?", (project_id,))

    def get_prospect(self, prospect_id: int) -> dict | None:
        return self._one("SELECT * FROM prospects WHERE id = ?", (prospect_id,))

    def get_settings(self) -> dict[str, str]:
        rows = self._rows("SELECT key, value FROM app_settings")
        return {row["key"]: row["value"] for row in rows}

    def save_setting(self, key: str, value: str) -> None:
        self.connection.execute(
            """
            INSERT INTO app_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        self.connection.commit()

    def add_project(self, payload: dict) -> None:
        payload = {**payload, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        self.connection.execute(
            """
            INSERT INTO projects (
                company,
                project_name,
                content_type,
                stage,
                status,
                total_value,
                entry_value,
                received_value,
                deliverables_count,
                progress,
                close_date,
                due_date,
                updated_at
            ) VALUES (
                :company,
                :project_name,
                :content_type,
                :stage,
                :status,
                :total_value,
                :entry_value,
                :received_value,
                :deliverables_count,
                :progress,
                :close_date,
                :due_date,
                :updated_at
            )
            """,
            payload,
        )
        self.connection.commit()
        self.changed.emit()

    def update_project(self, project_id: int, payload: dict) -> None:
        payload = {**payload, "id": project_id, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        self.connection.execute(
            """
            UPDATE projects
            SET
                company = :company,
                project_name = :project_name,
                content_type = :content_type,
                stage = :stage,
                status = :status,
                total_value = :total_value,
                entry_value = :entry_value,
                received_value = :received_value,
                deliverables_count = :deliverables_count,
                progress = :progress,
                close_date = :close_date,
                due_date = :due_date,
                updated_at = :updated_at
            WHERE id = :id
            """,
            payload,
        )
        self.connection.commit()
        self.changed.emit()

    def delete_project(self, project_id: int) -> None:
        self.connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        self.connection.commit()
        self.changed.emit()

    def add_prospect(self, payload: dict) -> None:
        payload = {**payload, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        self.connection.execute(
            """
            INSERT INTO prospects (
                company,
                contact,
                stage,
                proposal_value,
                note,
                meeting_scheduled,
                updated_at
            ) VALUES (
                :company,
                :contact,
                :stage,
                :proposal_value,
                :note,
                :meeting_scheduled,
                :updated_at
            )
            """,
            payload,
        )
        self.connection.commit()
        self.changed.emit()

    def update_prospect(self, prospect_id: int, payload: dict) -> None:
        payload = {**payload, "id": prospect_id, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        self.connection.execute(
            """
            UPDATE prospects
            SET
                company = :company,
                contact = :contact,
                stage = :stage,
                proposal_value = :proposal_value,
                note = :note,
                meeting_scheduled = :meeting_scheduled,
                updated_at = :updated_at
            WHERE id = :id
            """,
            payload,
        )
        self.connection.commit()
        self.changed.emit()

    def delete_prospect(self, prospect_id: int) -> None:
        self.connection.execute("DELETE FROM prospects WHERE id = ?", (prospect_id,))
        self.connection.commit()
        self.changed.emit()

    def convert_prospect_to_project(self, prospect_id: int, payload: dict) -> None:
        self.connection.execute("DELETE FROM prospects WHERE id = ?", (prospect_id,))
        self.connection.commit()
        self.add_project(payload)

    def create_backup(self, target_dir: Path | None = None) -> Path:
        destination = target_dir or self.db_path.parent / "backups"
        destination.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = destination / f"ugc_management_{timestamp}.db"
        self.connection.commit()
        shutil.copy2(self.db_path, backup_path)
        return backup_path

    def dashboard_snapshot(self, revenue_range: str = "last_6_months") -> dict:
        active_projects = self._rows("SELECT * FROM projects WHERE stage = 'Fechado' ORDER BY due_date ASC")
        delivered_projects = self._rows("SELECT * FROM projects WHERE stage = 'Entregue' ORDER BY due_date DESC")

        active_jobs = sum(project["deliverables_count"] for project in active_projects)
        companies = self.connection.execute("SELECT COUNT(DISTINCT company) FROM projects").fetchone()[0] or 0
        total_closed = sum(project["total_value"] for project in active_projects)
        entry_value = sum(project["entry_value"] for project in active_projects)

        revenue_points = self.revenue_points(revenue_range)

        prospects = self.list_prospects()
        pipeline = [
            {
                "stage": "Prospeccao",
                "count": sum(1 for item in prospects if item["stage"] == "Prospeccao"),
                "amount": int(sum(item["proposal_value"] for item in prospects if item["stage"] == "Prospeccao")),
                "icon": "target",
                "accent": "#4d8cff",
            },
            {
                "stage": "Negociacao",
                "count": sum(1 for item in prospects if item["stage"] == "Negociacao"),
                "amount": int(sum(item["proposal_value"] for item in prospects if item["stage"] == "Negociacao")),
                "icon": "chat",
                "accent": "#4d8cff",
            },
            {
                "stage": "Fechado",
                "count": len(active_projects),
                "amount": int(total_closed),
                "icon": "check",
                "accent": "#2fb9ac",
            },
            {
                "stage": "Entregue",
                "count": sum(project["deliverables_count"] for project in delivered_projects[:4]),
                "amount": int(sum(project["total_value"] for project in delivered_projects[:4])),
                "icon": "clock",
                "accent": "#aeb9c9",
            },
        ]
        for item in pipeline:
            item["progress"] = 0 if item["amount"] == 0 else {
                "Prospeccao": 54,
                "Negociacao": 33,
                "Fechado": 72,
                "Entregue": 59,
            }[item["stage"]]

        activities = []
        for project in active_projects[:2]:
            color_a, color_b, accent = self.company_palette(project["company"])
            activities.append(
                {
                    "id": project["id"],
                    "project": project["project_name"],
                    "company": project["company"],
                    "content_type": project["content_type"],
                    "progress": project["progress"],
                    "date": self._format_short_date(project["due_date"]),
                    "colors": (color_a, color_b),
                    "accent": accent,
                }
            )

        featured_project = active_projects[0] if active_projects else None
        featured = None
        if featured_project:
            color_a, color_b, accent = self.company_palette(featured_project["company"])
            featured = {
                **featured_project,
                "amount_text": self.currency(featured_project["total_value"]),
                "due_text": self._format_short_date(featured_project["due_date"]),
                "colors": (color_a, color_b),
                "accent": accent,
            }

        return {
            "stats": [
                {"title": "Trabalhos Ativos", "value": str(active_jobs), "icon": "briefcase", "accent": "#9fb4d5"},
                {"title": "Empresas Contratantes", "value": str(companies), "icon": "building", "accent": "#9fb4d5"},
                {"title": "Total Fechado", "value": self.currency(total_closed), "icon": "money", "accent": "#9fb4d5"},
                {"title": "Entrada", "value": self.currency(entry_value), "icon": "entry", "accent": "#9fb4d5"},
            ],
            "revenue_points": revenue_points,
            "pipeline": pipeline,
            "activities": activities,
            "featured": featured,
        }

    def prospection_snapshot(self) -> dict:
        prospects = self.list_prospects()
        total = len(prospects) or 1
        meetings = sum(item["meeting_scheduled"] for item in prospects)
        negotiation_count = sum(1 for item in prospects if item["stage"] == "Negociacao")

        columns = []
        for stage in ("Prospeccao", "Negociacao"):
            items = [item for item in prospects if item["stage"] == stage]
            for item in items:
                color_a, color_b, accent = self.company_palette(item["company"])
                item["accent"] = accent
                item["colors"] = (color_a, color_b)
            columns.append({"title": stage, "items": items})

        return {
            "stats": [
                {"title": "Novos Leads", "value": str(sum(1 for item in prospects if item["stage"] == "Prospeccao")), "icon": "search"},
                {"title": "Reunioes", "value": str(meetings), "icon": "chat"},
                {"title": "Taxa de resposta", "value": f"{round((negotiation_count / total) * 100)}%", "icon": "chart"},
                {"title": "Pipeline previsto", "value": self.currency(sum(item["proposal_value"] for item in prospects)), "icon": "money"},
            ],
            "columns": columns,
        }

    def jobs_snapshot(self) -> dict:
        projects = self.list_projects()
        active = [item for item in projects if item["stage"] == "Fechado"]
        delivered = [item for item in projects if item["stage"] == "Entregue"][:4]
        today = date.today()
        upcoming_limit = today + timedelta(days=21)

        for project in projects:
            color_a, color_b, accent = self.company_palette(project["company"])
            project["colors"] = (color_a, color_b)
            project["accent"] = accent
            project["due_text"] = self._format_short_date(project["due_date"])

        upcoming_deliveries = 0
        for project in active:
            due = datetime.strptime(project["due_date"], "%Y-%m-%d").date()
            if today <= due <= upcoming_limit:
                upcoming_deliveries += 1

        average_ticket = round(sum(item["total_value"] for item in active) / len(active)) if active else 0

        return {
            "stats": [
                {"title": "Jobs ativos", "value": str(len(active)), "icon": "briefcase"},
                {"title": "Aguardando cliente", "value": str(sum(1 for item in active if item["status"] == "Aguardando cliente")), "icon": "clock"},
                {"title": "Entregas proximas", "value": str(upcoming_deliveries), "icon": "check"},
                {"title": "Ticket medio", "value": self.currency(average_ticket), "icon": "money"},
            ],
            "active": active,
            "delivered": delivered,
        }

    def finance_snapshot(self) -> dict:
        active_projects = self._rows("SELECT * FROM projects WHERE stage = 'Fechado' ORDER BY due_date ASC")
        total_closed = sum(item["total_value"] for item in active_projects)
        received = sum(item["received_value"] for item in active_projects)
        receivable = total_closed - received
        entry = sum(item["entry_value"] for item in active_projects)

        schedule = []
        for item in active_projects:
            outstanding = max(item["total_value"] - item["received_value"], 0)
            if outstanding <= 0:
                continue

            color_a, color_b, accent = self.company_palette(item["company"])
            schedule.append(
                {
                    "company": item["company"],
                    "kind": "Saldo" if item["received_value"] > 0 else "Entrada",
                    "due": self._format_short_date(item["due_date"]),
                    "amount": self.currency(outstanding),
                    "status": "Pendente" if outstanding else "Quitado",
                    "accent": accent,
                }
            )

        return {
            "stats": [
                {"title": "Total Fechado", "value": self.currency(total_closed), "icon": "money"},
                {"title": "Ja recebido", "value": self.currency(received), "icon": "entry"},
                {"title": "A receber", "value": self.currency(receivable), "icon": "wallet"},
                {
                    "title": "Entrada media",
                    "value": f"{round((entry / total_closed) * 100) if total_closed else 0}%",
                    "icon": "chart",
                },
            ],
            "schedule": schedule,
            "breakdown": [
                {"label": "Total fechado", "amount_text": self.currency(total_closed), "progress": 100, "accent": "#20b7a7"},
                {"label": "Dinheiro de entrada", "amount_text": self.currency(entry), "progress": round((entry / total_closed) * 100) if total_closed else 0, "accent": "#4d8cff"},
                {"label": "A receber", "amount_text": self.currency(receivable), "progress": round((receivable / total_closed) * 100) if total_closed else 0, "accent": "#7f6fff"},
                {"label": "Ja recebido", "amount_text": self.currency(received), "progress": round((received / total_closed) * 100) if total_closed else 0, "accent": "#f59a3d"},
            ],
        }

    def reports_snapshot(self) -> dict:
        projects = self._rows("SELECT * FROM projects")
        active = [item for item in projects if item["stage"] == "Fechado"]
        delivered = [item for item in projects if item["stage"] == "Entregue"]
        prospects = self.list_prospects()

        delivered_on_time = sum(
            1
            for item in delivered
            if datetime.strptime(item["updated_at"], "%Y-%m-%d %H:%M:%S").date()
            <= datetime.strptime(item["due_date"], "%Y-%m-%d").date()
        )
        first_pass = sum(1 for item in active if item["status"] in {"Aprovado", "Entregue"})
        conversion_rate = round((len(active) / (len(active) + len(prospects))) * 100) if active or prospects else 0
        payments_on_time = round((sum(item["received_value"] for item in active) / sum(item["entry_value"] for item in active)) * 100) if active else 0
        delivered_units = sum(item["deliverables_count"] for item in delivered[-8:])
        avg_days = self._average_project_days(projects)
        margin = round(((sum(item["total_value"] for item in active) - (sum(item["total_value"] for item in active) * 0.37)) / sum(item["total_value"] for item in active)) * 100) if active else 0
        delivered_by_company = {}
        for item in delivered:
            delivered_by_company[item["company"]] = delivered_by_company.get(item["company"], 0) + 1
        repeat_rate = round((sum(1 for count in delivered_by_company.values() if count > 1) / len(delivered_by_company)) * 100) if delivered_by_company else 0

        return {
            "stats": [
                {"title": "Conteudos entregues", "value": str(delivered_units), "icon": "check"},
                {"title": "Taxa de recompra", "value": f"{repeat_rate}%", "icon": "chart"},
                {"title": "Tempo medio", "value": f"{avg_days:.1f} dias", "icon": "clock"},
                {"title": "Margem estimada", "value": f"{margin}%", "icon": "money"},
            ],
            "breakdown": [
                {"label": "Propostas convertidas", "amount_text": f"{conversion_rate}%", "progress": conversion_rate, "accent": "#4d8cff"},
                {"label": "Projetos entregues no prazo", "amount_text": f"{round((delivered_on_time / max(1, len(delivered))) * 100)}%", "progress": round((delivered_on_time / max(1, len(delivered))) * 100), "accent": "#20b7a7"},
                {"label": "Aprovacao sem retrabalho", "amount_text": f"{round((first_pass / max(1, len(active))) * 100)}%", "progress": round((first_pass / max(1, len(active))) * 100), "accent": "#7f6fff"},
                {"label": "Recebimentos em dia", "amount_text": f"{payments_on_time}%", "progress": payments_on_time, "accent": "#f59a3d"},
            ],
            "highlights": [
                {"title": "Canal com melhor retorno", "description": "Instagram Reels continua puxando a maior parte dos leads qualificados."},
                {"title": "Pacote mais lucrativo", "description": "Combos com 3 videos UGC mantem boa margem e recompra recorrente."},
                {"title": "Gargalo do mes", "description": "Aguardando cliente ainda alonga o prazo dos jobs de moda e beleza."},
            ],
        }

    def _average_project_days(self, projects: list[dict]) -> float:
        values = []
        for item in projects:
            close_date = datetime.strptime(item["close_date"], "%Y-%m-%d").date()
            due_date = datetime.strptime(item["due_date"], "%Y-%m-%d").date()
            values.append(max((due_date - close_date).days, 1))
        return round(sum(values) / len(values), 1) if values else 0.0

    def revenue_points(self, revenue_range: str = "last_6_months") -> list[tuple[str, int]]:
        months_by_range = {
            "current_month": 1,
            "last_quarter": 3,
            "last_6_months": 6,
        }
        month_count = months_by_range.get(revenue_range, 6)
        month_starts = self._month_window(month_count)
        totals = {month_start: 0.0 for month_start in month_starts}

        for item in self._rows("SELECT close_date, total_value FROM projects"):
            close_date = datetime.strptime(item["close_date"], "%Y-%m-%d").date()
            month_start = close_date.replace(day=1)
            if month_start in totals:
                totals[month_start] += float(item["total_value"])

        return [(self._format_month_label(month_start), int(round(totals[month_start]))) for month_start in month_starts]

    def _month_window(self, month_count: int) -> list[date]:
        current_month = date.today().replace(day=1)
        return [self._shift_month(current_month, -offset) for offset in range(month_count - 1, -1, -1)]

    def _shift_month(self, base_date: date, months: int) -> date:
        absolute_month = (base_date.year * 12) + (base_date.month - 1) + months
        year = absolute_month // 12
        month = (absolute_month % 12) + 1
        return date(year, month, 1)

    def currency(self, value: int | float) -> str:
        formatted = f"{value:,.0f}"
        formatted = formatted.replace(",", "_").replace(".", ",").replace("_", ".")
        return f"R${formatted}"

    def _format_short_date(self, iso_date: str) -> str:
        months = {
            1: "Jan",
            2: "Fev",
            3: "Mar",
            4: "Abr",
            5: "Mai",
            6: "Jun",
            7: "Jul",
            8: "Ago",
            9: "Set",
            10: "Out",
            11: "Nov",
            12: "Dez",
        }
        parsed = datetime.strptime(iso_date, "%Y-%m-%d").date()
        return f"{parsed.day:02d} {months[parsed.month]}"

    def _format_month_label(self, month_date: date) -> str:
        months = {
            1: "Jan",
            2: "Fev",
            3: "Mar",
            4: "Abr",
            5: "Mai",
            6: "Jun",
            7: "Jul",
            8: "Ago",
            9: "Set",
            10: "Out",
            11: "Nov",
            12: "Dez",
        }
        return f"{months[month_date.month]}/{month_date.year % 100:02d}"
