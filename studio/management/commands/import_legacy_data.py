from __future__ import annotations

import sqlite3
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from studio.models import Project, Prospect, WorkspaceSetting
from studio.services import ensure_default_settings, get_or_create_workspace_for_user


class Command(BaseCommand):
    help = "Importa dados do banco desktop antigo para o workspace de um usuario."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Usuario dono do workspace de destino.")
        parser.add_argument("--db-path", default="ugc_management.db", help="Caminho do banco legado SQLite.")

    def handle(self, *args, **options):
        username = options["username"]
        db_path = Path(options["db_path"]).resolve()

        if not db_path.exists():
            raise CommandError(f"Banco legado nao encontrado: {db_path}")

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"Usuario nao encontrado: {username}") from exc

        workspace = get_or_create_workspace_for_user(user)
        ensure_default_settings(workspace)

        legacy_connection = sqlite3.connect(db_path)
        legacy_connection.row_factory = sqlite3.Row

        prospects = legacy_connection.execute("SELECT * FROM prospects").fetchall()
        projects = legacy_connection.execute("SELECT * FROM projects").fetchall()
        settings_rows = legacy_connection.execute("SELECT key, value FROM app_settings").fetchall()

        for row in prospects:
            prospect = Prospect.objects.create(
                workspace=workspace,
                company=row["company"],
                contact=row["contact"],
                stage=row["stage"],
                proposal_value=row["proposal_value"],
                note=row["note"],
                meeting_scheduled=bool(row["meeting_scheduled"]),
            )
            Prospect.objects.filter(pk=prospect.pk).update(created_at=row["updated_at"], updated_at=row["updated_at"])

        for row in projects:
            project = Project.objects.create(
                workspace=workspace,
                company=row["company"],
                project_name=row["project_name"],
                content_type=row["content_type"],
                stage=row["stage"],
                status=row["status"],
                total_value=row["total_value"],
                entry_value=row["entry_value"],
                received_value=row["received_value"],
                deliverables_count=row["deliverables_count"],
                progress=row["progress"],
                close_date=row["close_date"],
                due_date=row["due_date"],
            )
            Project.objects.filter(pk=project.pk).update(created_at=row["updated_at"], updated_at=row["updated_at"])

        for row in settings_rows:
            WorkspaceSetting.objects.update_or_create(
                workspace=workspace,
                key=row["key"],
                defaults={"value": row["value"]},
            )

        legacy_connection.close()
        self.stdout.write(self.style.SUCCESS(f"Importacao concluida para o workspace {workspace.name}."))
